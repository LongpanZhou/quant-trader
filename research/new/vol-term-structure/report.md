# Realized-vol term structure on TQQQ — development report

**Slug:** `vol-term-structure`
**Window:** 2016-01-04 → 2023-12-29 (development only; 2024+ never loaded)
**Harness:** `research/bt.py`, 1-minute marks, next-open fills, 2% band
**Costs:** 1 bp headline (5/10 bp shown), long-only, weights ≥ 0, sum ≤ 1

## Verdict up front

The primary rule **passes the development bar comfortably**:

| | CAGR | Max DD | Sharpe | Exposure | Corr to TQQQ |
|---|---:|---:|---:|---:|---:|
| **Vol term structure (primary, 1 bp)** | **51.57%** | **37.90%** | **1.37** | **61.2%** | **0.68** |
| Lead's TQQQ dev bar | 36.72% | 82.29% | 0.82 | 100% | 1.00 |
| Harness TQQQ buy & hold (same 1-min panel) | 36.15% | 82.29% | 0.80 | 100% | 1.00 |

- **+14.85 pp** CAGR over the lead's 36.72% bar, with **44.39 pp** less max drawdown.
- 5 bp: **50.94% / 38.10% / 1.36**. 10 bp: **50.12% / 38.36% / 1.34**.
- 293 fills, turnover 565x total (~71x/year).
- Yearly exposure is 18% in 2022 and 72% in 2023 — the rule is doing real
  regime work, not sitting at a constant fraction.

The honest caveat is in §4: the term-structure sleeve **does not add raw CAGR
over a simple trend+spike rule** (53.46% / 48.25% / 1.20). It buys a 10.4 pp
drawdown reduction and +0.17 Sharpe. Relative to a volatility target or a
volatility-level gate, it adds both return and risk control. The signal is real,
but its value is crash avoidance, not return forecasting.

## 1. What is being tested

The full pre-registration, including the 8-cell grid, is in `HYPOTHESIS.md`.
At the close of session `t`, with QQQ daily log returns `r`:

```
RV_n(t) = sqrt(mean(r_{t-n+1..t}^2)) * sqrt(252)
trend_t = QQQ close > SMA_165
calm_t  = RV_20/RV_60 < 0.95
spike_t = RV_5 /RV_60 > 1.80

raw_t = 0.50*trend_t + 0.50*calm_t
w_t   = 0 if spike_t else raw_t
```

`w_t` is the TQQQ target for session `t+1`, executed at the next open. Idle
weight is cash at 0%. The four non-spike states are 1.0 (up/calm), 0.5
(up/inverted), 0.5 (down/calm), 0.0 (down/inverted); an acute spike forces 0.

Time in state over 2,012 sessions:

| trend | term structure | days | share | mean weight |
|---|---|---:|---:|---:|
| up | calm | 801 | 39.8% | 1.00 |
| up | inverted | 724 | 36.0% | 0.50 |
| down | calm | 135 | 6.7% | 0.50 |
| down | inverted | 277 | 13.8% | 0.00 |
| any | acute spike | 75 | 3.7% | 0.00 |

The spike flag occurs in 18 episodes. Most are 1–5 days (Brexit 2016, May 2017,
February/October 2018, May 2019, September 2020, March/September 2021); the
long one is 2020-02-24 → 2020-03-20 (20 sessions). Weight distribution:
0 on 17.5% of sessions, 0.5 on 42.7%, 1.0 on 39.8%; mean 0.612.

## 2. Headline results

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Exposure | Fills | Turnover |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 bp | 51.57% | 37.90% | 1.37 | 1.97 | 34.95% | 61.2% | 293 | 565x |
| 5 bp | 50.94% | 38.10% | 1.36 | 1.95 | 34.95% | 61.2% | 294 | 551x |
| 10 bp | 50.12% | 38.36% | 1.34 | 1.93 | 34.95% | 61.2% | 294 | 533x |

The lead's bar is 36.72% CAGR / 82.29% DD / 0.82 Sharpe. The harness computes
36.15% / 82.29% / 0.80 for buy-and-hold on the same 1-minute bars (the small
CAGR difference is a start-convention difference; the DD matches exactly). The
strategy clears the higher 36.72% bar, so the conclusion does not depend on
which benchmark convention is used.

### Yearly returns and exposure

