# Investment Strategy — Full Reference

## Purpose

This document is the complete reference for the household investment strategy
across Roth IRA and taxable accounts. The deployed automation (`SPEC.md`) is a
simplified subset of what's described here. Use this doc to:

- Recover the reasoning behind specific parameters
- Decide whether to upgrade the deployed system to a richer variant
- Onboard anyone (advisor, family member, future-you) into the full picture

## Account architecture

Two account types, two different strategies, because tax treatment fundamentally
changes what works.

### Roth IRA (Schwab) — active strategy

Tax-protected. No capital gains friction on rotations. This is where the active
regime-based strategy runs. Currently deployed as v1.5 (simple manual).
Possible upgrades documented below as v2 and v3.

### Taxable account (Schwab) — passive 50/50

Tax friction kills active strategies. Backtested: the active strategy
underperforms QQQ B&H by ~4 points/yr after-tax due to short-term gain rates
on every rotation. Solution: don't run it here.

Holdings:

- 50% SGOV (or equivalent T-bill ETF)
- 50% QQQ
- Annual rebalance back to 50/50 (or use new contributions to drift toward target)
- Continue first-of-month QQQ contribution regardless of regime signal state

Rationale for holding cash in SGOV not Schwab sweep:

- SGOV currently yields ~3.9% vs sweep ~0.05-0.45%
- Treasury interest is state-tax-exempt
- Effectively zero price risk
- Same-day liquidity for buying

### Cash management

Outside accounts: I-bonds annually if not maxed (10k/person/yr limit,
tax-deferred, federal-only).

If income is high enough to make federal-tax-free yield meaningful
(top brackets), consider muni money market like VMSXX in taxable for cash
allocation. At ~32% federal + state, tax-equivalent yield can beat SGOV.

## The signal (v1.5 deployed)

### Three sub-signals

1. **LQD > 200-day SMA**: investment-grade credit ETF above its long-term trend.
   When credit is healthy, equity risk is rewarded.
2. **MOVE < 200-day SMA**: rate volatility below long-term trend. Rate
   uncertainty often precedes equity stress.
3. **NFCI_credit < 26-week SMA**: Chicago Fed credit conditions sub-index
   below its medium-term trend. Composite measure of bank lending stress.

raw_signal = risk-on if at least 2 of 3 are true, else risk-off.

### Hysteresis (asymmetric)

- Risk-on → risk-off: act on first day of negative signal.
- Risk-off → risk-on: require 3 consecutive days of positive signal.

Rationale: stress regimes are asymmetric. They start fast and have false-bottom
recoveries. Quick to defense + slow to offense filters out head-fakes without
giving up bear-market protection.

### Why these three signals

Tested ~80 alternatives. The winning trio works because each signal captures
a different stress mechanism:

- **LQD** captures BOTH credit AND duration risk (tested vs. pure credit
  spreads like AAA10Y/BAA10Y, which only capture credit and miss rate-driven
  stress like 2022).
- **MOVE** captures rate volatility regime change before it hits equities.
- **NFCI_credit** is a Fed-published composite covering bank lending and
  funding markets. Caught 2025 stress that LQD missed.

Combinations tested and rejected:

- Single signal (LQD only): more whipsaws, no information advantage
- LQD + MOVE only: misses 2025-style soft regime
- LQD + Moody's BAA-10Y: BAA spread is too slow, missed 2022 by 7 months
- Adding FXY as 4th signal: degrades performance, FXY signal is too noisy
- Various OAS series: real but FRED restricts daily access to 3-year window

### Why 2-of-3 voting (not 3-of-3 or 1-of-3)

3-of-3 (all must agree): too defensive, too few risk-on days, misses recoveries.
1-of-3 (any can trigger risk-on): too permissive, defensive value collapses.
2-of-3: best Sharpe in backtest (1.44 in simple QQQ-or-SHV variant).

## The allocations (v1.5 deployed)

### Risk-on

100% QQQ.

Possible upgrades (v2 below) replace this with vol-targeted leverage, but
deployed v1.5 is plain QQQ.

### Risk-off

- 30% XLU (Utilities Select Sector SPDR)
- 40% GLD (gold)
- 30% UUP (US Dollar bullish)

Why XLU added to former 60/40 GLD/UUP baseline:

- Pure GLD/UUP gives up too much equity exposure when regime filter is wrong
- XLU has highest defensive characteristics among equity sectors:
  - Beta ~0.5 to QQQ
  - Annualized return in QQQ stress regimes: -19% (vs QQQ -44%)
  - 3-4% dividend yield
- Adding 30% XLU improved Sharpe from 1.38 to 1.50 in backtest, drawdown
  unchanged at -15%
- Wins 4 of 5 sub-period analyses (only loses to baseline in 2020 COVID
  V-shape recovery)

Why not financials despite intuitive case:

