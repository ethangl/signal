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
regime-based strategy runs. Currently deployed as v1.9.

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

## The signal (v1.9 deployed)

### Three macro sub-signals (drive risk-off)

1. **LQD > 200-day SMA**: investment-grade credit ETF above its long-term trend. 
   When credit is healthy, equity risk is rewarded.
2. **MOVE < 200-day SMA**: rate volatility below long-term trend. Rate 
   uncertainty often precedes equity stress.
3. **NFCI_credit < 26-week SMA**: Chicago Fed credit conditions sub-index 
   below its medium-term trend. Composite measure of bank lending stress.

macro_score = count of true sub-signals (0, 1, 2, or 3).
macro_signal = risk-on if macro_score >= 2, else risk-off.

### Price-action sub-signal (gates risk-on re-entry)

- **QQQ > 50-day SMA**: confirms the equity market itself is establishing 
  a short-term uptrend before committing to risk-on.

### Asymmetric state transitions

- Risk-off direction: macro_signal == False triggers immediate flip to risk-off.
  The price filter is not consulted. Macro deterioration is sufficient.
- Risk-on direction: requires macro_signal positive for 3 consecutive days 
  AND QQQ > 50d MA on the candidate flip day.

### Why these three macro signals

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
- Adding VIX as 4th signal: improves CAGR via threshold relaxation but 
  loses bear-market protection (2022 underperforms by 5 points)
- Replacing MOVE with VIX: MOVE is the better single equity-vol input for 
  this strategy
- Various OAS series: real but FRED restricts daily access to 3-year window

### Why 2-of-3 voting (not 3-of-3 or 1-of-3)

3-of-3 (all must agree): too defensive, too few risk-on days, misses recoveries.
1-of-3 (any can trigger risk-on): too permissive, defensive value collapses.
2-of-3: best Sharpe in backtest.

### Why the 50d MA (not 100d or 200d) for the price filter

Parameter swept windows 20d to 250d. Sharpe peaks at 40-60d, with 50d slightly 
ahead. The 200d MA filter delays re-entry too much in clean recoveries (2009, 
2023) and loses upside. The 50d MA is fast enough to capture genuine 
recoveries but slow enough to filter out the multi-week head-fake rallies 
that occurred mid-2022 bear.

### Why N=3 macro streak

v1.7 used N=5 with no price filter. The price filter and the hysteresis 
were doing similar work (both delay re-entry). With the 50d MA filter 
providing price-action confirmation, less temporal hysteresis is needed. 
Tested N=1 (no hysteresis) and it works with a slower price filter (100d MA) 
but causes whipsaws with the 50d MA. N=3 with 50d MA is the cleanest 
combination.

## The allocations (v1.9 deployed)

### Risk-on
100% QQQ.

### Risk-off (depth-aware)

At the moment of risk-on → risk-off flip, classify by macro depth:

| Depth | Description | Allocation |
|-------|-------------|-----------|
| 0 | Deep stress (macro_score = 0, ~11% of days) | 10% XLU + 55% GLD + 35% UUP |
| 1 | Mild stress (macro_score = 1, ~26% of days) | 30% XLU + 45% GLD + 25% UUP |

While risk-off, monitor macro_score daily. If depth crosses the 0/1 boundary, 
reclassify immediately and rotate the off-bucket to match. This dynamic 
reclassification was the key v1.8 → v1.9 change.

### Why depth-aware allocation

The diagnostic that motivated this change showed strikingly different asset 
behavior at macro_score = 0 vs macro_score = 1:

| Asset | Score 0 ann ret | Score 1 ann ret |
|-------|----------------|-----------------|
| XLU   | +4.4%          | **+27.9%**      |
| GLD   | **+16.7%**     | +1.0%           |
| UUP   | +7.5%          | +1.1%           |
| TLT   | +0.9%          | +8.4%           |

Score 0 favors flight-to-quality assets (GLD, UUP). Score 1 favors XLU 
because score 1 regimes are typically transient (66% recover within 10 days) 
and XLU captures that recovery. A static allocation can't optimize for both.

### Why dollar regime classification was removed