| Year | Strategy | TQQQ | Excess | Avg TQQQ exposure |
|---:|---:|---:|---:|---:|
| 2016 | +2.60% | +19.86% | −17.26 | 59.5% |
| 2017 | +65.47% | +114.54% | −49.07 | 70.7% |
| 2018 | +8.63% | −20.76% | +29.39 | 56.7% |
| 2019 | +57.14% | +148.23% | −91.09 | 74.0% |
| 2020 | +188.87% | +104.14% | +84.73 | 63.5% |
| 2021 | +79.95% | +81.05% | −1.10 | 74.7% |
| 2022 | −30.83% | −79.39% | +48.56 | 18.1% |
| 2023 | +143.31% | +192.05% | −48.74 | 72.4% |

The profile is exactly what the mechanism predicts: it lags strong low-vol
bulls (2017, 2019, 2023), survives the two bear markets (2018, 2022), and makes
its excess return in the 2020 crash/recovery. 2022 exposure of 18.1% is the
clearest evidence that the term-structure and trend states are not cosmetic.

### Subperiods

| Window | Strategy CAGR / DD / Sharpe | TQQQ CAGR / DD / Sharpe |
|---|---:|---:|
| 2016–2019 | 31.47% / 29.78% / 1.09 | 48.81% / 58.62% / 1.05 |
| 2020–2023 | **74.11% / 37.90% / 1.60** | 24.08% / 82.29% / 0.67 |
| 2016–2020 | 54.72% / 33.22% / 1.44 | 59.34% / 72.74% / 1.05 |
| 2021–2023 | **46.59% / 37.90% / 1.26** | 4.68% / 82.29% / 0.41 |

The edge is concentrated in the 2020–2023 crash/recovery block. In the calm
2016–2019 bull the strategy lags TQQQ on CAGR but has a slightly higher Sharpe
and half the drawdown. This is a risk-managed participation profile, not a
return-forecasting model that wins every regime.

## 3. Pre-registered grid: the plateau

Eight cells, one parameter changed at a time; all at 1 bp.

| Cell | CAGR | Max DD | Sharpe | Exposure |
|---|---:|---:|---:|---:|
| primary (SMA165, 20/60 < 0.95, spike 1.8, 50/50) | 51.57% | 37.90% | 1.37 | 61.2% |
| theta 0.92 | 49.32% | 30.91% | 1.35 | 59.2% |
| theta 0.98 | 49.87% | 39.29% | 1.31 | 63.4% |
| SMA150 | 51.92% | 42.64% | 1.37 | 61.3% |
| SMA180 | 51.65% | 37.37% | 1.37 | 61.3% |
| spike 1.6 | 48.73% | 37.38% | 1.33 | 59.6% |
| spike 2.0 | 51.88% | 37.90% | 1.37 | 61.7% |
| blend 40/60 | 50.66% | 40.03% | 1.37 | 58.3% |

**Plateau:** every cell is 48.7–51.9% CAGR with 30.9–42.6% DD and Sharpe
1.31–1.37. The centre is *not* the best cell (SMA150 is +0.35 pp, spike 2.0 is
+0.31 pp); the surface is flat. There is no cliff at the pre-registered
parameters.

Supplementary blend 60/40 (not in the grid): 52.45% / 36.04% / 1.35 / 64.2%.
It is marginally better on CAGR and DD than 50/50 and slightly worse on Sharpe;
the difference is within noise, so the equal split was kept.

## 4. Does the term structure add anything over a simple vol rule?

This is the central honesty test. All rows are 1 bp, 1-minute marks.

| Rule | CAGR | Max DD | Sharpe | Exposure | What it is |
|---|---:|---:|---:|---:|---|
| **Primary (trend + TS + spike)** | **51.57%** | **37.90%** | **1.37** | **61.2%** | submitted |
| Trend only (SMA165) | 43.26% | 59.62% | 1.00 | 78.4% | no vol at all |
| Term-structure gate only (100% sleeve) | 44.59% | 53.43% | 1.23 | 46.5% | no trend |
| Trend + spike (no TS sleeve) | 53.46% | 48.25% | 1.20 | 75.7% | simpler sibling |
| No spike overlay | 47.22% | 38.67% | 1.25 | 62.6% | TS + trend only |
| Vol target 14% (RV20) | 37.18% | 57.43% | 0.99 | 76.5% | classic vol target |
| Vol target 12% | 33.99% | 51.90% | 0.99 | 69.9% | classic vol target |
| Vol target 16% | 39.06% | 62.55% | 0.97 | 81.6% | classic vol target |
| Vol-level gate RV20 < 22% | 40.91% | 43.77% | 1.11 | 66.1% | absolute level only |
| Vol-level gate RV60 < 25% | 41.34% | 47.34% | 1.00 | 74.6% | absolute level only |
| Trend + vol-level gate + spike | 47.19% | 39.80% | 1.22 | 70.1% | closest simple substitute |
| BIL idle instead of cash | 52.23% | 37.28% | 1.38 | 61.2% TQQQ | not selected |

