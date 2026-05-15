# QQQ Regime Signal Bot — v1.7

## What this does

Daily automated check of a market regime signal. Sends a push notification
(via Pushover) only when the deployed state changes, with explicit trade
instructions. Designed for manual execution in a Roth IRA at Schwab.

## Signal logic

Compute three sub-signals from latest available daily data:

1. LQD close > 200-day SMA of LQD close
2. ^MOVE close < 200-day SMA of ^MOVE close
3. NFCICREDIT (FRED, weekly) < 26-week SMA of NFCICREDIT

raw_signal = risk-on if at least 2 of 3 are true, else risk-off.

## Hysteresis (asymmetric)

Maintain a deployed_state separate from raw_signal:

- If raw_signal == risk-off and deployed_state == risk-on:
  flip deployed_state to risk-off immediately.
- If raw_signal == risk-on and deployed_state == risk-off:
  require 5 consecutive trading days of raw_signal == risk-on before flipping.

In practice: track a rolling buffer of the last 5 raw_signal values. The
deployed_state flips to risk-on only when all 5 are risk-on. The state flips
to risk-off whenever the most recent raw_signal is risk-off.

## Risk-on allocation

100% QQQ.

## Risk-off allocation (dollar regime sub-classification)

At the moment deployed_state flips from risk-on to risk-off, classify the
dollar regime once and hold the corresponding allocation throughout the
entire risk-off period. Do NOT reweight if dollar regime changes mid-period.

Dollar regime classification (computed at flip):

- dollar_strong = DTWEXBGS close (yesterday) > 200-day SMA of DTWEXBGS close
- nfci_tight = NFCI (latest weekly value, 5d lag) > 0

Allocation by regime:

| Dollar | NFCI  | Regime          | Allocation                  |
| ------ | ----- | --------------- | --------------------------- |
| Strong | Tight | Stress          | 10% XLU + 30% GLD + 60% UUP |
| Strong | Loose | Cyclical strong | 30% XLU + 40% GLD + 30% UUP |
| Weak   | (any) | Weak            | 30% XLU + 50% GLD + 20% UUP |

The classification is logged in the notification so you know which allocation
applies. When deployed_state next flips back to risk-on, the classification
becomes irrelevant. Next risk-off event classifies fresh.

## Execution

- Script runs every trading day at 4:30pm ET via GitHub Actions cron
- Pulls QQQ, LQD, ^MOVE closes from yfinance
- Pulls NFCICREDIT, NFCI, DTWEXBGS from FRED API
- Computes raw_signal
- Updates rolling buffer of last 5 raw_signal values for hysteresis
- Determines deployed_state per hysteresis rules
- If deployed_state just flipped to risk-off: classify dollar regime,
  store target allocation in state file
- Stores state in JSON file committed to repo (last_state.json):
  - deployed_state
  - rolling_buffer (last 5 raw_signal values)
  - off_allocation (only meaningful when deployed_state == risk-off)
  - off_classified_at (timestamp of last classification)
- If deployed_state changed: send Pushover notification
- Otherwise exit silently with status logged to stdout

## Notification format

When flipping to risk-off:

```
REGIME CHANGE: risk-off
Score 1/3. Dollar regime: [stress|cyclical strong|weak]

Monday 10:30am ET execution:
SELL: 100% QQQ
BUY:  X% XLU + Y% GLD + Z% UUP

Components:
LQD:     [val] vs 200d MA [val]    [✓|✗]
MOVE:    [val] vs 200d MA [val]    [✓|✗]
NFCI_cr: [val] vs 26w MA [val]     [✓|✗]

Dollar regime context:
DTWEXBGS: [val] vs 200d MA [val]   [strong|weak]
NFCI:     [val]                     [tight|loose]
```

When flipping to risk-on:

```
REGIME CHANGE: risk-on
Score 2/3 (or 3/3) confirmed for 5 consecutive days.

Monday 10:30am ET execution:
SELL: current off-bucket allocation
BUY:  100% QQQ

Components:
[same as above]
```

## Manual execution rules

When notified of a flip:

1. Wait until next trading day at 10:30am ET
2. Place limit orders, not market orders. bid+1¢ for buys, ask-1¢ for sells.
3. Order sequence:
   - Going risk-off: sell QQQ first, then buy XLU/GLD/UUP simultaneously
     using the allocation specified in the notification
   - Going risk-on: sell XLU/GLD/UUP first, then buy QQQ
4. Round to whole shares, accept ±0.5% drift from target weights
5. Maintain $500-1000 cash buffer in SWVXX for rotation lubrication
6. Log every trade in trade journal sheet (date, prices, allocation used,
   emotional state, deviations from spec)

## Independent rules

- First-of-month QQQ contribution buy continues regardless of signal state
- Do not execute reversal trades within 2 business days of the original
- Annual review of spec on January 1; do not modify rules during an active
  losing position

## Secrets needed

- FRED_API_KEY
- PUSHOVER_USER_KEY
- PUSHOVER_API_TOKEN

## Data sources

- yfinance: QQQ, LQD, ^MOVE, XLU, GLD, UUP closes
- FRED API:
  - NFCICREDIT (weekly, 5-day publication lag)
  - NFCI (weekly, 5-day publication lag)
  - DTWEXBGS (daily, broad trade-weighted dollar)

## Files

- main.py — daily signal computation and notification
- dashboard.py — ad-hoc state printer (no notifications)
- last_state.json — committed state file
- .github/workflows/cron.yml — daily schedule
- README.md — deployment instructions
- SPEC.md — this file (the source of truth)
- STRATEGY.md — human reference with reasoning and rejected ideas

## Backtest reference

Full-period (2008-2026) backtest with v1.7 configuration:

- CAGR: ~17.5%
- Sharpe: ~1.26
- MaxDD: ~-16.5%

Forward expectations should be lower — anticipate Sharpe 1.0-1.1 in live
trading after slippage, with 1-2 year stretches of underperformance vs.
QQQ B&H during strong bull markets.

## Migration notes (between versions)

### v1.0 → v1.5

- Off-bucket: 60/40 GLD/UUP → 30% XLU + 40% GLD + 30% UUP
- Added hysteresis (N_off=1, N_on=3)
- Daily run cadence (was weekly)

### v1.5 → v1.6

- Added dollar regime sub-classification at risk-off flip
- last_state.json schema adds: off_allocation, off_classified_at
- New required FRED series: DTWEXBGS

### v1.6 → v1.7

- Hysteresis N_on changed from 3 to 5
- last_state.json rolling_buffer size grows from 3 to 5 entries
- On upgrade: initialize rolling_buffer with current raw_signal repeated 5 times

## Non-goals (v1.7)

- No automated trading
- No leveraged positions (no TQQQ/vol-targeting)
- No options overlay
- No web UI
- No tax-loss harvesting (Roth, irrelevant)
- No FX/EM short overlays (tested and rejected)
- No PFIX or IVOL satellites (tested and rejected)
- No tech sub-sector momentum (tested, fragile, on shelf)
- No BTC allocation (tested, regime-dependent, on shelf)

## Possible future additions (documented in STRATEGY.md)

- Vol-targeted leverage layer (QQQ + TQQQ blend)
- RSI(2) > 95 → temporary VIXY allocation
- Tech sub-sector momentum overlay (regime-dependent)
- BTC trend-gated allocation (5-10% of risk-on)
- Conviction-based hysteresis (z-score-driven N_on)
