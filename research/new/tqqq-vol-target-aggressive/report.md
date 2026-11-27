# Aggressive always-long TQQQ volatility target — development report

**Slug:** `tqqq-vol-target-aggressive`
**Window:** 2016-01-04 → 2023-12-29 (development only; 2024-2026 never loaded
or inspected)
**Harness:** `research/bt.py`, 1-minute regular-session marks, next-open fills,
2% band, 1 bp headline; 5 bp and 10 bp sensitivity. Long-only, weights ≥ 0,
sum ≤ 1.
**Files:** `HYPOTHESIS.md` (pre-registration), `strategy.py`, `result.json`.

---

## Verdict

**Pass on the development bar, and on the mandate's DD < 60% target.** At 1 bp
the promoted cell `rv20_t080` makes **40.16% CAGR / 57.77% max DD / 1.068
Sharpe**, versus the TQQQ bar of **36.72% / 82.29% / 0.82**. It still passes at
5 bp (**39.06% / 58.26% / 1.048**) and 10 bp (**37.71% / 58.87% / 1.023**).
Daily-close marks give 39.90% / 56.20% / 1.053.

The qualification is material. The CAGR edge is **+3.44 pp**, but it is not
broad alpha: the strategy **underperforms TQQQ in every bull year** (2016,
2017, 2019, 2020, 2021, 2023) and wins in 2018 and 2022. Excluding the best
year (2023) the CAGR falls to **24.57%**, below the absolute bar, though still
above TQQQ's 18.59% ex-2023. The strategy is best described as **risk-managed
TQQQ beta with a crash brake**, not as a new return source. The holdout is a
genuine coin-flip: it needs **30.51% CAGR** over 2024-2026 to match the full
37.54% bar, and its 75.8% average exposure and 0.795 monthly up-capture put it
right around that level.

| | 1 bp | 5 bp | 10 bp | TQQQ 1m | Task bar |
|---|---:|---:|---:|---:|---:|
| **CAGR** | **40.16%** | **39.06%** | **37.71%** | 36.15% | 36.72% |
| **Max DD** | **57.77%** | **58.26%** | **58.87%** | 82.29% | 82.29% |
| **Sharpe** | **1.068** | **1.048** | **1.023** | 0.801 | 0.82 |
| Sortino | 1.495 | 1.466 | 1.430 | — | — |
| Calmar (CAGR/DD) | 0.695 | 0.671 | 0.641 | 0.439 | 0.446 |
| Volatility | 38.75% | 38.75% | 38.75% | 66.55% | — |
| TQQQ exposure | 75.8% | 75.8% | 75.8% | 100% | 100% |
| Fills | 1,645 | 1,645 | 1,647 | 1 | — |
| Turnover (× start equity) | 873.6 | 837.8 | 795.7 | ~0 | — |
| Corr to TQQQ (daily) | 0.818 | 0.818 | 0.818 | 1.00 | — |
| Ending equity ($100k) | $1,481,124 | $1,391,328 | $1,287,160 | $1,175,283 | — |

`bt.stats` reports `exposure` ≈ 100% because BIL is an asset; `tqqq_exposure`
above is the economic TQQQ weight. The benchmark measured on the same 1-minute
panel is 36.15% / 82.29% / 0.801; the task's reference bar is 36.72% / 82.29% /
0.82. The candidate beats both. The daily-close benchmark is 35.98% / 81.68% /
0.799.

## 1. What the strategy does

Let `C_t` be TQQQ's adjusted daily close, `r_t = ln(C_t/C_{t-1})`, and
`σ_t = sqrt(252)·std(r_{t-19..t})`.

```
base_t  = clip(0.80 / σ_t, 0, 1)
hi15_t  = max(C_{t-14..t})
dd15_t  = 1 - C_t / hi15_t
brake_t = clip(1 - (dd15_t - 0.06) / (0.12 - 0.06), 0.25, 1)
w_t     = EMA_3(base_t · brake_t)        # span 3, causal
BIL_t   = 1 - w_t
```

