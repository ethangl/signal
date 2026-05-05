# QQQ Regime Signal Bot

## What this does

Weekly automated check of a market regime signal. Sends a push notification
(via Pushover) only when the signal changes, with explicit trade instructions.

## Signal logic

Risk-on if at least 2 of these 3 conditions are true:

1. LQD close > 200-day SMA of LQD close
2. ^MOVE close < 200-day SMA of ^MOVE close
3. NFCICREDIT (FRED, weekly) < 26-week SMA of NFCICREDIT

When risk-on: target = 100% QQQ
When risk-off: target = 60% GLD / 40% UUP

## Execution

- Runs Friday 4:30pm ET via GitHub Actions cron
- Pulls LQD, MOVE prices from yfinance
- Pulls NFCICREDIT from FRED API (key in repo secret FRED_API_KEY)
- Stores last known state in a JSON file committed to repo
- Compares current signal to last state
- If different: sends Pushover notification with explicit instructions
- If same: exits silently
- Always prints state to stdout so the action log is reviewable

## Notification format

"REGIME CHANGE: [risk-on/risk-off]. Score [X/3].
Monday 10:30am ET: SELL [current], BUY [target].
LQD: [val] vs MA [val] [✓/✗]
MOVE: [val] vs MA [val] [✓/✗]  
NFCI_cr: [val] vs MA [val] [✓/✗]"

## Secrets needed

- FRED_API_KEY
- PUSHOVER_USER_KEY
- PUSHOVER_API_TOKEN

## Manual dashboard

Separate script `dashboard.py` that prints current state regardless of change.
Used for weekly sanity check. No notifications.

## Non-goals

- No automated trading (manual execution at Schwab)
- No leverage layer (skipping vol-targeting and RSI overlay for v1)
- No web UI
- Build it simple, < 200 lines total