v1.6 added dollar regime classification (DTWEXBGS, NFCI tight/loose) as an 
attempt to differentiate stress types. The diagnostic showed that macro 
depth already captures most of what dollar regime was trying to capture:
- Score 0 days (deep stress) cluster in dollar Strong+Loose, but the 
  "stress" allocation (Strong+Tight) almost never fires (only 9 days)
- The 3-state dollar regime classification was adding complexity without 
  proportional value
- Removing it simplified the spec, dropped two FRED dependencies 
  (DTWEXBGS, NFCI), and improved performance

### Why these specific weights

Sensitivity analysis showed both score-0 and score-1 allocations are robust 
across a wide range:

Score-0 candidates from (0/50/50) to (20/50/30) all produce Sharpe 1.37-1.40.
The chosen 10/55/35 sits in the broad plateau with marginally better drawdown.

Score-1 candidates: higher XLU weighting actually produces higher Sharpe 
(45/35/20 gives Sharpe 1.42) but with worse drawdown (-14.3% vs -12.9% at 
30/45/25). The chosen 30/45/25 trades 0.03 Sharpe for 1.4 points of drawdown 
improvement.

## Execution mechanics

### Order types
Limit orders only. No market orders. 
- Buys: bid + 1¢
- Sells: ask - 1¢
- Mid-day execution (10:30am-3pm ET) for tightest spreads
- Avoid first 5-10 min of trading and last 30 min

### Order sequencing
- Going risk-off: sell QQQ first, then buy XLU/GLD/UUP simultaneously
- Mid-risk-off depth change: execute sells and buys simultaneously (small 
  rebalance trades). Score 1→0 sells XLU and buys GLD/UUP; score 0→1 sells 
  GLD/UUP and buys XLU.
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

Backtested impact: Sharpe ~1.36, CAGR ~24%, MaxDD ~-21% (on v1.8 base; not 
yet retested on v1.9). Not deployed because: requires daily attention, TQQQ 
decay risks, manual execution slippage.

### RSI(2) volatility overlay

Mean-reversion overlay on top of vol-targeted leverage:
- When RSI(2) of QQQ > 95 AND regime is risk-on: 
  allocate 25% to VIXY for 5 trading days, reduce on-leg to 75%

Backtested impact: marginal Sharpe improvement (+0.02). Not worth operational 
load for manual execution.

### Tech sub-sector momentum

70% QQQ + 30% momentum-picked from {SMH, IGV, CIBR, ARKK}, 6-month lookback:
- CAGR ~26%, Sharpe ~1.60 over 2015-2026 window

Not deployed because: window heavily biased toward AI/semis era continuing; 
operational complexity (rebalance between 5 ETFs monthly).

### BTC trend-gated allocation

5-15% BTC during risk-on AND when BTC > 200d MA, else redirected to QQQ:
- Full-window (2014-2026): +0.4 Sharpe improvement (flattered by 2014-2021)
- Post-2022 only: +0.10 Sharpe improvement, marginal

### Conviction-based hysteresis

Z-score the gap between each sub-signal and its threshold. Higher conviction 
= faster action; lower conviction = slower. Ties with fixed N=3 on Sharpe; 
not deployed because fixed N values are empirically dominant and simpler.

### Score-3 sub-strategy

Diagnostic showed macro_score=3 has different character than score=2 
(highest-conviction risk-on). Possible future addition: leverage QQQ position 
when score=3 (e.g., 80% QQQ + 20% TQQQ) for conviction-weighted exposure. 
Not tested in detail.

### Hybrid 70% QQQ + 30% momentum-pick (regime-risk hedge)

For protection against a 2000-2010 style QQQ malaise: hold 30% in a 
broader-universe momentum pick (rotated monthly across {QQQ, SPY, IWM, EFA, 
IWN, IWD, IWF}). Captures most QQQ upside while introducing some diversification 
across regimes. Not deployed because we have no evidence the regime is about 
to change. Documented for future consideration.

### Taxable hedge overlay (put spreads)

