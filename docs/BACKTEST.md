## Backtest implementation reference

### Data sources

**Equity ETFs (yfinance)**

- QQQ, TQQQ, SHV, LQD, ^MOVE, GLD, UUP, XLU, VIXY
- Use `auto_adjust=True` for split/dividend-adjusted closes
- yfinance returns multi-column DataFrames; need `["Close"]` accessor
- Common gotcha: ETFs have different inception dates. PFIX (2021), USMV
  (2011), TQQQ (2010). Limits backtest start.

**FRED data (requires API key)**

- API key stored in repo secret `FRED_API_KEY` (not committed)
- Endpoint: `https://api.stlouisfed.org/fred/series/observations`
- Required: `series_id`, `api_key`, `file_type=json`, `limit=100000`
- NFCICREDIT is weekly (Wednesday release); reindex to daily and
  forward-fill, then shift by 5 trading days for realistic publish lag
- DCOILWTICO and similar daily series occasionally restricted to 3-year
  windows (ICE BofA OAS series like BAMLC0A0CM are now licensed-data-only
  as of April 2026, FRED only serves 3 years)
- FRED occasionally returns 200 with no `observations` key — wrap in retry
  with 2-second backoff, max 3 attempts
- Series confirmed long-history accessible: NFCI, ANFCI, NFCICREDIT,
  NFCIRISK, NFCILEVERAGE, STLFSI4, BAA10Y, AAA10Y, DGS3MO, DGS10, T10Y2Y

### Signal computation (Python pseudocode)

```python
# Helper functions
def healthy(series, ma_period):
    return (series > series.rolling(ma_period).mean()).shift(1).fillna(False)

def calm_ma(series, ma_period):
    return (series < series.rolling(ma_period).mean()).shift(1).fillna(False)

# Three sub-signals
sig_lqd = healthy(LQD_close, 200)
sig_move = calm_ma(MOVE_close, 200)

nfci_daily = nfci_credit_weekly.reindex(daily_index, method='ffill').shift(5)
sig_nfci = (nfci_daily < nfci_daily.rolling(26 * 5).mean()).shift(1).fillna(False)

# Composite
sig_score = sig_lqd.astype(int) + sig_move.astype(int) + sig_nfci.astype(int)
raw_signal = (sig_score >= 2)
```

### Critical implementation notes

1. **Always shift signals by 1 day before applying to returns.** A signal
   computed from today's close cannot inform today's trade. Failure to
   shift creates lookahead bias and inflates backtest performance by
   1-3 Sharpe points.

2. **NFCI lag must be 5 trading days, not 1.** NFCI is published
   Wednesday-Thursday for the prior week's data. A 1-day shift assumes
   you have access to data you don't yet have.

3. **MA warmup matters.** 200-day MAs need 200 days of data before they're
   meaningful. Skip first ~250 trading days when computing strategy stats.
   Use `warmup_end = "2008-04-01"` for series starting around 2007.

4. **Returns calculation.** Use simple `pct_change()`, not log returns,
   for strategy simulation. Log returns are useful for cross-correlation
   tests but not for compounding actual portfolio returns.

5. **Hysteresis state machine.** Maintain a separate `deployed_state`
   variable, not just `raw_signal`. The deployed state has 1-day asymmetric
   lag from raw signal: instant on flips to off, 3-day delay on flips to on.

```python
def apply_hysteresis(raw, n_to_off=1, n_to_on=3):
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
```

### Standard stat computation

```python
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
```

### Standard sub-period set for evaluation

```python
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
```

These are the events that mattered most across the backtests. If a new
variant doesn't show meaningful behavior in at least 2018, 2020, and 2022,
it's probably not capturing anything real.

### Reference benchmark numbers

Use these as sanity checks when reproducing the backtest. If you're not
landing within ~0.05 Sharpe / 1 point of CAGR, something's off in the
implementation.

