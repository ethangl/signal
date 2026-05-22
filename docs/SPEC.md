# QQQ Regime Signal Bot — v1.9

## What this does
Daily automated check of a market regime signal. Sends a push notification 
(via Pushover) when the deployed state changes OR when macro depth changes 
during an active risk-off period. Designed for manual execution in a Roth 
IRA at Schwab.

## Signal logic

Compute three macro sub-signals from latest available daily data:
1. LQD close > 200-day SMA of LQD close
2. ^MOVE close < 200-day SMA of ^MOVE close
3. NFCICREDIT (FRED, weekly) < 26-week SMA of NFCICREDIT

macro_score = count of true sub-signals (0, 1, 2, or 3).
macro_signal = risk-on if macro_score >= 2, else risk-off.

Compute one price-action sub-signal:
- price_filter = QQQ close > 50-day SMA of QQQ close

## Hysteresis (asymmetric with price confirmation)

Maintain a deployed_state separate from macro_signal. State transitions:

**Risk-on → risk-off (immediate):**
- If deployed_state == risk-on and macro_signal == risk-off for any single day:
  flip deployed_state to risk-off immediately. Classify depth and set 
  current_allocation per Risk-off allocation table.

**Risk-off → risk-on (macro streak AND price confirmation):**
- If deployed_state == risk-off, require BOTH of the following:
  - macro_signal == risk-on for 3 consecutive trading days
  - price_filter == risk-on on the candidate flip day
- When both conditions met, flip deployed_state to risk-on.

## Risk-on allocation

100% QQQ.

## Risk-off allocation (depth-aware)

At the moment deployed_state flips to risk-off, classify depth:
- depth = 0 if macro_score == 0 (deep stress)
- depth = 1 if macro_score == 1 (mild stress)

Allocate per depth:

| Depth | Description | Allocation |
|-------|-------------|-----------|
| 0 | Deep stress (macro_score == 0) | 10% XLU + 55% GLD + 35% UUP |
| 1 | Mild stress (macro_score == 1) | 30% XLU + 45% GLD + 25% UUP |

## Mid-risk-off depth reclassification (new in v1.9)

While deployed_state == risk-off, monitor macro_score daily:
- If current_depth == 1 and macro_score == 0: set current_depth = 0, 
  rotate to deep-stress allocation
- If current_depth == 0 and macro_score == 1: set current_depth = 1,
  rotate to mild-stress allocation
- If macro_score >= 2: do not change current_depth (depth only flips on
  the 0/1 boundary). Risk-on confirmation handled separately by main 
  state transition logic.

Reclassification is immediate (no streak required). Notification sent on 
depth change with explicit rebalance instructions.

When deployed_state next flips to risk-on, current_depth and 
current_allocation become irrelevant. Next risk-off event classifies 
fresh.

## Execution

- Script runs every trading day at 4:30pm ET via GitHub Actions cron
- Pulls QQQ, LQD, ^MOVE closes from yfinance
- Pulls NFCICREDIT from FRED API
- Computes macro_score and price_filter
- Updates rolling buffer of last 3 macro_signal values (for risk-on confirmation)
- Determines deployed_state per hysteresis rules
- If deployed_state flipped to risk-off: classify depth, set current_allocation
- If deployed_state == risk-off and macro_score crossed the 0/1 boundary:
  update current_depth and current_allocation
- Stores state in JSON file committed to repo (last_state.json):
  - deployed_state
  - macro_rolling_buffer (last 3 macro_signal values)
  - current_depth (only meaningful when deployed_state == risk-off)
  - current_allocation (the active XLU/GLD/UUP weights)
  - last_classified_at (timestamp of last depth classification)
- If deployed_state changed OR depth changed: send Pushover notification
- Otherwise exit silently with status logged to stdout

## Notification formats

When flipping to risk-off:

```
REGIME CHANGE: risk-off
Macro score [0|1]/3 — [deep stress|mild stress]

Monday 10:30am ET execution:
SELL: 100% QQQ
BUY:  X% XLU + Y% GLD + Z% UUP

Macro components:
LQD:     [val] vs 200d MA [val]    [✓|✗]
MOVE:    [val] vs 200d MA [val]    [✓|✗]
NFCI_cr: [val] vs 26w MA [val]     [✓|✗]
```

When mid-risk-off depth deepens (score 1 → 0):

