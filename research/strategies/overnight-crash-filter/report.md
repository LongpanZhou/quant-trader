> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Rebuild: `overnight-crash-filter` — Night Continuation / Day Reversal

**Status:** pre-registered, **backtest paused by the lead**. No result.json has
been generated. Numbers below marked *TBD* must be filled only after
authorization.

**Original:** `research/agents2/overnight-crash-filter` — 165-day QQQ regime +
TQQQ overnight/first-hour + 20-day vol filter + 4% stop.
**Rebuild:** `research/strategies/overnight-crash-filter`.

---

## 1. What was actually new in the original

Strip the 165-day QQQ regime and the round-1 stop and two things remain:

1. **The overnight premium is a block effect, not a 24-hour effect.** On the
   local 2016-2026 data TQQQ's close-to-open block compounds at roughly
   +30%/yr against +7%/yr for the session, and the first hour is the best
   intraday block.
2. **Volatility decides whether the overnight block is worth its gap risk.**
   The original's 20-day vol filter skipped the worst 2020 nights.

Both are real. But the original only *timed* an existing 24-hour TQQQ position;
the return came from the 165-day regime and the overlay shaved a few days a
year. That is exactly the "strip the base and call the residue a strategy"
failure the clarification warns about.

## 2. Hypothesis (pre-registered, before any run)

> The overnight and intraday blocks are priced by different clienteles, so the
> *sign of the previous block's return* predicts which block pays next:
> **the night continues an up day, and the day reverses a down night.** A
> strategy that holds the leveraged index only in the predicted block, sized so
> that a 3-sigma gap costs a fixed fraction of equity, earns a risk premium that
> is **not** the old 165-day trend exposure.

Mechanism, from the literature:

- "Night extends the day": the overnight return is positively related to the
  prior intraday return (Lou-Polk-Skouras clientele story; *Day Destroys the
  Night* continuation result).
- "The day destroys the night": the intraday return is negatively related to the
  overnight gap (same paper: coefficient t = -5.67, R² ≈ 13%).
- The overnight premium is compensation for bearing risk while the market is
  closed (NY Fed SR 917; *Give me a break* 2025), so the right risk control is an
  **ex-ante gap budget**, not a price stop and not a long moving average.

**What would falsify the hypothesis:**

| # | Falsifier | Decision if it fails |
|---|---|---|
| F1 | Mean TQQQ overnight return after up days is **not** greater than after down days, or the difference has t < 1.5 | Night leg fails |
| F2 | Mean QQQ intraday return after a negative gap is **not** positive, or is not greater than after a positive gap | Day leg fails |
| F3 | Dev daily-return correlation vs the 165-day baseline is **>= 0.60** | Strategy rejected (shared-base rule) |
| F4 | Dev Sharpe is below the 165-day baseline's, or dev max drawdown is not lower | Strategy rejected as a rebuild of the same risk |
| F5 | The vol ceiling does not reduce max drawdown versus the same strategy with no ceiling | Risk rule fails; simplify to the budget only |
| F6 | The result is not on a parameter plateau (±1 step changes the sign of the edge) | Rejected as overfit |

If F1 fails but F2 passes, the strategy becomes day-reversal only; if F2 fails
but F1 passes, it becomes night-continuation only; if both fail, the idea is
retired with evidence. **The two legs are independent bets and are tested
separately before being combined.**

### 2.1 How this differs from the old base

| | Old base | This rebuild |
|---|---|---|
| Gate | QQQ close vs 165-day SMA, binary | none (no moving average of any length) |
| Signal | slow trend | sign of the prior block's return + overnight gap |
| Holding period | 24 hours, always | night leg ~17.5 h, day leg ~6.5 h, never 24 h |
| Asset | 100% TQQQ | TQQQ at night, QQQ by day, cash otherwise |
| Sizing | 0% or 100% | continuous 0-100%, gap-budget formula |
| Risk control | 4% intraday stop (cannot see gaps) | ex-ante 3-sigma gap budget + 40% vol ceiling |
| Time in market | ~80% of bars | ~50% of calendar time (night ~39%, day ~12%); bar-weighted ~45% because the night leg is a single 15:59 bar |

