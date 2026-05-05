"""Manual sanity check: print current signal state. No notifications."""
from signal_bot import compute, render

if __name__ == "__main__":
    print(render(compute()))