```
DEPTH CHANGE: stress deepening to score 0/3
Allocation rotating to deep-stress weights

Monday 10:30am ET execution (rebalance within risk-off):
SELL: 20% XLU + 0% GLD + 0% UUP
BUY:  0% XLU + 10% GLD + 10% UUP
TARGET: 10% XLU + 55% GLD + 35% UUP

Macro components:
[same as above]
```

When mid-risk-off depth improves (score 0 → 1):

```
DEPTH CHANGE: stress easing to score 1/3
Allocation rotating to mild-stress weights

Monday 10:30am ET execution (rebalance within risk-off):
SELL: 0% XLU + 10% GLD + 10% UUP
BUY:  20% XLU + 0% GLD + 0% UUP
TARGET: 30% XLU + 45% GLD + 25% UUP

Macro components:
[same as above]
```

When flipping to risk-on:

```
REGIME CHANGE: risk-on
Macro score 2/3 (or 3/3) confirmed for 3 consecutive days.
Price filter: QQQ [val] vs 50d MA [val] [✓]

Monday 10:30am ET execution:
SELL: current off-bucket allocation
BUY:  100% QQQ
```

## Manual execution rules

When notified of any state or depth change:
1. Wait until next trading day at 10:30am ET
2. Place limit orders, not market orders. bid+1¢ for buys, ask-1¢ for sells.
3. Order sequence:
   - Going risk-off: sell QQQ first, then buy XLU/GLD/UUP simultaneously
   - Depth change: execute sells and buys simultaneously (small rebalance)
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
- Active risk-off positions held under v1.8 spec at deployment time of 
  v1.9 are NOT immediately rebalanced. v1.9 logic applies from next state 
  transition or depth change.

## Secrets needed

- FRED_API_KEY
- PUSHOVER_USER_KEY  
- PUSHOVER_API_TOKEN

## Data sources

- yfinance: QQQ, LQD, ^MOVE, XLU, GLD, UUP closes
- FRED API:
  - NFCICREDIT (weekly, 5-day publication lag)

NOTE: DTWEXBGS and NFCI (non-credit) are no longer needed. v1.9 removes 
the dollar regime classification that depended on them.

## Files

- main.py — daily signal computation and notification
- dashboard.py — ad-hoc state printer (no notifications)
- last_state.json — committed state file
- .github/workflows/cron.yml — daily schedule
- README.md — deployment instructions
- SPEC.md — this file (the source of truth)
- STRATEGY.md — human reference with reasoning and rejected ideas

## Backtest reference

Full-period (2010-2026) backtest with v1.9 configuration:
- CAGR: ~19.4%
- Sharpe: ~1.39
- MaxDD: ~-12.9%
- Out-of-sample (2019-now) Sharpe: ~1.70
- Out-of-sample (2019-now) MaxDD: ~-12.9%

Forward expectations should be lower — anticipate Sharpe 1.1-1.3 in live 
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
- Hysteresis N_on reduced from 5 back to 3
- last_state.json rolling_buffer size returns to 3 entries

### v1.8 → v1.9
- REMOVED: dollar regime classification (DTWEXBGS, NFCI no longer needed)
- ADDED: depth-aware off-bucket allocation (based on macro_score 0 vs 1)
- ADDED: mid-risk-off depth reclassification with immediate rotation
- last_state.json schema changes:
  - REMOVED: off_allocation field (now derived from current_depth)
  - REMOVED: off_classified_at (replaced by last_classified_at)
  - ADDED: current_depth (integer 0 or 1, null when risk-on)
  - ADDED: current_allocation (object with xlu/gld/uup weights, null when risk-on)
  - ADDED: last_classified_at (timestamp of last depth set/change)
- Notification system handles new "depth change" event type
- On upgrade: existing v1.8 active risk-off positions are NOT rebalanced.
  Initialize current_depth from current macro_score on first cron run after
  upgrade. If currently risk-off, current_allocation field set from v1.8 
  values to avoid spurious depth-change notification on first run.

## Non-goals (v1.9)

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
- No dollar regime classification (tested, removed in v1.9 as redundant 
  with macro depth)

## Possible future additions (documented in STRATEGY.md)

- Vol-targeted leverage layer (QQQ + TQQQ blend)
- RSI(2) > 95 → temporary VIXY allocation
- Tech sub-sector momentum overlay (regime-dependent)
- BTC trend-gated allocation (5-10% of risk-on)
- Conviction-based hysteresis (z-score-driven N_on)
- Score-3 sub-strategy (highest-conviction risk-on with possible leverage)