The weight is set from the close of session `t` and filled at the open of
`t+1`. There is no moving-average regime, no slow trend gate, no stop-loss and
no shorting. The 3-session EMA is a turnover control: in the exploratory
raw-target run it reduced traded notional from 1,256× to 874× start equity and
raised the 10 bp CAGR from 35.57% to 37.71%; it is not a signal.

The brake is a **fast drawdown scaler**, not a binary crash stop. It is full at
a 15-session drawdown of 6% or less, falls linearly to 0.25 at 12%, and stays at
0.25 beyond. It is active often: the average weight is **75.8%**, the strategy is
at ≥99% only **46.3%** of sessions, and below 50% **26.4%** of sessions. That is
the "aggressive" shape: fully invested in calm tapes, hard cut in drawdowns.

## 2. Yearly returns

Measured from session-end equity on the 1-minute panel. The 2016 base is the
first session of the archive.

| Year | Strategy | TQQQ | Difference | Avg TQQQ weight |
|---:|---:|---:|---:|---:|
| 2016 | +17.5% | +18.6% | −1.1 pp | 82.9% |
| 2017 | +103.6% | +118.3% | −14.7 pp | 96.7% |
| 2018 | **−15.1%** | −19.6% | +4.5 pp | 67.6% |
| 2019 | +92.6% | +133.1% | −40.5 pp | 85.0% |
| 2020 | +100.7% | +109.6% | −8.9 pp | 71.1% |
| 2021 | +40.5% | +83.0% | −42.5 pp | 82.0% |
| 2022 | **−47.7%** | −79.1% | **+31.4 pp** | 40.8% |
| 2023 | +154.0% | +198.4% | −44.4 pp | 80.4% |

The shape is exactly a crash-avoidance payoff: give up 1–44 pp in bull years,
earn 31 pp back in 2022. The full-window CAGR wins because the smaller 2022
loss compounds into the 2023 recovery.

| Subperiod | Strategy CAGR / DD / Sharpe | TQQQ CAGR / DD / Sharpe |
|---|---:|---:|
| 2016–2019 | 41.12% / 38.13% / 1.188 | 48.60% / 58.0% / 1.04 |
| 2020–2021 | 65.87% / 32.04% / 1.344 | 91.47% / 69.9% / 1.21 |
| 2022–2023 | 14.50% / 50.27% / 0.537 | −22.33% / 81.0% / 0.07 |

The strategy loses to TQQQ in the two bull subperiods and wins by 36.8 pp CAGR
in 2022–2023. That is the whole trade.

## 3. Pre-registered grid and plateau

All cells use the same brake (`H=15`, 6–12%, floor 0.25) and EMA-3 smoothing.
The primary `rv20_t080` was fixed before the run as the lowest target in the
mandated 0.8–1.0 range, i.e. the most conservative point and the one that
prioritises DD < 60%.

| id | CAGR | Max DD | Sharpe | TQQQ expo | Daily-close DD | Both bar & DD<60? |
|---|---:|---:|---:|---:|---:|---|
| **`rv20_t080` (primary)** | **40.16%** | **57.77%** | **1.068** | **75.8%** | **56.20%** | **yes** |
| `rv20_t090` | 39.39% | 59.78% | 1.041 | 76.7% | 58.15% | yes |
| `rv20_t100` | 38.60% | 61.41% | 1.018 | 77.3% | 59.92% | no on 1m; yes on daily |
| `rv10_t080` | 39.66% | 61.20% | 1.055 | 76.0% | 59.73% | no |
| `rv60_t080` | 36.26% | 58.89% | 0.999 | 75.3% | 57.39% | no (CAGR −0.46 pp) |
| `park20_t080` | 38.60% | 61.95% | 1.012 | 77.6% | 60.24% | no |
| `ewma_t080` | 38.75% | 59.14% | 1.043 | 75.8% | 57.77% | yes |
| `rv20_t080_nocut` | 38.28% | 78.33% | 0.854 | 95.5% | 77.66% | no (DD) |

