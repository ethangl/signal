"""Manual sanity check: print live signal + last committed state. No notifications."""
import json
from pathlib import Path

from main import (
    DEPTH_ALLOCATIONS,
    compute_raw_signal,
    fmt_alloc,
    render_components,
    render_price_filter,
)

STATE_FILE = Path(__file__).parent / "last_state.json"

if __name__ == "__main__":
    cur = compute_raw_signal()
    print("Live raw signal (not committed):")
    print(f"  macro_signal: {cur['macro_signal']} (score {cur['score']}/3)")
    print(f"  price_filter: {'✓' if cur['price_filter'] else '✗'} ({render_price_filter(cur['components'])})")
    print(f"  as of close: {cur['last_close_date']}\n")
    print(render_components(cur["components"]))
    print()
    if not STATE_FILE.exists():
        print("No committed state yet (first run pending).")
    else:
        prev = json.loads(STATE_FILE.read_text())
        deployed = prev["deployed_state"]
        alloc = prev.get("current_allocation") or prev.get("off_allocation")
        if deployed == "risk-on":
            target = "100% QQQ"
        elif alloc:
            target = fmt_alloc(alloc)
        else:
            target = "(off-bucket classification pending next main.py run)"
        buf = (
            prev.get("macro_rolling_buffer")
            or prev.get("rolling_buffer")
            or prev.get("buffer")
        )
        print(f"Last committed state ({prev.get('asof')}):")
        print(f"  deployed_state:       {deployed}")
        print(f"  target:               {target}")
        print(f"  macro_rolling_buffer: {buf}")
        print(f"  last_close:           {prev['last_close_date']}")
        if deployed == "risk-off" and alloc:
            depth = prev.get("current_depth")
            depth_desc = DEPTH_ALLOCATIONS[depth][0] if depth in DEPTH_ALLOCATIONS else "unclassified"
            classified_at = prev.get("last_classified_at") or prev.get("off_classified_at")
            print(f"  current_depth:        {depth} ({depth_desc})")
            print(f"  classified_at:        {classified_at}")