## 3. Universe and data constraint

| Asset | Role | Why |
|---|---|---|
| TQQQ | night leg (3x) | the leveraged expression of the overnight premium |
| QQQ | day leg (1x), signal source | the reversal trade is a 1x mean-reversion, not a 3x bet |
| Cash | flat | BIL doubles the fill count on every transition and the carry does not pay for it at 1-5 bp |

Local data available: 1-minute QQQ/TQQQ/BIL from 2016-01-04, plus daily
2015-2026. **No other intraday asset exists locally**: `data/cache/dukascopy/SPY`
covers only 2026-08-31 onward (7 weeks), and there is no sector, bond, gold or
volatility-product intraday history. A wider universe (GLD/TLT/VIXY or sector
LETFs) would require new data under `data/round3/` and is out of scope while the
backtest is paused. The design is therefore deliberately built on the three
assets that can be tested honestly.

## 4. Exact specification

### 4.1 Signals (all causal)

For session *k* (bars `first[k]..last[k]`, half days included by index, not by
clock time):

| Signal | Definition | Known at |
|---|---|---|
| `r_day[k]` | QQQ close of the 15:58 bar / QQQ open of 09:30 - 1 | 15:58 of day k |
| `gap[k]` | QQQ 09:30 open / QQQ close of the previous session - 1 | 09:30 of day k |
| `sig_night[k]` | stdev of TQQQ overnight log returns, 20 sessions through k-1, annualised | before 15:58 of day k |
| `sig_day[k]` | stdev of QQQ open-to-close log returns, 20 sessions through k-1, annualised | before 09:30 of day k |
| `sig_tot[k]` | stdev of QQQ close-to-close log returns, 20 sessions through k-1, annualised | before 09:30 of day k |

No moving average of any length is used. `sig_*` are volatility estimates, not
trend filters.

### 4.2 Positions

**Night leg** (decided 15:58, filled 15:59 open, exits 09:30 open):

```
if r_day[k] > 0 and sig_night[k] <= 40% and sig_tot[k] <= 40%:
    w_night = min(1, 4% / (3 * sig_night_daily[k]))
    long TQQQ from 15:59 open to 09:30 open
else:
    flat
```

**Day leg** (decided at the 09:30 close, filled 09:31 open, exits 15:59 open):

```
if gap[k] < 0 and sig_day[k] <= 40% and sig_tot[k] <= 40%:
    w_day = 0.5 * min(1, 4% / (3 * sig_day_daily[k]))
    long QQQ from 09:31 open to 15:59 open
else:
    flat
```

- The two legs never overlap: the night leg ends at the 09:30 open, the day leg
  starts at the 09:31 open.
- `sig_night_daily = sig_night / sqrt(252)`, same for the day.
- The position is at most 100% in one asset; the rest is cash.
- No stop, no short, no leverage beyond TQQQ's own 3x.

### 4.3 Why the entry/exit times are what they are

- The night decision uses the 15:58 close and fills at the 15:59 open: the
  harness convention is "weight set at bar i, filled at i+1's open", and the
  15:58 bar is the last bar whose close is known before the 15:59 print.
- The day decision needs the 09:30 open, which is only known when the 09:30 bar
  has printed; the earliest legal fill is therefore the 09:31 open. The 09:30
  bar's move (the bounce itself) is deliberately **not** captured, which makes
  the test conservative.
- Exits are at the 09:30 / 15:59 opens, so the strategy never holds the closing
  auction or the opening print. This is conservative relative to the original
  (which bought the 15:59 open and sold the 09:30 open) and avoids the
  close-rebalancing flow that the `letf-rebalance-flow` rebuild studies.

### 4.4 Risk model

