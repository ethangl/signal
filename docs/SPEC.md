# QQQ Regime Signal Bot — v1.8

## What this does

Daily automated check of a market regime signal. Sends a push notification
(via Pushover) only when the deployed state changes, with explicit trade
instructions. Designed for manual execution in a Roth IRA at Schwab.

## Signal logic

Compute three macro sub-signals from latest available daily data:

1. LQD close > 200-day SMA of LQD close
1. ^MOVE close < 200-day SMA of ^MOVE close
1. NFCICREDIT (FRED, weekly) < 26-week SMA of NFCICREDIT

macro_signal = risk-on if at least 2 of 3 are true, else risk-off.

Compute one price-action sub-signal:

- price_filter = QQQ close > 50-day SMA of QQQ close

## Hysteresis (asymmetric with price confirmation)

Maintain a deployed_state separate from macro_signal. State transitions:

**Risk-on → risk-off (immediate):**

- If deployed_state == risk-on and macro_signal == risk-off for any single day:
  flip deployed_state to risk-off immediately.

**Risk-off → risk-on (macro streak AND price confirmation):**

- If deployed_state == risk-off, require BOTH of the following:
  - macro_signal == risk-on for 3 consecutive trading days
  - price_filter == risk-on on the candidate flip day
- When both conditions met, flip deployed_state to risk-on.

In practice: maintain a rolling buffer of the last 3 macro_signal values.
When all 3 are positive AND price_filter is positive on the current day,
flip to risk-on. The risk-off direction does not consult the price filter —
macro deterioration triggers defensive rotation immediately.

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
- Computes macro_signal (2-of-3 voting) and price_filter (QQQ > 50d MA)
- Updates rolling buffer of last 3 macro_signal values
- Determines deployed_state per hysteresis rules
- If deployed_state just flipped to risk-off: classify dollar regime,
  store target allocation in state file
- Stores state in JSON file committed to repo (last_state.json):
  - deployed_state
  - macro_rolling_buffer (last 3 macro_signal values)
  - off_allocation (only meaningful when deployed_state == risk-off)
  - off_classified_at (timestamp of last classification)
- If deployed_state changed: send Pushover notification
- Otherwise exit silently with status logged to stdout

## Notification format

When flipping to risk-off:

```
REGIME CHANGE: risk-off
Macro score 1/3. Dollar regime: [stress|cyclical strong|weak]

Monday 10:30am ET execution:
SELL: 100% QQQ
BUY:  X% XLU + Y% GLD + Z% UUP

Macro components:
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
Macro score 2/3 (or 3/3) confirmed for 3 consecutive days.
Price filter: QQQ [val] vs 50d MA [val] [✓]

Monday 10:30am ET execution:
SELL: current off-bucket allocation
BUY:  100% QQQ

Macro components:
[same as above]
```

## Manual execution rules

When notified of a flip:

1. Wait until next trading day at 10:30am ET
1. Place limit orders, not market orders. bid+1¢ for buys, ask-1¢ for sells.
1. Order sequence:

- Going risk-off: sell QQQ first, then buy XLU/GLD/UUP simultaneously
  using the allocation specified in the notification
- Going risk-on: sell XLU/GLD/UUP first, then buy QQQ

1. Round to whole shares, accept ±0.5% drift from target weights
1. Maintain $500-1000 cash buffer in SWVXX for rotation lubrication
1. Log every trade in trade journal sheet (date, prices, allocation used,
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

Full-period (2010-2026) backtest with v1.8 configuration:

- CAGR: ~19.0%
- Sharpe: ~1.36
- MaxDD: ~-15.1%
- Trades/year: ~4.4
- Out-of-sample (2019-now) Sharpe: ~1.64

Forward expectations should be lower — anticipate Sharpe 1.1-1.2 in live
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

### v1.7 → v1.8

- Added price-action confirmation for risk-on re-entry: QQQ > 50d MA
- Hysteresis N_on reduced from 5 back to 3 (price filter does additional work)
- last_state.json rolling_buffer size returns to 3 entries
- On upgrade: initialize macro_rolling_buffer with current macro_signal
  repeated 3 times. Existing deployed_state preserved unchanged.

## Non-goals (v1.8)

- No automated trading
- No leveraged positions (no TQQQ/vol-targeting)
- No options overlay
- No web UI
- No tax-loss harvesting (Roth, irrelevant)
- No FX/EM short overlays (tested and rejected)
- No PFIX or IVOL satellites (tested and rejected)
- No tech sub-sector momentum (tested, fragile, on shelf)
- No BTC allocation (tested, regime-dependent, on shelf)
- No VIX-based signals (tested, MOVE is the better vol input)

## Possible future additions (documented in STRATEGY.md)

- Vol-targeted leverage layer (QQQ + TQQQ blend)
- RSI(2) > 95 → temporary VIXY allocation
- Tech sub-sector momentum overlay (regime-dependent)
- BTC trend-gated allocation (5-10% of risk-on)
- Conviction-based hysteresis (z-score-driven N_on)
