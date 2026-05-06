"""Manual sanity check: print live signal + last committed state. No notifications."""
import json
from pathlib import Path

from main import ALLOC, compute, render_components

STATE_FILE = Path(__file__).parent / "last_state.json"

if __name__ == "__main__":
    cur = compute()
    print("Live raw signal (not committed):")
    print(f"  raw_signal: {cur['raw_signal']} (score {cur['score']}/3)")
    print(f"  as of close: {cur['last_close_date']}\n")
    print(render_components(cur["components"]))
    print()
    if STATE_FILE.exists():
        prev = json.loads(STATE_FILE.read_text())
        print(f"Last committed state ({prev.get('asof')}):")
        print(f"  deployed_state: {prev['deployed_state']}")
        print(f"  target:         {ALLOC[prev['deployed_state']]}")
        print(f"  buffer:         {prev['buffer']}")
        print(f"  last_close:     {prev['last_close_date']}")
    else:
        print("No committed state yet (first run pending).")