| Rule | Value | Rationale |
|---|---|---|
| Gap budget | 4% of equity per 3-sigma block move | ex-ante cap on what a gap can do; replaces the unobservable stop |
| Vol ceiling | 40% annualised, on `sig_night`/`sig_day` and on `sig_tot` | cut the fat-tail regime where the 3-sigma budget is not credible |
| Day-leg scale | 0.5 | lower conviction: the reversal is a weaker, 1x effect |
| Cash | 100% when flat | cost; BIL doubles fills |
| Drawdown brake | none in the base | kept as a variant only; a path-dependent brake is a second overfitting surface |

## 5. Test plan (to run only after authorization)

1. **Legs separately.** Night-only (day leg off) and day-only (night leg off) on
   dev, 1 bp: event count, mean, t-stat, bootstrap p-value (the brief requires
   this for <100 events; the broad legs have ~900-1000 events, but the
   large-gap diagnostic will be reported with its ~30 events).
2. **Combined** on dev 2016-01-04..2023-12-29 at 0/1/5/10 bp.
3. **Benchmarks:** TQQQ, QQQ, the 165-day baseline (benchmark only), and the
   original's own 10y/5y numbers from
   `research/agents2/overnight-crash-filter/result.json`.
4. **Correlation:** daily returns vs the 165-day baseline on dev. Expected
   0.40-0.50; the hard cap is 0.60. The baseline is warmed on the daily QQQ
   parquet (which starts 2015-01-02) so it is fully invested from the first
   development session rather than cold for 165 days — a cold baseline would
   flatter the correlation. Correlation vs other rebuilds is the lead's job (no
   other rebuild exists yet at the time of writing).
5. **Sub-periods:** 2016-19, 2020-21, 2022-23.
6. **Neighbourhood (±1 step):** vol_win 10/20/40; vol_ceil 35/40/45%;
   gap_budget 3/4/5/6%; day_scale 0.25/0.5/0.75; morning extension 0/30/60
   minutes on the night leg.
7. **Placebo:** (a) shuffle the sign of `r_day` across days, keeping the same
   number of night legs and the same sizing; (b) replace `gap < 0` with a random
   draw with the same trigger rate. Report the placebo CAGR/DD distribution.
8. **Overfitting controls:** `variants_tried` count, yearly returns, DD windows,
   and the plateau table.

## 6. Expected result and correlation (pre-registered)

- Night leg: ~55% of sessions, mean overnight return above the unconditional
  +12.6 bp/day (dev, exploratory); the effect should be strongest in 2016-19 and
  weakest in 2022.
- Day leg: ~45% of sessions, mean intraday return modestly positive; if it is
  not, F2 fires and the leg is dropped.
- Combined dev: expected Sharpe 0.9-1.3, max DD 25-40%, CAGR 25-40% at 1 bp,
  with the range deliberately wide because no run has been done.
- **Expected correlation vs the 165-day baseline: 0.40-0.50.** The base is
  100% TQQQ roughly 80% of the time; the rebuild is 40-90% TQQQ only on
  selected nights (~55%) and 30-60% QQQ on selected days (~45%), and is out of
  the market the rest of the time. Shared variance is the overlapping overnight
  block, not the whole day.
- **Collision risk:** the closest rebuild is `intraday-momentum` (overnight +
  first hour). That rebuild should be 24-hour or first-hour focused; this one is
  a two-block sign-conditional rotation with a gap budget. The lead must check
  the <0.70 pairwise rule; if it collides, this strategy should move to the
  large-gap day leg or the first-hour night extension, not the other rebuild.

**Known weaknesses that the test must expose:**

1. The day leg is the weak half. In the 25-30% vol regime the dev session mean is
   **-26.9 bp/day**, so a long-QQQ reversal leg fights a headwind there. If F2
   fails, the strategy drops to night-only and the day leg is reported as a
   rejected sub-idea.
2. The night leg's conditional edge could be concentrated in a few 2020-type
   rebounds; the sub-period table and the 2020-21 block will show it.
3. The 40% vol ceiling is calibrated on one crisis (2020). Its ablation is a
   required check, not an optional one.
4. The gap budget is a Gaussian approximation to a fat-tailed variable; a
   single 10-sigma gap can still exceed the budget. That is why the ceiling
   exists and why the strategy is capped at 100% with no leverage.

