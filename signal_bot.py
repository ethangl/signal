"""Weekly QQQ regime signal bot. See SPEC.md."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

STATE_FILE = Path(__file__).parent / "state.json"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
PUSHOVER_URL = "https://api.pushover.net/1/messages.json"


def yf_close_and_sma(ticker: str, window: int = 200) -> tuple[float, float]:
    df = yf.download(ticker, period="2y", progress=False, auto_adjust=False)
    closes = df["Close"].dropna().squeeze()
    if len(closes) < window:
        raise RuntimeError(f"{ticker}: only {len(closes)} closes, need {window}")
    return float(closes.iloc[-1]), float(closes.rolling(window).mean().iloc[-1])


def fred_close_and_sma(series: str, window: int = 26) -> tuple[float, float]:
    key = os.environ["FRED_API_KEY"]
    r = requests.get(
        FRED_URL,
        params={"series_id": series, "api_key": key, "file_type": "json"},
        timeout=30,
    )
    r.raise_for_status()
    obs = [float(o["value"]) for o in r.json()["observations"] if o["value"] != "."]
    if len(obs) < window:
        raise RuntimeError(f"{series}: only {len(obs)} obs, need {window}")
    s = pd.Series(obs)
    return float(s.iloc[-1]), float(s.tail(window).mean())


def compute() -> dict:
    lqd, lqd_ma = yf_close_and_sma("LQD")
    move, move_ma = yf_close_and_sma("^MOVE")
    nfci, nfci_ma = fred_close_and_sma("NFCICREDIT")
    c = [lqd > lqd_ma, move < move_ma, nfci < nfci_ma]
    score = sum(c)
    regime = "risk-on" if score >= 2 else "risk-off"
    target = "100% QQQ" if regime == "risk-on" else "60% GLD / 40% UUP"
    return {
        "regime": regime,
        "score": score,
        "target": target,
        "lqd": [lqd, lqd_ma, c[0]],
        "move": [move, move_ma, c[1]],
        "nfci": [nfci, nfci_ma, c[2]],
        "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def render(s: dict) -> str:
    def row(name: str, fmt: str, vals: list) -> str:
        v, ma, ok = vals
        return f"{name}: {v:{fmt}} vs MA {ma:{fmt}} {'✓' if ok else '✗'}"
    return (
        f"Score {s['score']}/3 ({s['regime']}). Target: {s['target']}.\n"
        + row("LQD", ".2f", s["lqd"]) + "\n"
        + row("MOVE", ".2f", s["move"]) + "\n"
        + row("NFCI_cr", ".4f", s["nfci"])
    )


def render_change(s: dict, prev_target: str) -> str:
    def row(name: str, fmt: str, vals: list) -> str:
        v, ma, ok = vals
        return f"{name}: {v:{fmt}} vs MA {ma:{fmt}} {'✓' if ok else '✗'}"
    return (
        f"REGIME CHANGE: {s['regime']}. Score {s['score']}/3.\n"
        f"Monday 10:30am ET: SELL {prev_target}, BUY {s['target']}.\n"
        + row("LQD", ".2f", s["lqd"]) + "\n"
        + row("MOVE", ".2f", s["move"]) + "\n"
        + row("NFCI_cr", ".4f", s["nfci"])
    )


def push(msg: str) -> None:
    r = requests.post(
        PUSHOVER_URL,
        data={
            "token": os.environ["PUSHOVER_API_TOKEN"],
            "user": os.environ["PUSHOVER_USER_KEY"],
            "message": msg,
            "title": "QQQ Regime Signal",
        },
        timeout=30,
    )
    r.raise_for_status()


def main() -> int:
    state = compute()
    print(render(state))

    prev = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    changed = bool(prev) and prev.get("regime") != state["regime"]

    if changed:
        msg = render_change(state, prev.get("target", "current holdings"))
        print("\n--- REGIME CHANGE ---")
        print(msg)
        push(msg)
    elif not prev:
        print("\nFirst run: initializing state, no notification.")
    else:
        print(f"\nNo change. Still {state['regime']}.")

    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
