"""Daily QQQ regime signal bot with asymmetric hysteresis. See SPEC.md."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

STATE_FILE = Path(__file__).parent / "last_state.json"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
PUSHOVER_URL = "https://api.pushover.net/1/messages.json"

ALLOC = {
    "risk-on": "100% QQQ",
    "risk-off": "30% XLU / 40% GLD / 30% UUP",
}


def yf_close_sma(ticker: str, window: int = 200) -> tuple[float, float, str]:
    df = yf.download(ticker, period="2y", progress=False, auto_adjust=False)
    closes = df["Close"].dropna().squeeze()
    if len(closes) < window:
        raise RuntimeError(f"{ticker}: only {len(closes)} closes, need {window}")
    last_date = pd.Timestamp(closes.index[-1]).strftime("%Y-%m-%d")
    return (
        float(closes.iloc[-1]),
        float(closes.rolling(window).mean().iloc[-1]),
        last_date,
    )


def fred_close_sma(series: str, window: int = 26) -> tuple[float, float]:
    r = requests.get(
        FRED_URL,
        params={
            "series_id": series,
            "api_key": os.environ["FRED_API_KEY"],
            "file_type": "json",
        },
        timeout=30,
    )
    r.raise_for_status()
    obs = [float(o["value"]) for o in r.json()["observations"] if o["value"] != "."]
    if len(obs) < window:
        raise RuntimeError(f"{series}: only {len(obs)} obs, need {window}")
    s = pd.Series(obs)
    return float(s.iloc[-1]), float(s.tail(window).mean())


def compute() -> dict:
    lqd, lqd_ma, close_date = yf_close_sma("LQD")
    move, move_ma, _ = yf_close_sma("^MOVE")
    nfci, nfci_ma = fred_close_sma("NFCICREDIT")
    c = [lqd > lqd_ma, move < move_ma, nfci < nfci_ma]
    score = sum(c)
    raw = "risk-on" if score >= 2 else "risk-off"
    return {
        "raw_signal": raw,
        "score": score,
        "last_close_date": close_date,
        "components": {
            "lqd": [lqd, lqd_ma, c[0]],
            "move": [move, move_ma, c[1]],
            "nfci": [nfci, nfci_ma, c[2]],
        },
    }


def apply_hysteresis(raw: str, prev_deployed: str | None, buffer: list) -> str:
    if prev_deployed is None:
        return raw
    if raw == "risk-off":
        return "risk-off"
    if prev_deployed == "risk-on":
        return "risk-on"
    if len(buffer) >= 3 and all(b == "risk-on" for b in buffer[-3:]):
        return "risk-on"
    return "risk-off"


def render_components(comp: dict) -> str:
    def row(name: str, fmt: str, vals: list) -> str:
        v, ma, ok = vals
        return f"{name}: {v:{fmt}} vs MA {ma:{fmt}} {'✓' if ok else '✗'}"
    return (
        row("LQD", ".2f", comp["lqd"]) + "\n"
        + row("MOVE", ".2f", comp["move"]) + "\n"
        + row("NFCI_cr", ".4f", comp["nfci"])
    )


def render_status(s: dict) -> str:
    return (
        f"raw_signal: {s['raw_signal']} (score {s['score']}/3)\n"
        f"deployed_state: {s['deployed_state']}\n"
        f"target: {ALLOC[s['deployed_state']]}\n"
        f"buffer: {s['buffer']}\n"
        f"as of close: {s['last_close_date']}\n\n"
        + render_components(s["components"])
    )


def render_change(s: dict, prev_deployed: str) -> str:
    return (
        f"Signal flipped to {s['deployed_state']}. Score {s['score']}/3.\n"
        f"Monday 10:30am ET execution:\n"
        f"SELL: {ALLOC[prev_deployed]}\n"
        f"BUY: {ALLOC[s['deployed_state']]}\n\n"
        f"Components:\n"
        + render_components(s["components"]) + "\n\n"
        f"Hysteresis buffer: {s['buffer']}"
    )


def push(title: str, msg: str) -> None:
    r = requests.post(
        PUSHOVER_URL,
        data={
            "token": os.environ["PUSHOVER_API_TOKEN"],
            "user": os.environ["PUSHOVER_USER_KEY"],
            "title": title,
            "message": msg,
        },
        timeout=30,
    )
    r.raise_for_status()


def main() -> int:
    cur = compute()
    prev = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}

    if prev.get("last_close_date") == cur["last_close_date"]:
        print(
            f"Already processed close of {cur['last_close_date']}. No-op.\n"
            f"deployed_state: {prev.get('deployed_state')}, "
            f"buffer: {prev.get('buffer')}"
        )
        return 0

    buffer = (prev.get("buffer", []) + [cur["raw_signal"]])[-3:]
    prev_deployed = prev.get("deployed_state")
    deployed = apply_hysteresis(cur["raw_signal"], prev_deployed, buffer)

    state = {
        **cur,
        "deployed_state": deployed,
        "buffer": buffer,
        "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    print(render_status(state))

    changed = prev_deployed is not None and prev_deployed != deployed
    if changed:
        title = f"REGIME CHANGE: {deployed}"
        msg = render_change(state, prev_deployed)
        print("\n--- REGIME CHANGE ---")
        print(msg)
        push(title, msg)
    elif not prev:
        print("\nFirst run: state initialized, no notification.")
    else:
        print(f"\nNo change. Deployed still {deployed}.")

    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