## 7. Exploratory evidence gathered before the pause (dev only)

These numbers are from the superseded v1 design (always-on overnight with a
binary vol skip). They motivate the redesign but are **not** results of the
pre-registered strategy. Files: `explore.py`, `grid.py`, `grid_dev.csv`
(sandbox, not part of the frozen strategy).

| Block (dev 2016-01-04..2023-12-29) | Mean | Ann. | t |
|---|---:|---:|---:|
| TQQQ overnight 15:59->09:30 | 12.58 bp | +26.3% | 2.22 |
| TQQQ first 30 min | 6.42 bp | +14.9% | 2.14 |
| TQQQ first 60 min | 6.77 bp | +14.2% | 1.76 |
| TQQQ session 09:30->15:59 | 9.95 bp | +11.5% | 1.34 |

| QQQ 20-day vol bucket | Overnight mean | First-60m mean | Session mean |
|---|---:|---:|---:|
| <12% | +12.0 bp | +3.5 bp | +15.3 bp |
| 12-16% | +12.9 bp | +0.7 bp | +9.3 bp |
| 16-20% | +15.8 bp | +20.8 bp | +17.2 bp |
| 20-25% | +32.3 bp | +1.9 bp | +15.5 bp |
| 25-30% | +33.1 bp | -13.9 bp | -26.9 bp |
| 30-40% | -35.8 bp | +16.6 bp | +13.5 bp |
| >40% | +40.5 bp | +77.7 bp | +50.9 bp |

Two facts drive the new design: the overnight mean is positive and largest in
the 20-30% vol band, and it inverts in the 30-40% band — so the overnight block
must be *sized*, not simply switched on/off; and the session mean is negative in
the 25-30% band, which is the regime where a day-reversal leg must prove itself.

## 8. Results (TBD after authorization)

### 8.1 Headline, development 2016-01-04..2023-12-29

| Costs | CAGR | Max DD | Sharpe | Vol | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|
| 0 bp | TBD | TBD | TBD | TBD | TBD | TBD |
| **1 bp** | TBD | TBD | TBD | TBD | TBD | TBD |
| 5 bp | TBD | TBD | TBD | TBD | TBD | TBD |
| 10 bp | TBD | TBD | TBD | TBD | TBD | TBD |

### 8.2 Legs separately and falsifier checks

| Check | Result | Pass? |
|---|---|---|
| Night: mean after up vs down days (t) | TBD | TBD (F1) |
| Day: mean after negative vs positive gaps (t) | TBD | TBD (F2) |
| Correlation vs 165-day baseline | TBD (expected 0.40-0.50) | TBD (F3, cap 0.60) |
| Sharpe vs baseline / DD vs baseline | TBD | TBD (F4) |
| Vol ceiling ablation | TBD | TBD (F5) |
| ±1-step plateau | TBD | TBD (F6) |
| Placebo (shuffled signal) | TBD | TBD |

### 8.3 Sub-periods, yearly, neighbourhood, placebo

TBD. Tables to be generated by `strategy.py` and copied here without hand edits.

### 8.4 Correlation and collision

| Counterpart | Dev daily-return correlation |
|---|---:|
| 165-day baseline | TBD |
| TQQQ buy & hold | TBD |
| QQQ buy & hold | TBD |
| Other rebuilds (lead) | TBD |

## 9. Files

| File | Purpose |
|---|---|
| `strategy.py` | frozen implementation: `build_weights(...) -> (weights, info)` and `main()` (dev only by default; `--full` for the lead) |
| `PROVENANCE.md` | source table, roles, rejected ideas |
| `report.md` | this file |
| `result.json` | **not generated** — backtest paused |
| `explore.py`, `grid.py`, `grid_dev.csv` | pre-pause sandbox for the superseded v1; not part of the frozen strategy |

Reproduce (only after authorization):

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\strategies\overnight-crash-filter\strategy.py          # dev only
python research\strategies\overnight-crash-filter\strategy.py --full   # lead: 10y/5y/holdout
```
