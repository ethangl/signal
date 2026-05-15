"""Manual sanity check: print live signal + last committed state. No notifications."""
import json
from pathlib import Path

from main import compute_raw_signal, fmt_alloc, render_components

STATE_FILE = Path(__file__).parent / "last_state.json"

if __name__ == "__main__":
    cur = compute_raw_signal()
    print("Live raw signal (not committed):")
    print(f"  raw_signal: {cur['raw_signal']} (score {cur['score']}/3)")
    print(f"  as of close: {cur['last_close_date']}\n")
    print(render_components(cur["components"]))
    print()
    if not STATE_FILE.exists():
        print("No committed state yet (first run pending).")
    else:
        prev = json.loads(STATE_FILE.read_text())
        deployed = prev["deployed_state"]
        off_alloc = prev.get("off_allocation")
        if deployed == "risk-on":
            target = "100% QQQ"
        elif off_alloc:
            target = fmt_alloc(off_alloc)
        else:
            target = "(off-bucket classification pending next main.py run)"
        print(f"Last committed state ({prev.get('asof')}):")
        print(f"  deployed_state: {deployed}")
        print(f"  target:         {target}")
        print(f"  rolling_buffer: {prev.get('rolling_buffer') or prev.get('buffer')}")
        print(f"  last_close:     {prev['last_close_date']}")
        if deployed == "risk-off" and off_alloc:
            regime = prev.get("off_regime") or {}
            print(f"  classified_at:  {prev.get('off_classified_at')}")
            if regime:
                print(
                    f"  off_regime:     {regime.get('regime')} "
                    f"({regime.get('dollar')} dollar, {regime.get('nfci')} NFCI)"
                )
