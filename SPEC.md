# QQQ Regime Signal Bot — v1.5

## What this does

Weekly automated check of a market regime signal. Sends a push notification
(via Pushover) only when the signal changes, with explicit trade instructions.
Designed for manual execution in a Roth IRA at Schwab.

## Signal logic

Compute three sub-signals from Friday EOD data:

1. LQD close > 200-day SMA of LQD close
2. ^MOVE close < 200-day SMA of ^MOVE close
3. NFCICREDIT (FRED, weekly) < 26-week SMA of NFCICREDIT

raw_signal = risk-on if at least 2 of 3 are true, else risk-off.

## Hysteresis (asymmetric)

Maintain a deployed_state separate from raw_signal.

- If raw_signal == risk-off and deployed_state == risk-on:
  flip deployed_state to risk-off immediately.
- If raw_signal == risk-on and deployed_state == risk-off:
  require 3 consecutive trading days of raw_signal == risk-on before flipping.

In practice: track a rolling buffer of the last 3 raw_signal values. The
deployed_state flips to risk-on only when all 3 are risk-on. The state flips
to risk-off whenever the most recent raw_signal is risk-off.

## Allocations

deployed_state == risk-on:

- 100% QQQ

deployed_state == risk-off:

- 30% XLU
- 40% GLD
- 30% UUP

## Execution

- Script runs every trading day at 4:30pm ET via GitHub Actions cron
- Pulls LQD, MOVE, QQQ closes from yfinance
- Pulls NFCICREDIT from FRED API (key in repo secret FRED_API_KEY)
- Computes raw_signal
- Updates rolling buffer of last 3 raw_signal values
- Determines deployed_state per hysteresis rules
- Stores state in JSON file committed to repo (last_state.json)
- If deployed_state changed from prior commit: send Pushover notification
- If unchanged: exit silently with status logged to stdout
- A separate dashboard.py script prints current state for ad-hoc checking
  without sending notifications

## Notification format

Subject: REGIME CHANGE: [risk-on|risk-off]

Body:
"Signal flipped to [risk-on|risk-off]. Score [X/3].
Monday 10:30am ET execution:
SELL: [current allocation as % targets]
BUY: [target allocation as % targets]

Components:
LQD: [val] vs 200d MA [val] [✓|✗]
MOVE: [val] vs 200d MA [val] [✓|✗]
NFCI_cr: [val] vs 26w MA [val] [✓|✗]

Hysteresis buffer: [last 3 raw_signal values, oldest first]"

## Manual execution rules

When notified of a flip:

1. Wait until Monday 10:30am ET (or next trading day at 10:30am if Monday is a holiday)
2. Place limit orders, not market orders. Use bid+1¢ for buys, ask-1¢ for sells.
3. Order sequence:
   - Going risk-off: sell QQQ first, then buy XLU, GLD, UUP simultaneously
   - Going risk-on: sell XLU, GLD, UUP first, then buy QQQ
4. Round to whole shares, accept ±0.5% drift from target weights
5. Maintain $500-1000 cash buffer in SWVXX for rotation lubrication
6. Log every trade in the trade journal sheet (date, prices, emotional state,
   reason for any deviation from spec)

## Independent rules

- First-of-month QQQ contribution buy continues regardless of signal state.
  This is a separate dollar-cost-averaging program for new capital, not
  governed by the regime signal.
- Do not execute "reversal" trades within 2 business days of the original
  rotation. The hysteresis layer (N=3 for return to risk-on) prevents this
  in normal operation but worth a sanity check.
- Annual review of the spec on Jan 1. Do not modify rules during a position
  the strategy is actively losing on.

## Secrets needed

- FRED_API_KEY
- PUSHOVER_USER_KEY
- PUSHOVER_API_TOKEN

## Files

- main.py — daily signal computation and notification
- dashboard.py — ad-hoc state printer (no notifications)
- last_state.json — committed state file
- .github/workflows/cron.yml — daily schedule
- README.md — deployment instructions
- SPEC.md — this file (the source of truth)

## Non-goals (v1.5)

- No automated trading
- No leveraged positions (no TQQQ/vol-targeting)
- No options overlay
- No web UI
- No tax-loss harvesting (Roth, irrelevant)
- No FX/EM short overlays (tested and rejected)
- No PFIX or IVOL satellites (tested and rejected)

## Possible v2 additions (not for now)

- Vol-targeted leverage layer (QQQ + TQQQ blend, target 15% portfolio vol)
- RSI(2) > 95 → temporary VIXY allocation
- Monthly performance summary email vs. 60/40 SPY/AGG benchmark

## Backtest reference

Full-period (2008-2026) backtest stats with this configuration:

- CAGR: ~19%
- Sharpe: ~1.28
- MaxDD: ~-22%
- Trades/yr: ~5.1

Forward expectations should be lower — anticipate Sharpe 1.0-1.1 in live
trading after slippage, with 1-2 year stretches of underperformance vs.
QQQ B&H during strong bull markets.
