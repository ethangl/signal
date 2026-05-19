"""Daily QQQ regime signal bot with asymmetric hysteresis. See docs/SPEC.md."""
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

BUFFER_SIZE = 3

# (dollar, nfci) → (regime name, off-bucket allocation as ordered dict).
DOLLAR_REGIMES = {
    ("strong", "tight"): ("stress",          {"XLU": 10, "GLD": 30, "UUP": 60}),
    ("strong", "loose"): ("cyclical strong", {"XLU": 30, "GLD": 40, "UUP": 30}),
    ("weak",   "tight"): ("weak",            {"XLU": 30, "GLD": 50, "UUP": 20}),
    ("weak",   "loose"): ("weak",            {"XLU": 30, "GLD": 50, "UUP": 20}),
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


def fred_observations(series: str) -> list[float]:
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
    return [float(o["value"]) for o in r.json()["observations"] if o["value"] != "."]


def fred_value_and_sma(series: str, window: int) -> tuple[float, float]:
    obs = fred_observations(series)
    if len(obs) < window:
        raise RuntimeError(f"{series}: only {len(obs)} obs, need {window}")
    s = pd.Series(obs)
    return float(s.iloc[-1]), float(s.tail(window).mean())


def fred_latest(series: str) -> float:
    obs = fred_observations(series)
    if not obs:
        raise RuntimeError(f"{series}: no observations")
    return obs[-1]


def compute_raw_signal() -> dict:
    lqd, lqd_ma, close_date = yf_close_sma("LQD")
    move, move_ma, _ = yf_close_sma("^MOVE")
    qqq, qqq_ma, _ = yf_close_sma("QQQ", window=50)
    nfci_cr, nfci_cr_ma = fred_value_and_sma("NFCICREDIT", 26)
    c = [lqd > lqd_ma, move < move_ma, nfci_cr < nfci_cr_ma]
    score = sum(c)
    macro = "risk-on" if score >= 2 else "risk-off"
    price_filter = qqq > qqq_ma
    return {
        "macro_signal": macro,
        "score": score,
        "price_filter": price_filter,
        "last_close_date": close_date,
        "components": {
            "lqd":  [lqd,     lqd_ma,     c[0]],
            "move": [move,    move_ma,    c[1]],
            "nfci": [nfci_cr, nfci_cr_ma, c[2]],
            "qqq":  [qqq,     qqq_ma,     price_filter],
        },
    }


def classify_dollar_regime() -> dict:
    dtwex, dtwex_ma = fred_value_and_sma("DTWEXBGS", 200)
    nfci = fred_latest("NFCI")
    dollar = "strong" if dtwex > dtwex_ma else "weak"
    tightness = "tight" if nfci > 0 else "loose"
    name, alloc = DOLLAR_REGIMES[(dollar, tightness)]
    return {
        "dollar": dollar,
        "nfci": tightness,
        "regime": name,
        "allocation": alloc,
        "dtwex": [dtwex, dtwex_ma],
        "nfci_val": nfci,
    }


def apply_hysteresis(
    buffer: list[str], prev_deployed: str | None, price_filter: bool
) -> str:
    macro = buffer[-1]
    if prev_deployed is None:
        # First run: seed deployed_state from macro_signal alone. Price filter
        # only gates re-entry from an established risk-off state.
        return macro
    if macro == "risk-off":
        return "risk-off"
    if prev_deployed == "risk-on":
        return "risk-on"
    macro_streak = (
        len(buffer) >= BUFFER_SIZE
        and all(b == "risk-on" for b in buffer[-BUFFER_SIZE:])
    )
    if macro_streak and price_filter:
        return "risk-on"
    return "risk-off"


def fmt_alloc(alloc: dict) -> str:
    return " + ".join(f"{v}% {k}" for k, v in alloc.items())


def render_components(comp: dict) -> str:
    mark = lambda b: "✓" if b else "✗"
    lqd_v, lqd_m, lqd_ok = comp["lqd"]
    mv_v,  mv_m,  mv_ok  = comp["move"]
    nf_v,  nf_m,  nf_ok  = comp["nfci"]
    return (
        f"LQD:     {lqd_v:8.2f} vs 200d MA {lqd_m:8.2f}   {mark(lqd_ok)}\n"
        f"MOVE:    {mv_v:8.2f} vs 200d MA {mv_m:8.2f}   {mark(mv_ok)}\n"
        f"NFCI_cr: {nf_v:+.4f}  vs 26w MA {nf_m:+.4f}    {mark(nf_ok)}"
    )


def render_price_filter(comp: dict) -> str:
    qqq_v, qqq_m, qqq_ok = comp["qqq"]
    mark = "✓" if qqq_ok else "✗"
    return f"QQQ {qqq_v:.2f} vs 50d MA {qqq_m:.2f} [{mark}]"


def render_dollar_context(regime: dict) -> str:
    dtwex_v, dtwex_m = regime["dtwex"]
    return (
        f"DTWEXBGS: {dtwex_v:8.2f} vs 200d MA {dtwex_m:8.2f}   {regime['dollar']}\n"
        f"NFCI:     {regime['nfci_val']:+.4f}                       {regime['nfci']}"
    )


def render_off_flip(state: dict) -> str:
    regime = state["off_regime"]
    return (
        f"REGIME CHANGE: risk-off\n"
        f"Macro score {state['score']}/3. Dollar regime: {regime['regime']}\n\n"
        f"Monday 10:30am ET execution:\n"
        f"SELL: 100% QQQ\n"
        f"BUY:  {fmt_alloc(state['off_allocation'])}\n\n"
        f"Macro components:\n"
        + render_components(state["components"]) + "\n\n"
        f"Dollar regime context:\n"
        + render_dollar_context(regime)
    )


def render_on_flip(state: dict, prev_off_alloc: dict | None) -> str:
    sell = fmt_alloc(prev_off_alloc) if prev_off_alloc else "current off-bucket allocation"
    return (
        f"REGIME CHANGE: risk-on\n"
        f"Macro score {state['score']}/3 confirmed for {BUFFER_SIZE} consecutive days.\n"
        f"Price filter: {render_price_filter(state['components'])}\n\n"
        f"Monday 10:30am ET execution:\n"
        f"SELL: {sell}\n"
        f"BUY:  100% QQQ\n\n"
        f"Macro components:\n"
        + render_components(state["components"])
    )


def render_status(state: dict) -> str:
    if state["deployed_state"] == "risk-on":
        target = "100% QQQ"
    else:
        target = fmt_alloc(state["off_allocation"])
    pf = "✓" if state["price_filter"] else "✗"
    return (
        f"macro_signal: {state['macro_signal']} (score {state['score']}/3)\n"
        f"price_filter: {pf}  ({render_price_filter(state['components'])})\n"
        f"deployed_state: {state['deployed_state']}\n"
        f"target: {target}\n"
        f"macro_rolling_buffer: {state['macro_rolling_buffer']}\n"
        f"as of close: {state['last_close_date']}\n\n"
        + render_components(state["components"])
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
    cur = compute_raw_signal()
    prev = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}

    # v1.7 → v1.8: state file rename rolling_buffer → macro_rolling_buffer
    # and resize from 5 to 3. Accept either old name on read.
    prev_buffer = prev.get("macro_rolling_buffer")
    if prev_buffer is None:
        prev_buffer = prev.get("rolling_buffer") or prev.get("buffer")

    needs_buffer_migration = bool(prev) and (
        prev_buffer is None or len(prev_buffer) != BUFFER_SIZE
    )
    needs_alloc_classification = (
        prev.get("deployed_state") == "risk-off" and "off_allocation" not in prev
    )
    is_new_close = prev.get("last_close_date") != cur["last_close_date"]

    if not is_new_close and not (needs_buffer_migration or needs_alloc_classification):
        print(
            f"Already processed close of {cur['last_close_date']}. No-op.\n"
            f"deployed_state: {prev.get('deployed_state')}, "
            f"macro_rolling_buffer: {prev_buffer}"
        )
        return 0

    # On schema migration, seed macro_rolling_buffer with the current
    # macro_signal repeated BUFFER_SIZE times (per v1.7 → v1.8 spec).
    if needs_buffer_migration:
        buffer = [cur["macro_signal"]] * BUFFER_SIZE
    elif is_new_close:
        buffer = ((prev_buffer or []) + [cur["macro_signal"]])[-BUFFER_SIZE:]
    else:
        buffer = prev_buffer

    prev_deployed = prev.get("deployed_state")
    deployed = apply_hysteresis(buffer, prev_deployed, cur["price_filter"])

    state = {
        **cur,
        "deployed_state": deployed,
        "macro_rolling_buffer": buffer,
        "asof": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    flipped_to_off = prev_deployed == "risk-on" and deployed == "risk-off"
    flipped_to_on  = prev_deployed == "risk-off" and deployed == "risk-on"
    prev_off_alloc = prev.get("off_allocation")

    # Classify whenever we (re)enter risk-off OR when migrating an existing
    # risk-off state that pre-dates the v1.5 → v1.6 schema.
    if deployed == "risk-off" and (flipped_to_off or prev_off_alloc is None):
        regime = classify_dollar_regime()
        state["off_regime"] = regime
        state["off_allocation"] = regime["allocation"]
        state["off_classified_at"] = state["asof"]
    elif deployed == "risk-off":
        state["off_regime"] = prev.get("off_regime")
        state["off_allocation"] = prev_off_alloc
        state["off_classified_at"] = prev.get("off_classified_at")

    print(render_status(state))

    if flipped_to_off:
        title, msg = "REGIME CHANGE: risk-off", render_off_flip(state)
    elif flipped_to_on:
        title, msg = "REGIME CHANGE: risk-on", render_on_flip(state, prev_off_alloc)
    else:
        title = msg = None

    if msg:
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