**Plateau:** 7 of 8 cells pass the formal program bar; 6 of the 7 cut cells pass
(the RV60 cell misses by 0.46 pp); **3 of 8 meet both** the program bar and the
DD < 60% target at 1 bp (`rv20_t080`, `rv20_t090`, `ewma_t080`). The target
dimension is a clean monotone trade-off — 0.80/0.90/1.00 give 40.16/39.39/38.60%
CAGR and 57.77/59.78/61.41% DD. The 1.00 cell is 1.41 pp above the DD target on
1-minute marks but 59.92% on daily closes, so the DD constraint is
mark-frequency-sensitive at the top of the range.

The primary is the **best CAGR cell of the 8-cell grid**. That is a warning
sign and is disclosed in `result.json` (`primary_is_best_cagr: true`). The
defence is that the 0.90 cell is only 0.77 pp behind and also passes both tests,
and the 0.90/1.00 cells still pass the formal program bar; the result is not a
single-cell artifact. The DD < 60% margin, however, is target-sensitive.

## 4. Neighbour robustness

All rows are 1-minute marks at 1 bp, unrounded from `result.json`.

| Family | Cell | CAGR | Max DD | Sharpe | TQQQ expo |
|---|---|---:|---:|---:|---:|
| Target | 0.70 | 40.16% | 56.04% | 1.088 | 74.3% |
| Target | 0.75 | 40.46% | 56.51% | 1.080 | 75.1% |
| Target | 0.85 | 39.93% | 58.88% | 1.060 | 76.3% |
| Target | 0.95 | 38.90% | 60.78% | 1.030 | 77.1% |
| RV lookback | RV5 | 39.20% | 59.11% | 1.045 | 76.0% |
| RV lookback | RV120 | 36.59% | 59.07% | 1.008 | 75.1% |
| Parkinson | PARK10 | 40.22% | 61.67% | 1.040 | 77.7% |
| Parkinson | PARK60 | 38.33% | 62.22% | 1.010 | 77.4% |
| Blend | RV10+RV60 | 38.17% | 60.49% | 1.030 | 75.7% |
| Brake H | 10 | 37.92% | 69.33% | 1.000 | 78.8% |
| Brake H | 20 | 38.92% | 56.67% | 1.065 | 73.6% |
| Brake H | 30 | 33.94% | 54.70% | 0.996 | 70.2% |
| Brake start/floor | 5% / 0.20 | 38.92% | 54.81% | 1.070 | 73.4% |
| Brake start/end/floor | 6% / 15% / 0.25 | 39.80% | 59.77% | 1.044 | 77.6% |
| Brake start/floor | 8% / 0.30 | 40.94% | 61.81% | 1.048 | 79.1% |
| Brake start/floor | 4% / 0.10 | 37.09% | 50.77% | 1.070 | 69.7% |
| Brake start/floor | 10% / 0.40 | 40.11% | 66.93% | 0.970 | 85.3% |
| Smoothing | raw (no EMA) | 39.39% | 58.78% | 1.051 | 75.8% |
| Smoothing | EMA-2 | 39.98% | 58.26% | 1.070 | 75.8% |
| Smoothing | EMA-5 | 39.85% | 56.17% | 1.060 | 75.8% |

The brake is a genuine plateau in the **15–20 session** region: H20 gives
38.92% / 56.67%, H15 gives 40.16% / 57.77%, and H30 fails the CAGR bar. H10 is
too noisy to protect the 2022 grind (DD 69.33%). The start/floor frontier is
also smooth: a more defensive brake (4%/0.10) gives 37.09% / 50.77%; a looser
one (8%/0.30) gives 40.94% / 61.81%. The primary sits inside this plateau. It
is **not** the best point on the wider target sweep: the out-of-grid 0.70 and
0.75 targets are marginally better on both axes (40.16% / 56.04% and 40.46% /
56.51%). They are disclosed but not promoted, to avoid selecting the best
out-of-grid cell on the evaluation window. The flatness from 0.70 to 0.85 is
itself the finding: the exact nominal target is not economically important.

## 5. Is the target just leverage?

No weight exceeds 1, so the strategy is not levered above TQQQ. The average
TQQQ weight is 75.8%. The constant controls show that leverage/constant
exposure cannot reproduce the result:

| Constant TQQQ | CAGR | Max DD | Sharpe |
|---:|---:|---:|---:|
| 60% | 27.94% | 60.78% | 0.82 |
| 70% | 30.71% | 67.44% | 0.81 |
| 80% | 33.10% | 73.02% | 0.81 |
| 85% | 33.68% | 76.05% | 0.80 |
| 90% | 35.41% | 77.88% | 0.81 |
| 95% | 35.74% | 80.38% | 0.80 |
| 100% | 36.15% | 82.29% | 0.80 |

Every constant fails the CAGR bar; every constant of 60% or more has a
drawdown above 60%. The **matched constant** at the primary's average weight
(75.8%) makes **31.93% / 69.49% / 0.800** on daily marks, versus the strategy's
**39.91% / 56.20% / 1.053**. Same average exposure, 8.0 pp more CAGR and 13.3 pp
less DD: the timing, not the exposure, is the edge.

The honest comparison to the moderate-target sibling is less flattering. A
supplementary run of a 0.45 target with no brake (the earlier
`always-long-vol-target` design) makes **39.47% / 58.94% / 0.999** with 79.5%
average exposure on this harness. The aggressive candidate is only **+0.69 pp
CAGR and −1.17 pp DD** better at 1 bp, and is slightly worse at 10 bp (37.71% vs
38.23% for the sibling's frozen result). The high nominal target is **not** a
large improvement over a moderate vol target. Its distinct feature is the shape
— full exposure in calm tapes, a hard cut in drawdowns — not a new risk/return
frontier.

## 6. Is the crash cut the real edge?

The clean decomposition uses the same target, estimator and EMA-3 smoothing:

| Variant | CAGR | Max DD | Sharpe | TQQQ expo |
|---|---:|---:|---:|---:|
| No cut (`rv20_t080_nocut`) | 38.28% | 78.33% | 0.854 | 95.5% |
| **Fast drawdown brake** | **40.16%** | **57.77%** | **1.068** | **75.8%** |
| Binary cut at 12% DD | 36.61% | 65.23% | 0.945 | 81.7% |
| Vol-acceleration cut only | 41.24% | 77.04% | 0.913 | 92.6% |

The brake's **robust contribution is the drawdown reduction: −20.6 pp** at a
small CAGR cost/benefit that depends on the smoothing. With the pre-registered
EMA-3 it adds +1.88 pp CAGR; without the EMA the raw no-cut control makes
39.54% / 78.36% and the raw cut 39.39% / 58.78%, i.e. the cut costs −0.15 pp
CAGR for −19.6 pp DD. The truth is: **the cut is the real DD edge; it is not a
reliable CAGR engine.** The CAGR edge over buy-and-hold comes mainly from the
vol target's modest de-risking in the worst vol states, and from avoiding the
2022 loss.

The cut-shape rivals confirm that the drawdown state is special. A **binary**
cut at 12% is worse on both axes (36.61% / 65.23%): it re-enters too early and
whipsaws. A **vol-acceleration-only** cut raises CAGR to 41.24% but leaves the
DD at 77.04%: it catches the acute 2020 spike but not the slow 2022 grind. The
continuous 15-session drawdown brake is what handles both.

## 7. Placebos, causality and performance cuts

**Placebos (daily marks, 500 circular shifts of the daily weight path).** The
real daily path makes 39.91% / 56.20% / 1.053. The matched constant makes
31.93% / 69.49% / 0.800. The shift distribution has mean CAGR 28.27% (p05
16.45%, p50 28.22%, p95 41.13%), mean DD 73.32% (p50 73.77%) and median Sharpe
0.732. **6.6%** of shifts beat the real CAGR; **0.0%** beat both the real CAGR
and the real DD. The alignment of the weights with returns matters, and the DD
improvement is far outside the placebo distribution.

**Lag placebo.** Delaying the weight path by 5 sessions gives 35.26% / 54.99%
(Sharpe 0.928); 20 sessions gives 23.90% / 68.17% (0.684); 60 sessions gives
25.18% / 69.40% (0.688). A 5-day lag still works because the brake is a slow
state; 20+ days loses the edge. The signal is not a same-day artifact.

**Causal truncation.** Rebuilding the weights on panels truncated at
2018-12-31, 2020-03-12 11:07, 2021-12-31 and 2022-09-13 gives **0.0 maximum
absolute difference** on both the minute and daily panels at all four cuts. This
is the bug that rejected the earlier always-long vol-target (it used the
panel's last timestamp to set the daily signal end, so a mid-day truncation
changed the same morning's weights); this implementation loads the daily signal
only through the session **before** the panel's last session, so the truncated
panel cannot change any pre-cut weight.

**Performance cuts.**

| Cut | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Ex-best year (2023, +154.0%) | 24.57% | 56.36% | 0.792 |
| Ex-2020 | 28.30% | 56.36% | 0.891 |
| Ex-2022 | 51.84% | 37.96% | 1.330 |
| Ex-best 20 sessions | 16.22% | 70.44% | 0.592 |
| Start 2017-01-03 | 43.23% | 57.77% | 1.113 |
| Start 2018-01-02 | 35.03% | 57.77% | 0.943 |

The ex-best-year and ex-best-20 rows are the weak points. The strategy gives up
a lot in strong up years and depends on participating in the 2023 recovery and
on a small number of large up days. The start-2018 CAGR is below the absolute
36.72% bar, but it still beats TQQQ's 27.44% / 81.7% over 2018-2023. The
drawdown improvement is robust across all cuts; the CAGR is not.

## 8. Holdout arithmetic and honest verdict

The dev multiple is 14.81× over 7.984 years. Matching the full 2016-2026 TQQQ
bar (37.54% CAGR, 31.27× over 10.801 years) requires **2.111× over the 2.806
holdout years, i.e. 30.51% CAGR**. The strategy's 75.8% average exposure and
0.795 monthly up-capture imply roughly 30–31% in a holdout where TQQQ compounds
near 39.5%, before any brake cost. That is **right at the required level** — a
real chance, not a comfortable margin.

What would make the holdout fail:

- a strong, low-drawdown bull market in which the brake's 1–44 pp annual
  give-up is not repaid by a crash (the 2021 problem: +40.5% vs +83.0%);
- another 2023-like recovery where the strategy participates but lags TQQQ by
  44 pp;
- a repeat of the 2018 start: 35.03% dev CAGR is below the absolute bar.

What would make it succeed:

- a 2022-like drawdown, where the strategy loses about half of TQQQ's loss;
- a 2020-like crash, where the brake's 31% loss vs TQQQ's 70% is worth years of
  beta;
- a holdout with TQQQ above ~40%, where the 75.8% average exposure alone can
  clear 30.5%.

**Bottom line.** This is a valid, causal, mandate-compliant strategy that
passes the development bar and the DD < 60% target at 1, 5 and 10 bp. It is
**not** evidence that aggressive 0.8–1.0 vol targets are superior: the nominal
target is nearly flat from 0.70 to 0.85, the realised exposure is 75.8%, and the
result is only ~0.7 pp CAGR better than a moderate 0.45 target. The crash brake
is the real DD edge, worth about 20 pp of drawdown; the CAGR edge is modest and
concentrated in 2022–2023. Promote it to the one-shot holdout as a
**risk-managed TQQQ beta / crash-hedge**, with the expectation that it will
underperform in a strong bull and outperform in a drawdown. Do not expect the
40% dev CAGR to repeat.

## 9. Data and reproducibility

- Development only: `bt.panel(("QQQ","TQQQ","BIL"), "2016-01-04", "2023-12-29",
  "1min")` and `"1D"`; the daily reader filters `date < 2023-12-30`.
- The daily yahoo archive starts 2015-01-02 and is used only to warm the
  volatility and drawdown estimators; no 2024-2026 data is read.
- Run from the repo root:

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/tqqq-vol-target-aggressive/strategy.py
```

- `result.json` contains the full grid, neighbours, constants, placebos, cut
  tests, subperiods, episodes and diagnostics. All weights are long-only,
  sum ≤ 1, and set from completed daily bars with next-open fills.
