"""Daily QQQ regime signal bot with asymmetric hysteresis + depth-aware off-bucket. See docs/SPEC.md."""
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

# depth → (description, ordered allocation dict). Iteration order is the
# canonical render order for SELL/BUY/TARGET lines.
DEPTH_ALLOCATIONS = {
    0: ("deep stress", {"XLU": 10, "GLD": 55, "UUP": 35}),
    1: ("mild stress", {"XLU": 30, "GLD": 45, "UUP": 25}),
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


def depth_for_score(score: int) -> int:
    """0 = deep stress, 1 = mild stress. For score>=2 (risk-on macro) we fall
    back to 1 — only used during v1.8→v1.9 migration when the score has already
    crossed the risk-on threshold but the buffer hasn't confirmed yet."""
    return 0 if score == 0 else 1


def fmt_alloc(alloc: dict) -> str:
    return " + ".join(f"{v}% {k}" for k, v in alloc.items())


def alloc_delta(prev: dict, new: dict) -> tuple[dict, dict]:
    """Return (sells, buys), each ordered like `new` and including 0% entries
    so depth-change notifications show all three tickers per spec format."""
    sells, buys = {}, {}
    for k in new:
        delta = new[k] - prev.get(k, 0)
        sells[k] = max(-delta, 0)
        buys[k] = max(delta, 0)
    return sells, buys


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


def render_off_flip(state: dict) -> str:
    desc = DEPTH_ALLOCATIONS[state["current_depth"]][0]
    return (
        f"REGIME CHANGE: risk-off\n"
        f"Macro score {state['score']}/3 — {desc}\n\n"
        f"Monday 10:30am ET execution:\n"
        f"SELL: 100% QQQ\n"
        f"BUY:  {fmt_alloc(state['current_allocation'])}\n\n"
        f"Macro components:\n"
        + render_components(state["components"])
    )


def render_depth_change(state: dict, prev_alloc: dict, direction: str) -> str:
    adj = "deep-stress" if state["current_depth"] == 0 else "mild-stress"
    sells, buys = alloc_delta(prev_alloc, state["current_allocation"])
    return (
        f"DEPTH CHANGE: stress {direction} to score {state['score']}/3\n"
        f"Allocation rotating to {adj} weights\n\n"
        f"Monday 10:30am ET execution (rebalance within risk-off):\n"
        f"SELL: {fmt_alloc(sells)}\n"
        f"BUY:  {fmt_alloc(buys)}\n"
        f"TARGET: {fmt_alloc(state['current_allocation'])}\n\n"
        f"Macro components:\n"
        + render_components(state["components"])
    )


def render_on_flip(state: dict, prev_alloc: dict | None) -> str:
    sell = fmt_alloc(prev_alloc) if prev_alloc else "current off-bucket allocation"
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
        target = fmt_alloc(state["current_allocation"])
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

    prev_buffer = (
        prev.get("macro_rolling_buffer")
        or prev.get("rolling_buffer")
        or prev.get("buffer")
    )

    needs_buffer_migration = bool(prev) and (
        prev_buffer is None or len(prev_buffer) != BUFFER_SIZE
    )
    # v1.8 → v1.9: active risk-off positions get current_depth seeded from
    # the current macro_score and inherit the v1.8 off_allocation. No
    # depth-change notification fires on the migration run itself.
    needs_v19_migration = (
        prev.get("deployed_state") == "risk-off" and "current_depth" not in prev
    )
    is_new_close = prev.get("last_close_date") != cur["last_close_date"]

    if not is_new_close and not needs_buffer_migration and not needs_v19_migration:
        print(
            f"Already processed close of {cur['last_close_date']}. No-op.\n"
            f"deployed_state: {prev.get('deployed_state')}, "
            f"macro_rolling_buffer: {prev_buffer}"
        )
        return 0

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

    prev_depth = prev.get("current_depth")
    prev_alloc = prev.get("current_allocation") or prev.get("off_allocation")

    depth_change_direction = None
    if deployed == "risk-on":
        state["current_depth"] = None
        state["current_allocation"] = None
        state["last_classified_at"] = None
    elif flipped_to_off or prev_deployed is None:
        depth = depth_for_score(cur["score"])
        state["current_depth"] = depth
        state["current_allocation"] = DEPTH_ALLOCATIONS[depth][1]
        state["last_classified_at"] = state["asof"]
    elif needs_v19_migration:
        depth = depth_for_score(cur["score"])
        state["current_depth"] = depth
        state["current_allocation"] = prev_alloc or DEPTH_ALLOCATIONS[depth][1]
        state["last_classified_at"] = prev.get("off_classified_at") or state["asof"]
    else:
        new_depth = prev_depth
        if prev_depth == 1 and cur["score"] == 0:
            new_depth = 0
            depth_change_direction = "deepening"
        elif prev_depth == 0 and cur["score"] == 1:
            new_depth = 1
            depth_change_direction = "easing"
        state["current_depth"] = new_depth
        if depth_change_direction:
            state["current_allocation"] = DEPTH_ALLOCATIONS[new_depth][1]
            state["last_classified_at"] = state["asof"]
        else:
            state["current_allocation"] = prev_alloc
            state["last_classified_at"] = (
                prev.get("last_classified_at") or prev.get("off_classified_at")
            )

    print(render_status(state))

    if flipped_to_off:
        title, msg = "REGIME CHANGE: risk-off", render_off_flip(state)
    elif flipped_to_on:
        title, msg = "REGIME CHANGE: risk-on", render_on_flip(state, prev_alloc)
    elif depth_change_direction:
        title = f"DEPTH CHANGE: stress {depth_change_direction}"
        msg = render_depth_change(state, prev_alloc, depth_change_direction)
    else:
        title = msg = None

    if msg:
        print("\n--- " + title + " ---")
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