If/when QQQ position in taxable becomes large enough to warrant active 
hedging: long 5% OTM, short 15% OTM, 60 DTE puts on QQQ during risk-off. 
Marginal Sharpe improvement; psychologically hard to execute; premium drag 
in calm years.

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
- **VIX as 4th macro signal (2-of-4 voting)**: improves CAGR via threshold 
  relaxation but loses bear-market protection (2022 underperforms by 5 points).
- **VIX replacing MOVE**: slightly worse than MOVE (Sharpe 1.29 vs 1.32).
- **VIX term structure (contango as input)**: 92% positive, too permissive 
  to add information.
- **Currency baskets short of EUR/JPY/etc.**: retail products don't exist 
  in IRA-eligible form.
- **Buffered ETFs (BJUL/PJUL)**: 2-3% structural drag, only for behavioral 
  reasons.
- **All-weather/risk-parity ETFs (RPAR/UPAR/ALLW)**: structurally fragile in 
  2022 (RPAR -22.8%).
- **Cross-sectional momentum across {QQQ, SPY, IWM, EFA, EEM}**: every variant 
  underperforms always-QQQ baseline in our test window.
- **Symmetric hysteresis (N=2, 3, 5, 10)**: all worse than asymmetric 
  N_off=1, N_on>1.
- **Offensive-bias hysteresis (slow to defense, quick to offense)**: drawdown 
  blows up to -32%.
- **Vol-scaled MA windows**: parameter sweeps reveal effect is largely 
  curve-fit; out-of-sample improvement is mixed.
- **Banded thresholds around MA**: delays entry to risk-on, hurts performance.
- **TSMOM reformulation of signals**: 12-month trailing returns are too slow 
  for regime detection.
- **GLD/IEI split in off-bucket**: tested ratios 100/0 to 0/100, all roughly 
  flat in Sharpe; pure GLD has best CAGR and MaxDD.
- **Equal-weight 25/25/25/25 GLD/IEI/UUP/XLU off-bucket**: ties on Sharpe 
  with v1.5 baseline but loses 0.7 points CAGR.
- **Eliminating hysteresis entirely with 50d MA price filter**: -3.6% CAGR 
  in 2022 because the 50d MA isn't slow enough on its own.
- **Long-window price filter (200d MA) for risk-on**: too restrictive.
- **Oversold triggers as alternate risk-on path**: RSI<30, RSI<25, 
  distance-from-MA, recent decline all tested as supplemental triggers. 
  None added meaningful Sharpe (+0.01 best case). Macro signal is the rate-
  limiting step, not the price filter.
- **QQQA (Dorsey Wright momentum on Nasdaq)**: worse than QQQ on every 
  metric, $17M AUM is delisting risk.
- **QQQE (equal-weight Nasdaq)**: 4.4 points CAGR worse, 0.21 Sharpe worse. 
  Concentration in QQQ has been the feature, not the bug.
- **27 defensive sector candidates**: XLU wins. XLP/DVY/VYM are within 0.05 
  Sharpe as defensible alternatives; bonds (IEI/IEF/TLT) more defensive in 
  stress but earn less in calm periods.
- **Static depth classification (Option A)**: same Sharpe as v1.8 baseline. 
  Must reclassify dynamically (Option B) to capture the depth signal.
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

### Why these specific MA periods (200d for LQD/MOVE, 26w for NFCI, 50d for QQQ)
Tested 50d, 100d, 200d, 252d for LQD/MOVE. 200d was robust across 
sub-periods without being so slow it missed 2018/2020 transitions. For 
NFCI_credit (weekly data), 26-week MA is the equivalent timescale. For the 
QQQ price filter, parameter sweep showed 40-60d is the Sharpe peak.

### Why XLU specifically vs. USMV or VPU
USMV: too dynamic, ends up concentrated in whatever was recently low-vol.
VPU: similar to XLU but slightly higher expense ratio with no clear advantage.
XLU: clean, liquid, low expense ratio, predictable holdings.

### Why GLD not IAU or GLDM  
Functionally identical for our purposes. GLD has highest liquidity. IAU 
slightly cheaper expense ratio. Either is acceptable.

### Why UUP not USDU
UUP tracks DXY directly (~58% EUR weight). USDU is a managed product with 
discretionary weights. UUP is more predictable.

