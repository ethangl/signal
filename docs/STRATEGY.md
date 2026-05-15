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
regime-based strategy runs. Currently deployed as v1.7.

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

## The signal (v1.7 deployed)

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
- Risk-off → risk-on: require 5 consecutive days of positive signal.

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
- Adding HYG/LQD divergence as 4th signal: hurts performance, including in
  2018 (the year the thesis specifically predicts should benefit)
- Various OAS series: real but FRED restricts daily access to 3-year window

### Why 2-of-3 voting (not 3-of-3 or 1-of-3)

3-of-3 (all must agree): too defensive, too few risk-on days, misses recoveries.
1-of-3 (any can trigger risk-on): too permissive, defensive value collapses.
2-of-3: best Sharpe in backtest.

## The allocations (v1.7 deployed)

### Risk-on

100% QQQ.

Possible upgrades (on-shelf variants below) replace this with vol-targeted
leverage, but deployed v1.7 is plain QQQ.

### Risk-off (dollar-regime-aware)

At the moment of risk-on → risk-off flip, classify the dollar regime once:

| Dollar | NFCI  | Regime                | Allocation                  |
| ------ | ----- | --------------------- | --------------------------- |
| Strong | Tight | Stress (5% of days)   | 10% XLU + 30% GLD + 60% UUP |
| Strong | Loose | Cyclical strong (50%) | 30% XLU + 40% GLD + 30% UUP |
| Weak   | (any) | Weak (45%)            | 30% XLU + 50% GLD + 20% UUP |

Weights frozen for the duration of the risk-off period. Next event classifies
fresh.

Why XLU added to former 60/40 GLD/UUP baseline:

- Pure GLD/UUP gives up too much equity exposure when regime filter is wrong
- XLU has highest defensive characteristics among equity sectors:
  - Beta ~0.5 to QQQ
  - Annualized return in QQQ stress regimes: -19% (vs QQQ -44%)
  - 3-4% dividend yield
- Adding 30% XLU improved Sharpe from 1.38 to 1.50 in initial backtest

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

Why dollar-regime-aware off-bucket sizing:

- In stress regimes (dollar strong + NFCI tight), UUP outperforms by ~22% annualized
- Loading UUP to 60% in those rare regimes captures flight-to-quality flow
- Reduces MaxDD from -22% to -17% with same CAGR
- Only ~5% of days are stress regime, so sample is small — variance on
  forward outcome is wide

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

Required. Sheet with columns: date, signal score, allocation deployed,
action, prices, emotional state, deviations from spec. Audit quarterly.

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

## On-shelf variants (not deployed, real but conditional)

These backtest well but require either operational commitment, regime
conditions that may not persist, or both. Documented for future review.

### Vol-targeted leverage

Replace the on-leg 100% QQQ with vol-targeted blend:

- Compute realized 20-day vol of QQQ daily
- Target 15% annualized portfolio vol
- desired_leverage = clip(15 / realized_vol, 1.0, 3.0)
- Position = (desired_leverage - 1) / 2 in TQQQ + remainder in QQQ

Backtested impact: Sharpe ~1.36, CAGR ~24%, MaxDD ~-21%.

Not deployed because:

- Requires daily attention
- TQQQ has decay properties most retail investors misunderstand
- Manual execution adds slippage that the backtest doesn't model

### RSI(2) volatility overlay

Mean-reversion overlay on top of vol-targeted leverage:

- When RSI(2) of QQQ > 95 AND regime is risk-on:
  allocate 25% to VIXY for 5 trading days, reduce on-leg to 75%

Backtested impact: marginal Sharpe improvement (+0.02). Not worth operational
load for manual execution.

### Tech sub-sector momentum

70% QQQ + 30% momentum-picked from {SMH, IGV, CIBR, ARKK}, 6-month lookback:

- CAGR ~26%, Sharpe ~1.60 over 2015-2026 window

Not deployed because:

- Window heavily biased toward AI/semis era continuing
- If semis underperform next decade, the overlay is pure drag
- Operational complexity (rebalance between 5 ETFs monthly)

If you want some of the benefit with less fragility: 5-10% trend-gated
allocation, smaller commitment.

### BTC trend-gated allocation

5-15% BTC during risk-on AND when BTC > 200d MA, else redirected to QQQ:

- Full-window (2014-2026): +0.4 Sharpe improvement, but heavily flattered by
  2014-2021 BTC rocket-ship
- Post-2022 only: +0.10 Sharpe improvement, marginal

Not deployed because:

- Most of the historical edge came from a one-time asset class re-rating
- Forward expected return contribution is smaller
- 2025 has been a weak BTC year, demonstrating the overlay can hurt

### Conviction-based hysteresis

Z-score the gap between each sub-signal and its threshold. Higher conviction
= faster action; lower conviction = slower:

- Ties with fixed N=5 on Sharpe
- Marginally better in fast regime transitions, worse in chop
- Not deployed because fixed N=5 is empirically dominant and simpler

### Taxable hedge overlay (put spreads)

If/when QQQ position in taxable becomes large enough to warrant active
hedging, consider put-spread overlay during risk-off regimes:

- Long 5% OTM, short 15% OTM, 60 DTE
- Sized at 25-100% of QQQ notional
- Roll at 30 DTE remaining

Backtested with realistic IV skew + MOVE bump: marginal Sharpe improvement,
reduces MaxDD by 3-5 points at 100% notional. Active hedging is psychologically
hard to execute consistently; premium drag in calm years (1-2%/yr) is real.

## Tested and rejected (don't re-litigate)

- **PFIX permanent or tactical**: 5y of data dominated by rate-shock regime,
  out-of-sample expectation much worse, decay risk in calm regimes severe.
- **IVOL satellite**: returns -5% CAGR standalone over its lifetime, broken.
- **TBF tactical on MOVE acceleration**: 50% win rate, no edge.
- **EUM tactical short on deep risk-off**: marginal Sharpe, decay too aggressive.
- **BITI inverse bitcoin**: -40% CAGR standalone, decay catastrophic.
- **FXY as regime input**: degrades all variants tested.
- **HYG/LQD divergence as 4th signal**: hurts performance, including in 2018
  when McClellan-style thesis specifically predicts it should help.
- **Currency baskets short of EUR/JPY/etc.**: retail products don't exist
  in IRA-eligible form.
- **Buffered ETFs (BJUL/PJUL)**: 2-3% structural drag, only for behavioral
  reasons.
- **All-weather/risk-parity ETFs (RPAR/UPAR/ALLW)**: structurally fragile in
  2022 (RPAR -22.8%).
- **Cross-sectional momentum across {QQQ, SPY, IWM, EFA, EEM}**: every variant
  underperforms always-QQQ baseline.
- **Symmetric hysteresis (N=2, 3, 5, 10)**: all worse than asymmetric
  N_off=1, N_on=5.
- **Offensive-bias hysteresis (slow to defense, quick to offense)**: drawdown
  blows up to -32%.
- **Vol-scaled MA windows**: parameter sweeps reveal effect is largely
  curve-fit; out-of-sample improvement is mixed.
- **Banded thresholds around MA (vol-scaled hysteresis at sub-signal level)**:
  delays entry to risk-on, hurts performance.
- **TSMOM reformulation of signals**: 12-month trailing returns are too slow
  for regime detection. MA crossings respond faster to regime changes. Lost
  0.2-0.4 Sharpe across all TSMOM variants.
- **Margin on PFIX or anything else**: combines volatile asset + leverage +
  margin interest + theta decay = asymmetric ruin.
- **Active strategy in taxable account**: tax friction kills the math;
  -4 pts/yr CAGR vs. taxable B&H.
- **Skipping monthly contributions during risk-off**: time-in-market wins for
  periodic contributions; signal misses tops by design.

## Reasoning archive

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

### Why hysteresis N_on = 5 specifically

Tested 1, 2, 3, 5, 10 plus adaptive variants. N=5 produces lowest drawdown
(-16.8%) with Sharpe tied for best (1.26). Adaptive approaches (z-score
conviction, flip-count scaling) don't beat fixed N=5.

### Why static dollar regime classification

Classification happens once at risk-off flip, then frozen. Reweighting daily
based on dollar regime changes would create excessive trading within the
off-bucket. The small benefit of dynamic adjustment isn't worth the
operational complexity.

## Annual review checklist (every January 1)

Don't modify rules during active losing positions. On Jan 1 each year:

1. Pull last 12 months of trade journal entries
2. Compare strategy returns to:
   - QQQ B&H (sanity check)
   - 60/40 SPY/AGG (real benchmark)
   - Target-date fund (life-cycle benchmark)
3. Count trades. If > 12 in a year, hysteresis tuning may be off.
4. Review emotional-state column for patterns of override pressure
5. Re-read the "Tested and rejected" list before considering changes
6. If considering changes:
   - Document the proposed change and reasoning
   - Backtest against full history
   - Run parameter sweep to check robustness
   - Wait until next January to deploy (annual cadence is the discipline
     that prevents recency-driven tinkering)
7. Update this doc with any deployed changes

## Account targets

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

## Backtest implementation reference

### Data sources

**Equity ETFs (yfinance)**

- QQQ, TQQQ, SHV, LQD, ^MOVE, GLD, UUP, XLU, VIXY
- Use auto_adjust=True for split/dividend-adjusted closes
- yfinance returns multi-column DataFrames; need ["Close"] accessor
- Common gotcha: ETFs have different inception dates

**FRED data (requires API key)**

- API key stored in repo secret FRED_API_KEY (not committed)
- Endpoint: https://api.stlouisfed.org/fred/series/observations
- Required params: series_id, api_key, file_type=json, limit=100000
- NFCICREDIT and NFCI are weekly (Wednesday release); reindex to daily and
  forward-fill, then shift by 5 trading days for realistic publish lag
- DTWEXBGS is daily, accessible normally
- FRED occasionally returns 200 with no observations key — wrap in retry
  with 2-second backoff, max 3 attempts
- Note: ICE BofA OAS series (BAMLC0A0CM etc) are now licensed-data-only as
  of April 2026, FRED only serves 3 years. Use Moody's BAA10Y/AAA10Y if you
  need credit spreads with long history.