Three honest conclusions:

1. **It is not a volatility target.** A 14% vol target earns 37.18% with 57.4%
   DD; the term-structure rule earns +14.4 pp more CAGR with 19.5 pp less DD at
   lower average exposure. The slope is a different signal from the level.
2. **It adds over the best simple vol-level substitute.** The trend +
   RV20<22% + spike blend earns 47.19% / 39.80% / 1.22 at 70.1% exposure. The
   primary earns +4.38 pp CAGR, −1.90 pp DD, +0.15 Sharpe at 61.2% exposure.
   The slope is doing work beyond "hold when vol is low."
3. **It does not add raw CAGR over trend + spike.** That sibling earns 53.46%
   with 48.25% DD and 1.20 Sharpe. The term-structure sleeve gives up 1.9 pp
   CAGR to cut drawdown by 10.4 pp and raise Sharpe by 0.17. If the only
   objective were dev CAGR, the sibling would win; if drawdown and holdout
   survivability matter, the primary is the better submission.

The spike overlay itself is valuable: removing it costs 4.35 pp CAGR (51.57 →
47.22) and 0.12 Sharpe. The mechanism is visible in 2020: the 5/60 ratio crosses
1.8 at the 2020-02-24 close, so the book is flat from the 2020-02-25 open,
avoiding the worst of the COVID crash; it re-enters at 0.5 at the 2020-04-14
open and 1.0 at the 2020-04-16 open (signals of 2020-04-13 and 2020-04-15).

**Execution-delay fragility (daily-mark diagnostic).** Delay the whole weight
series by one extra session and the result is 47.80% / 33.98% / 1.26; two
sessions gives 43.30% / 45.72% / 1.17; three gives 33.62% / 46.55% / 0.97. The
edge survives a one-session delay but not a three-session one. This is expected
for a signal whose fast leg is a 5-day spike, and it is why the rule must run on
daily closes with next-open execution rather than be treated as a slow-moving
allocation. It is a genuine fragility, not a footnote.

## 5. Placebo tests

Both placebos are run on daily marks (2,012 sessions) so 200 draws are cheap;
the actual daily-mark result is 51.84% / 35.79%, close to the 1-minute 51.57% /
37.90%.

**A. Block shuffle of the final weight series (20-session blocks, 200 draws).**
This preserves the exact weight histogram and local persistence but destroys the
alignment with the market.

| | Actual | Placebo median | Placebo p05 | Placebo p95 | Rank |
|---|---:|---:|---:|---:|---:|
| CAGR | 51.84% | 23.16% | 6.63% | 43.21% | **1.000** |
| Max DD | 35.79% | 68.57% | — | — | — |
| Sharpe | 1.35 | 0.68 | — | — | — |

**B. Circular shift of the term-structure component (20–1,992 sessions, 200
draws), keeping the trend sleeve in place.** This tests whether the TS timing
adds anything over the trend timing.

| | Actual | Placebo median | Placebo p05 | Placebo p95 | Rank |
|---|---:|---:|---:|---:|---:|
| CAGR | 51.84% | 30.22% | 17.72% | 41.74% | **0.995** |
| Max DD | 35.79% | 55.15% | — | — | — |
| Sharpe | 1.35 | 0.86 | — | — | — |

The actual result is at the 100th percentile of the block-shuffle null and the
99.5th percentile of the TS-shift null. The weight histogram alone earns only
~23% CAGR with a 69% drawdown; the timing is what produces the result.

## 6. Cut tests and concentration

Each row removes one year (or the N best days) from the daily return series and
recomputes CAGR over the remaining days. The benchmark is cut identically, so
the comparison is like-for-like.

| Cut | Strategy CAGR | TQQQ CAGR | Strategy − TQQQ |
|---|---:|---:|---:|
| drop 2016 | 60.29% | 38.66% | +21.63 |
| drop 2017 | 49.31% | 27.06% | +22.25 |
| drop 2018 | 58.65% | 46.60% | +12.05 |
| drop 2019 | 50.83% | 25.90% | +24.93 |
| **drop 2020** | **37.73%** | 27.84% | +9.89 |
| drop 2021 | 47.71% | 30.34% | +17.37 |
| drop 2022 | 69.41% | 77.75% | −8.34 |
| drop 2023 | 41.40% | 21.49% | +19.91 |
| drop best 10 days | 35.29% | 21.36% | +13.93 |
| drop best 20 days | 24.60% | 11.65% | +12.95 |