- Tested XLF, KIE (insurance), KRE (regional banks), KBE, IAI
- All lose more than utilities in stress
- KIE is the closest to defensive but still -38% annualized in QQQ stress
  (vs XLU's -19%)
- Insurance was positive in 2022 specifically due to rate-rise benefiting
  bond portfolios, but this is a single regime, not a structural property

Why not all-defensive sectors (XLU + XLP + XLV mixed):

- Equal-weight mix of defensives slightly underperforms XLU alone
- Diversification across defensive sectors doesn't add much because they
  share the equity beta they're trying to dampen

## Execution mechanics

### Order types

Limit orders only. No market orders.

- Buys: bid + 1¢
- Sells: ask - 1¢
- Mid-day execution (10:30am-3pm ET) for tightest spreads
- Avoid first 5-10 min of trading and last 30 min

### Order sequencing

- Going risk-off: sell QQQ first, then buy XLU/GLD/UUP simultaneously
- Going risk-on: sell defensives first, then buy QQQ
- Round to whole shares, accept ±0.5% drift

### Cash buffer

Maintain $500-1000 in SWVXX in Roth for rotation lubrication.

### Trade journal

Required. Sheet with columns: date, signal score, action, prices,
emotional state, deviations from spec. Audit quarterly. The emotional
state column is the operational equivalent of pre-mortem documentation.

### Settlement awareness (T+1 since May 2024)

- Same-session ETF rotation is fine
- Don't execute reversal within 2 business days of original (hysteresis
  layer prevents this in normal operation)

### Disaster recovery

- Phone broker line: 1-800-435-4000
- Trading authorization on file for backup executor
- If you miss a signal day, do not catch up late — wait for next signal

### First-of-month contributions

Independent of regime signal. Always buy QQQ on the 1st (or first trading
day after). Don't conflate rotation trades with new-money deployment.

## Performance benchmarking

Don't compare to QQQ. Wrong benchmark — strategy gives up CAGR for
risk-adjusted return, you'll abandon it.

Compare to:

- 60/40 SPY/AGG portfolio (proper diversified benchmark)
- Target-date fund equivalent (e.g., FFFGX 2050)

Track quarterly. Annual review on January 1. Do not modify rules mid-position
during a losing stretch.

## v2: Vol-targeted leverage (not deployed, available)

If/when willing to commit to daily monitoring and more aggressive position
sizing, the on-leg becomes a vol-targeted blend:

- Compute realized 20-day vol of QQQ daily
- Target 15% annualized portfolio vol
- desired_leverage = clip(15 / realized_vol, 1.0, 3.0)
- Position = (desired_leverage - 1) / 2 in TQQQ + remainder in QQQ

Rationale: scales position to risk environment. In calm regimes (vol < 15%)
takes leverage. In normal regimes (vol = 15-30%) sits at 1x QQQ. In
stressed regimes (vol > 30%) reduces below 1x — though regime filter
would have flipped to off-bucket already.

Backtested impact: Sharpe ~1.36, CAGR ~24%, MaxDD ~-21%.

Not deployed because:

- Requires daily attention (vs. weekly for v1.5)
- TQQQ has decay properties most retail investors misunderstand
- Manual execution adds slippage that the backtest doesn't model

## v3: RSI(2) volatility overlay (not deployed)

Mean-reversion overlay on top of v2:

- Compute RSI(2) of QQQ daily
- When RSI(2) > 95 AND regime is risk-on:
  allocate 25% to VIXY for 5 trading days, reduce on-leg to 75%
- After 5 days: revert to standard allocation

Captures the empirical pattern that very-high RSI(2) readings often precede
short-term mean reversion. The VIXY position monetizes the volatility
expansion if reversion materializes.

Backtested impact: marginal Sharpe improvement (+0.02), but operationally
expensive (~5 events/year, 5-day positions, requires daily monitoring).

Not deployed because the marginal benefit doesn't justify the operational
load for manual execution.

## v4: Taxable hedge overlay (not deployed)

If/when QQQ position in taxable becomes large enough to warrant active
hedging (>$500k or so), consider put-spread overlay:

- Hold QQQ core permanently, never sell
- During risk-off regime, buy QQQ put spreads
  - Long: 5% OTM, 60 DTE
  - Short: 15% OTM, 60 DTE
  - Notional: 25-100% of QQQ position depending on conviction
- Roll at 30 DTE remaining
- Close on regime flip back to risk-on

Backtested with realistic IV skew + MOVE bump assumptions:

- 25% notional sizing: marginal improvement, basically tied with B&H on Sharpe
- 100% spread sizing: improves Sharpe by 0.02-0.04, reduces MaxDD by 3-5 points
- Naked puts at 5-10% OTM: dramatic 2020-style payoffs, big 2018-style drag

Not deployed because:

- Active hedging is psychologically hard to execute consistently
- Premium drag in calm years (1-2% / yr) is real and constant
- Most of the Sharpe improvement is fragile to options pricing assumptions