### Signal computation (Python pseudocode)

    def healthy(series, ma_period):
        return (series > series.rolling(ma_period).mean()).shift(1).fillna(False)

    def calm_ma(series, ma_period):
        return (series < series.rolling(ma_period).mean()).shift(1).fillna(False)

    sig_lqd = healthy(LQD_close, 200)
    sig_move = calm_ma(MOVE_close, 200)

    nfci_daily = nfci_credit_weekly.reindex(daily_index, method='ffill').shift(5)
    sig_nfci = (nfci_daily < nfci_daily.rolling(26 * 5).mean()).shift(1).fillna(False)

    sig_score = sig_lqd.astype(int) + sig_move.astype(int) + sig_nfci.astype(int)
    raw_signal = (sig_score >= 2)

### Critical implementation notes

1.  **Always shift signals by 1 day before applying to returns.** A signal
    computed from today's close cannot inform today's trade. Failure to
    shift creates lookahead bias.

2.  **NFCI lag must be 5 trading days.** NFCI is published Wednesday-Thursday
    for the prior week's data.

3.  **MA warmup matters.** Skip first ~250 trading days when computing strategy
    stats. Use warmup_end = "2008-04-01" for series starting around 2007.

4.  **Returns calculation.** Use simple pct_change(), not log returns.

5.  **Hysteresis state machine.** Maintain separate deployed_state, not just
    raw_signal. The deployed state has asymmetric lag.

        def apply_hysteresis(raw, n_to_off=1, n_to_on=5):
            out = raw.copy()
            state = raw.iloc[0]
            countdown = 0
            target = state
            for i in range(len(raw)):
                observed = raw.iloc[i]
                if observed != state:
                    threshold = n_to_off if observed == 0 else n_to_on
                    if observed != target:
                        target = observed
                        countdown = 1
                    else:
                        countdown += 1
                    if countdown >= threshold:
                        state = observed
                        countdown = 0
                        target = state
                else:
                    countdown = 0
                    target = state
                out.iloc[i] = state
            return out

### Standard stat computation

    def stats(eq_curve, idx_start=None, idx_end=None):
        e = eq_curve.loc[idx_start:idx_end].dropna()
        if len(e) < 30: return None
        e = e / e.iloc[0]
        yrs = (e.index[-1] - e.index[0]).days / 365.25
        final = e.iloc[-1]
        cagr = final ** (1/yrs) - 1
        daily_ret = e.pct_change().dropna()
        sharpe = (daily_ret.mean() / daily_ret.std() * (252 ** 0.5)
                  if daily_ret.std() > 0 else 0)
        maxdd = (e / e.cummax() - 1).min()
        return {"final": final, "cagr": cagr, "sharpe": sharpe, "maxdd": maxdd}

### Standard sub-period set for evaluation

    PERIODS = [
        ("Full",          None,            None),
        ("GFC 2008",      "2008-01-01",    "2009-06-30"),
        ("2018",          "2018-01-01",    "2018-12-31"),
        ("2020 COVID",    "2020-01-01",    "2020-12-31"),
        ("2022 bear",     "2022-01-01",    "2022-12-31"),
        ("Aug 2024 yen",  "2024-07-01",    "2024-09-30"),
        ("2023-2024",     "2023-01-01",    "2024-12-31"),
        ("2025-now",      "2025-01-01",    None),
    ]

### Pitfalls encountered (don't repeat)

1. **VIX as IV proxy without skew model**: overstates hedge effectiveness
   by 30-50%. Add a skew bump for realistic options pricing.

2. **Daily-reset inverse ETFs in backtests**: BITI, EUM, etc. lose value
   in volatile sideways markets even with no directional move. Use actual
   ETF price returns.

3. **Forgetting the 1-day shift on signals**: lookahead bias. Most common
   bug.

4. **Resampling weekly NFCI to daily without forward-fill or shift**:
   creates NaN gaps that break correlations or applies future data.

5. **Comparing strategies with different start dates**: always restrict
   comparisons to common windows.

6. **Parameter sweeps that look impressive but don't generalize**: if a
   parameter sweep shows wide variation in results across reasonable
   parameter values, the improvement isn't real — even if individual
   configurations look great.

### Repo structure suggestion

    strategy-bot/
    ├── README.md
    ├── SPEC.md                  # implementation contract (deployed system)
    ├── STRATEGY.md              # human reference (this doc)
    ├── main.py                  # daily signal bot
    ├── dashboard.py             # ad-hoc state printer
    ├── last_state.json          # committed state
    ├── .github/workflows/
    │   └── cron.yml             # daily schedule
    └── backtests/
        ├── README.md            # what each backtest tests
        ├── _common.py           # shared data pulls, stats functions
        ├── v1_7_baseline.py     # reproduce deployed strategy
        ├── hysteresis_test.py
        ├── defensive_sectors.py
        ├── vol_overlay.py
        ├── dollar_regime.py
        ├── tsmom_signals.py
        ├── parameter_sweep.py
        └── ... (one file per question explored)