| Variant                               | CAGR  | Sharpe | MaxDD  |
| ------------------------------------- | ----- | ------ | ------ |
| QQQ B&H (2008-2026)                   | 16.9% | 0.83   | -49.4% |
| 2-of-3 vote, simple QQQ-or-SHV        | 17.6% | 1.44   | -12.7% |
| v1.5 deployed (2-of-3 + 30/40/30 off) | 19.8% | 1.29   | -23.4% |
| v1.5 + N_off=1, N_on=3 hysteresis     | 19.1% | 1.28   | -22.2% |
| v2 (vol-targeted leverage)            | 24.2% | 1.36   | -21.1% |

### Code style for backtest scripts

Existing pattern (used across ~30 backtest scripts in the conversation):

- Single-file Python scripts (no imports of local modules)
- Dependencies: pandas, numpy, yfinance, requests, matplotlib, scipy
- Each script is self-contained: pulls data, computes signals, runs backtest,
  prints results, saves chart to `/mnt/user-data/outputs/`
- Print results in fixed-width format with `:<X` formatting for tables
- Chart format: 1 or 2 panels, log-scale y-axis for equity curves
- File naming: descriptive, e.g., `vol_overlay.py`, `hysteresis_test.py`
- No need to factor common code into a library yet; copy-paste between
  scripts is fine for backtest exploration

### Repo structure suggestion

strategy-bot/
├── README.md
├── SPEC.md # implementation contract (deployed system)
├── STRATEGY.md # human reference (this doc)
├── main.py # daily signal bot
├── dashboard.py # ad-hoc state printer
├── last_state.json # committed state
├── .github/workflows/
│ └── cron.yml # daily schedule
└── backtests/
├── README.md # what each backtest tests
├── \_common.py # shared data pulls, stats functions
├── v1_5_baseline.py # reproduce deployed strategy
├── hysteresis_test.py
├── defensive_sectors.py
├── vol_overlay.py
└── ... (one file per question explored)

The `_common.py` module would hold:

- `fred(series_id)` with retry logic
- `pull_etf(ticker, start, end)` wrapping yfinance
- `apply_hysteresis()`
- `stats()`
- The standard PERIODS list
- A canonical `nfci_daily` helper

Each backtest script then just:

```python
from _common import fred, pull_etf, stats, PERIODS
# ... rest of the test
```

### Pitfalls encountered (don't repeat)

1. **VIX as IV proxy without skew model**: overstates hedge effectiveness
   by 30-50%. Add a skew bump (~0.5-1.0 vol points per 1% OTM) and a
   MOVE-based vol expansion bump for realistic options pricing.

2. **Daily-reset inverse ETFs in backtests**: BITI, EUM, etc. lose value
   in volatile sideways markets even with no directional move. Don't
   compute their backtest as "gain when underlying falls" — use actual
   ETF price returns.

3. **Treating VIX-derived IV as static through hedge lifetime**: real
   hedges benefit from vol expansion at exit. The simulation undervalues
   actual hedge payoff in stress events by maybe 40%.

4. **Forgetting the 1-day shift on signals**: lookahead bias. Most common
   bug.

5. **Resampling weekly NFCI to daily without forward-fill or shift**:
   creates NaN gaps that break correlations or applies future data.

6. **Comparing strategies with different start dates**: PFIX backtests
   only go to 2021, can't be compared to QQQ B&H backtests starting 2008.
   Always restrict comparisons to common windows.

### Walk-forward validation

The signal selection (LQD>200, MOVE<200, NFCI<26w, 2-of-3 voting) was
walk-forward validated 2015-2025 using anchored expanding window. Key
findings:

- LQD>200 was selected as best single signal in 10/11 years
- 2-of-3 voting selected as best ensemble in 9/11 years
- Out-of-sample Sharpe 1.35, slightly above in-sample best
- This is unusual; signals don't usually validate this cleanly

If walking forward into new data and reselection yields meaningfully
different signals, that's a flag — either the relationship has decayed
or there's an implementation bug.