## Things tested and rejected (don't re-litigate)

- **PFIX permanent or tactical**: 5y of data dominated by rate-shock regime,
  out-of-sample expectation much worse, decay risk in calm regimes severe.
- **IVOL satellite**: returns -5% CAGR standalone over its lifetime, broken
  by design.
- **TBF tactical on MOVE acceleration**: 50% win rate, no edge, wash on Sharpe.
- **EUM tactical short on deep risk-off**: works mechanically (+54% in QQQ
  DD>10%) but bleeds offset gains in calm regimes. Marginal Sharpe gain.
- **BITI inverse bitcoin**: -40% CAGR standalone, decay too aggressive.
- **FXY as regime input**: degrades all variants tested.
- **Currency baskets short of EUR/JPY/etc.**: retail products don't really
  exist in IRA-eligible form.
- **Buffered ETFs (BJUL/PJUL)**: 2-3% structural drag, only justified for
  someone behaviorally unable to hold equity through drawdowns.
- **All-weather/risk-parity ETFs (RPAR/UPAR/ALLW)**: structurally fragile
  in 2022 (RPAR -22.8%).
- **Symmetric hysteresis (N=2, 3, 5, 10)**: all reduce Sharpe.
- **Offensive-bias hysteresis (slow to defense, quick to offense)**:
  drawdown blows up to -32%.
- **Margin on PFIX or anything else**: combines volatile asset + leverage
  - margin interest + theta decay = asymmetric ruin.
- **Active strategy in taxable account**: tax friction kills the math;
  -4 pts/yr CAGR vs. taxable B&H.
- **Skipping monthly contributions during risk-off**: time-in-market wins for
  periodic contributions; signal misses tops by design and would have you
  buying after recoveries are well underway.

## Reasoning archive: why these decisions

### Why a regime filter at all

QQQ B&H over 2008-2026 had Sharpe 0.94 with -53% max drawdown. Most retail
investors abandon strategies with >30% drawdowns. The regime filter trades
modest CAGR underperformance in bull markets for substantially better
drawdown profile, which improves the probability you actually stick with
the strategy across full cycles.

### Why these specific MA periods (200d, 200d, 26w)

Tested 50d, 100d, 200d, 252d for LQD/MOVE. 200d was robust across
sub-periods without being so slow it missed 2018/2020 transitions. For
NFCI_credit (weekly data), 26-week MA is the equivalent timescale.

### Why XLU specifically vs. USMV or VPU

USMV: too dynamic, ends up concentrated in whatever was recently low-vol
(was XLU-heavy going into 2022, then rotated late).
VPU: similar to XLU but slightly higher expense ratio with no clear
performance advantage.
XLU: clean, liquid, low expense ratio, predictable holdings.

### Why GLD not IAU or GLDM

Functionally identical for our purposes. GLD has highest liquidity. IAU
slightly cheaper expense ratio. Either is acceptable.

### Why UUP not USDU

UUP tracks DXY directly (~58% EUR weight). USDU is a managed product with
discretionary weights. UUP is more predictable.

### Why hysteresis N_on = 3 specifically

Tested 1, 2, 3, 5, 10.

- 1 = current behavior, no benefit
- 2 = small improvement, still gives back to whipsaws
- 3 = sweet spot, 44% fewer trades for 0.01 Sharpe cost
- 5+ = too slow, costs meaningful CAGR in bull markets

## Annual review checklist (every January 1)

Don't modify rules during active losing positions. On Jan 1 each year:

1. Pull last 12 months of trade journal entries
2. Compare strategy returns to:
   - QQQ B&H (sanity check)
   - 60/40 SPY/AGG (real benchmark)
   - Target-date fund (life-cycle benchmark)
3. Count trades. If > 12 in a year, hysteresis tuning may be off.
4. Review emotional-state column for patterns of override pressure
5. Re-read the "Things tested and rejected" list before considering changes
6. If considering changes:
   - Document the proposed change and reasoning
   - Backtest against full history
   - Wait until next January to deploy (annual cadence is the discipline
     that prevents recency-driven tinkering)
7. Update this doc with any deployed changes

## Account targets (long-term)

Roth contributions: max annually ($7,500 in 2026 if under 50, $8,000 if over 50).
Taxable contributions: discretionary, but maintain 50/50 split.
I-bonds: $10k/yr/person if cash flow allows.
Emergency fund: separate from this document, held in HYSA/MMF. Not subject
to any of these rules.

## Operational risk

The single biggest risk to this strategy is not market behavior but
behavioral drift. Mechanical rules + signal-driven notifications + trade
journal are the discipline architecture. If any of these decay, the
strategy decays.

Specifically: the moment you start checking the signal more often than
the deployed cadence, or start reading the daily output to "see how the
strategy is doing," you've started the slide toward overriding it.
The system runs you, not the other way around. That's the design.