### Why asymmetric signals for risk-on vs risk-off
Risk-off is a question about emerging macro stress — credit, vol, and 
conditions deterioration are forward-looking signals of equity stress. 
Risk-on is a question about whether the equity market itself is establishing 
an uptrend — a price-action question, not a credit-conditions question. 
The 2022-2023 transition was the canonical case: credit normalized in 
late 2022 but QQQ chopped sideways through Q1 2023 before launching higher. 
v1.7's signal would have re-entered in December 2022, two months early. 
v1.8+'s 50d MA filter delayed re-entry to mid-January 2023.

### Why N=3 macro streak (not eliminating hysteresis entirely)
Tested N=1 (no hysteresis) with various price filter windows. Works with 
slow filters (100d MA) but causes whipsaws with faster filters (50d). The 
50d filter is preferred because it captures recoveries faster, so N=3 
provides the small amount of additional patience needed to avoid bad 
re-entries during prolonged choppy regimes like 2022.

### Why dynamic depth reclassification (not static)
Most risk-off flips start at score=1 (mild stress as the first deterioration). 
The score deepens to 0 after the flip in some cases. Static classification 
at flip captures only the initial state. Dynamic reclassification when depth 
crosses 0/1 boundary lets the off-bucket respond to the actual regime as it 
evolves. The diagnostic showed this happens ~4-5 times per year, not 
constantly, so flicker isn't a concern.

### Why immediate reclassification (no streak)
The depth change uses the same macro signal we already trust for the main 
risk-off trigger. Same N=1 logic. The historical reclassification count 
(71 events over 16 years) confirms this isn't noisy in practice.

## Annual review checklist (every January 1)

Don't modify rules during active losing positions. On Jan 1 each year:

1. Pull last 12 months of trade journal entries
2. Compare strategy returns to:
   - QQQ B&H (sanity check)
   - 60/40 SPY/AGG (real benchmark)
   - Target-date fund (life-cycle benchmark)
3. Count trades. If > 12 in a year, hysteresis tuning may be off. Note: 
   v1.9 expects 4-6 main flips + 0-4 depth changes per year.
4. Review emotional-state column for patterns of override pressure
5. Re-read the "Tested and rejected" list before considering changes
6. Specific v1.9 questions to revisit:
   - Has QQQ leadership held? If not, consider hybrid 70/30 with momentum 
     pick from broader universe
   - Are score-1 → score-0 transitions occurring with expected frequency 
     (~4/year)? If much more or less, examine signal sensitivities.
7. If considering changes:
   - Document the proposed change and reasoning
   - Backtest against full history
   - Run parameter sweep to check robustness
   - Verify in-sample / out-of-sample stability
   - Wait until next January to deploy (annual cadence is the discipline)
8. Update this doc with any deployed changes

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
- QQQ, TQQQ, SHV, LQD, ^MOVE, GLD, UUP, XLU, VIXY, IEI
- Use auto_adjust=True for split/dividend-adjusted closes
- yfinance returns multi-column DataFrames; need ["Close"] accessor
- Common gotcha: ETFs have different inception dates

**FRED data (requires API key)**
- API key stored in repo secret FRED_API_KEY (not committed)
- Endpoint: https://api.stlouisfed.org/fred/series/observations
- Required params: series_id, api_key, file_type=json, limit=100000
- NFCICREDIT is weekly (Wednesday release); reindex to daily and 
  forward-fill, then shift by 5 trading days for realistic publish lag
- FRED occasionally returns 200 with no observations key — wrap in retry 
  with 2-second backoff, max 3 attempts

### Signal computation (Python pseudocode)

    def healthy(series, ma_period):
        return (series > series.rolling(ma_period).mean()).shift(1).fillna(False)

    def calm_ma(series, ma_period):
        return (series < series.rolling(ma_period).mean()).shift(1).fillna(False)

    # Macro signals
    sig_lqd = healthy(LQD_close, 200)
    sig_move = calm_ma(MOVE_close, 200)

    nfci_daily = nfci_credit_weekly.reindex(daily_index, method='ffill').shift(5)
    sig_nfci = (nfci_daily < nfci_daily.rolling(26 * 5).mean()).shift(1).fillna(False)

    macro_score = sig_lqd.astype(int) + sig_move.astype(int) + sig_nfci.astype(int)
    macro_signal = (macro_score >= 2)

    # Price filter
    price_filter = healthy(QQQ_close, 50)