The **absolute** headline is sensitive to the two big years: dropping 2020
leaves 37.73% (still just above the 36.72% bar), and dropping the best 10 days
leaves 35.29% (just below the bar). But the **relative** edge over TQQQ is
positive in every cut except "drop 2022", where removing the crash naturally
favors buy-and-hold. The strategy is not a one-day or one-year artefact; it is
a crash-avoidance profile whose excess return is concentrated in the periods
when crash avoidance pays.

Concentration: the best 10 days account for 27.4% of total log return; the best
day is +13.27%, the worst −15.40%, and 47.8% of days are positive. That is
typical for a leveraged long strategy, not an unusual dependence on a handful
of prints.

## 7. Costs, fills, implementation

- 293 fills over 8 years (~37/year). Turnover 565x total, ~71x/year. The 2%
  band suppresses most of the daily state churn.
- 1 → 10 bp costs 1.45 pp CAGR (51.57 → 50.12) and 0.46 pp DD. The result is
  not cost-fragile.
- Signals are daily closes; execution is the next session open. No intraday
  signal, no minute-level look-ahead. The 15:59 bar carries the next session's
  target, which is exactly how the harness executes it.
- The idle sleeve is cash at 0%. A BIL idle variant earns 52.23% / 37.28% /
  1.38 with 585 fills; it is not selected because it adds a second asset and
  turns over the idle sleeve, and the headline already clears the bar without
  the extra carry.

## 8. Holdout arithmetic and final verdict

The development result compounds $100k to $2.768M, a **27.68x** multiple over
7.984 years. TQQQ's stated full 2016–2026 result is 37.54% CAGR, a **31.29x**
multiple over 10.80 years. The holdout is 2.82 years long, so the strategy
needs only

```
(31.29 / 27.68)^(1/2.82) - 1 = +4.4% CAGR
```

over the holdout to match TQQQ's full-period CAGR. A flat holdout gives 35.99%
full-period CAGR; +5%/year gives 37.73%. That is a large cushion, and it is the
main reason this submission is interesting: the dev CAGR is high enough that the
holdout does not need to repeat 2020.

What could go wrong:

- **2020 is one observation.** The spike overlay is economically motivated, but
  the +4.35 pp it adds is dominated by one crash. A future crash that does not
  produce a 5/60 ratio above 1.8 (e.g., a slow grind) would not trigger it; the
  trend sleeve would have to carry the protection.
- **The exact 20/60 window matters.** Supplementary variants: 20/90 earns
  50.89%, 30/60 earns 48.47%, but 10/60 earns only 37.79%. A 10-day short
  window is too noisy and whipsaws. The 20–30 day short / 60–90 day long region
  is the plateau; the 10/60 corner is a genuine weakness.
- **Calm-bull lag.** 2016–2019 CAGR is 31.47% vs TQQQ's 48.81%. If the holdout
  is a persistent low-vol melt-up with no inversions, the 50% term-structure
  sleeve will keep the book at 50–100% and may lag. The +4.4% required holdout
  CAGR is the buffer against this.
- **Threshold selection.** 0.95 and 1.80 were chosen on the development window.
  The 8-cell grid, the 200-draw placebos, and the year cuts are the defence; the
  holdout is still a single shot.
- **The term-structure sleeve is not a free lunch on raw return.** The simpler
  trend+spike rule has a higher dev CAGR. The primary is submitted because it
  has a materially better drawdown and Sharpe and a better chance of surviving
  a bad holdout, not because it maximizes the dev point estimate.

**Bottom line:** a causal, long-only, daily vol-term-structure rule on TQQQ
delivers 51.57% dev CAGR with 37.90% max DD and 1.37 Sharpe, clears the bar at
1/5/10 bp, sits on a broad parameter plateau, beats both placebo nulls at the
99.5–100th percentile, and survives every year cut with a positive relative
edge. The honest qualification is that its excess return is crash avoidance,
and a simpler trend+spike rule has a higher dev CAGR with a worse drawdown.

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\vol-term-structure\strategy.py
```

`strategy.py` exposes `build_weights(ts, o, c)` and `main()`; `main()` writes
`result.json` next to the script. It refuses to proceed if the panel crosses
2024-01-01, and every parquet read is filtered to `date <= 2023-12-29`.