### State machine (v1.9)

    def deploy_v19(macro_signal, macro_score, price_filter, n_to_on=3):
        """
        Returns (deployed_state, current_depth) for each day.
        deployed_state: True if risk-on, False if risk-off
        current_depth: 0 or 1 when risk-off, None when risk-on
        """
        state = bool(macro_signal.iloc[0])
        depth = None if state else (0 if int(macro_score.iloc[0]) == 0 else 1)
        macro_streak = 0
        states = []
        depths = []
        
        for i in range(len(macro_signal)):
            m = bool(macro_signal.iloc[i])
            s = int(macro_score.iloc[i])
            p = bool(price_filter.iloc[i])
            
            if state:
                # Currently risk-on
                if not m:
                    # Flip to risk-off; classify depth
                    state = False
                    depth = 0 if s == 0 else 1
                    macro_streak = 0
            else:
                # Currently risk-off
                if m:
                    # Macro positive day - track streak for re-entry
                    macro_streak += 1
                    if macro_streak >= n_to_on and p:
                        state = True
                        depth = None
                        macro_streak = 0
                    # NOTE: depth doesn't change while macro_signal == True
                    # because we're testing re-entry, not stress depth
                else:
                    # Macro negative - reset streak, check for depth change
                    macro_streak = 0
                    new_depth = 0 if s == 0 else 1
                    if new_depth != depth:
                        depth = new_depth
            
            states.append(state)
            depths.append(depth)
        
        return states, depths

### Critical implementation notes

1. **Always shift signals by 1 day before applying to returns.** A signal 
   computed from today's close cannot inform today's trade.

2. **NFCI lag must be 5 trading days.** NFCI is published Wednesday-Thursday 
   for the prior week's data.

3. **MA warmup matters.** Skip first ~250 trading days when computing strategy 
   stats.

4. **Returns calculation.** Use simple pct_change(), not log returns.

5. **Depth reclassification timing.** When checking depth crosses, use the 
   shifted (lagged) macro_score, not the current day's. This avoids 
   lookahead bias.

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
        ("Early 2023 recovery", "2023-01-01", "2023-06-30"),
        ("Aug 2024 yen",  "2024-07-01",    "2024-09-30"),
        ("2023-2024",     "2023-01-01",    "2024-12-31"),
        ("2025-now",      "2025-01-01",    None),
    ]

### Pitfalls encountered (don't repeat)

1. **VIX as IV proxy without skew model**: overstates hedge effectiveness 
   by 30-50%.

2. **Daily-reset inverse ETFs in backtests**: BITI, EUM, etc. lose value 
   in volatile sideways markets even with no directional move.

3. **Forgetting the 1-day shift on signals**: lookahead bias. Most common bug.

4. **Resampling weekly NFCI to daily without forward-fill or shift**: 
   creates NaN gaps that break correlations.

5. **Comparing strategies with different start dates**: always restrict 
   comparisons to common windows.

6. **Parameter sweeps that look impressive but don't generalize**: if a 
   parameter sweep shows wide variation in results across reasonable 
   parameter values, the improvement isn't real.

7. **Confusing threshold relaxation with new information**: adding a 4th 
   signal with the same vote threshold (e.g., VIX 2-of-4) effectively 
   loosens the macro requirement.

8. **Static classification of dynamic regimes**: the v1.8 → v1.9 lesson. 
   Risk-off regimes evolve in depth over their duration. Static classification 
   at flip captures only the initial conditions. When the underlying assets 
   have meaningfully different returns at different depths, dynamic 
   reclassification adds real value.

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
        ├── v1_9_baseline.py     # reproduce deployed strategy
        ├── hysteresis_test.py
        ├── defensive_sectors.py
        ├── vol_overlay.py
        ├── depth_aware.py
        ├── tsmom_signals.py
        ├── asymmetric_signals.py
        ├── parameter_sweep.py
        └── ... (one file per question explored)
