# Round 2, agent 11: blending the winner with the round-1 ensemble

**Verdict: no strict dominance. The best blend is a 75/25 winner/ensemble blend
(`WE75`), which meets target #2 (lower drawdown, CAGR within 2 pp) on both windows
at 1 bp, and is the only one of the three headline blends (WE75, IV2, IV3) that
also meets it at 5 bp and 10 bp.**
At 5 bp and 10 bp it outright dominates the winner on the 10-year window: higher
CAGR *and* lower drawdown.

| Window | Cost | **WE75 CAGR / DD** | Winner CAGR / DD | TQQQ CAGR / DD |
|---|---:|---:|---:|---:|
| 10y (2017-01-03 → 2026-10-23) | 1 bp | **58.42% / 41.18%** | 58.80% / 44.56% | 39.28% / 81.68% |
| 10y | 5 bp | **54.91% / 43.39%** | 54.60% / 47.08% | — |
| 10y | 10 bp | **50.63% / 46.04%** | 49.50% / 50.06% | — |
| 5y (2021-10-25 → 2026-10-23) | 1 bp | **47.92% / 32.33%** | 49.88% / 33.49% | 13.47% / 81.68% |
| 5y | 5 bp | **44.70% / 32.96%** | 45.89% / 34.13% | — |
| 5y | 10 bp | **40.77% / 33.74%** | 41.05% / 34.93% | — |

The 5-year CAGR gap at 1 bp is −1.96 pp: inside the 2 pp rule by four hundredths
of a point. That is not a comfortable margin, and it is the binding constraint.
On the 10-year window the blend gives up only 0.38 pp of CAGR and cuts the max
drawdown by 3.38 pp at 1 bp, and it wins on both metrics at 5 bp and 10 bp.

Why the crossover with cost: the winner trades **17,331×** starting equity over
10 years (657 fills, mostly 4% stop round-trips); WE75 trades **14,160×** (903
fills) because only the 25% ensemble sleeve changes when the two disagree on an
intraday exit. That is enough to flip the 10-year comparison by 5 bp.

**What was tested and rejected:** strict dominance (never achieved), fixed
50/50 (fails on 5-year CAGR), inverse-volatility blends with momentum
(best 1 bp numbers, but cost-fragile), drawdown throttles (catastrophic), and
volatility targeting (fails the 2 pp rule). Details in §6.

---

## 1. Mandate and approach

Round 1 produced a clear winner: daily QQQ 165-day SMA regime plus an armed 4%
minute stop on TQQQ (58.80%/44.56% 10y, 49.88%/33.49% 5y at 1 bp). The mandate
here was to blend it with the round-1 ensemble (trend + volatility budget + 1m
crash vote), optionally with intraday momentum and intraday mean reversion, using
only causal weights (trailing volatility/drawdown), and to test:

1. fixed 50/50,
2. inverse-volatility weighting,
3. drawdown-throttled blends.

All results use the shared `research/bt.py` harness conventions: adjusted local
1-minute QQQ/TQQQ/BIL data, regular session only, weights set at bar *i* and
filled at the open of bar *i+1*, 2% rebalance band, long-only, weights sum to 1.
Headline drawdowns are 1-minute marks, the stricter convention used by the
winner's report. Year-by-year uses the first/last bar of each calendar year (the
harness `yearly` convention); rolling 3-year tables use 15:59 daily marks.

**A causality bug was found and fixed during the study.** My first inverse-vol
implementation paired a 20-day volatility computed through day *d* with day *d*
itself (a positional `zip` over arrays of different length), i.e. a one-day
look-ahead. It reported IV2 at 60.70%/41.90% and 51.54%/31.53%. The corrected
mapping (daily returns indexed by their end date, `shift(1)`) reports
58.50%/41.83% and 49.43%/31.56%. All numbers in this report are post-fix. The
truncation test in `strategy.py` confirms that the allocation before 2022-01-03
is unchanged when the panel is cut at 2022-01-03 (`max abs diff = 0.0`).

---

## 2. Idea and literature

The result is a textbook risk-reduction blend, not a new alpha source. Three
strands of evidence motivate it:

1. **Rebalancing/ensemble premium.** A periodically rebalanced mix of two
   strategies can have a higher geometric return than the weighted average of
   the components, because rebalancing sells the recent winner and buys the
   recent laggard (a concave payoff). Newfound's *Ensembles and Rebalancing*
   shows that the optimal blend of two strategies can outperform either one;
   the effect is largest when the components have similar Sharpe ratios and
   imperfect correlation.
   [Newfound, 2020](https://blog.thinknewfound.com/2020/02/ensembles-and-rebalancing)
   The underlying mathematics is in *Diversification Returns, Rebalancing
   Returns and Volatility Pumping* ([SSRN 2311240](https://ssrn.com/abstract=2311240))
   and *Demystifying Rebalancing Premium*
   ([SSRN 2927791](https://ssrn.com/abstract=2927791)).
2. **Inverse-volatility / naive risk parity.** Weighting sleeves inversely to
   their trailing volatility equalises risk contributions without estimating
   expected returns. It is the simplest robust risk-based allocation and is
   hard to beat out of sample; DeMiguel, Garlappi & Uppal (2009) show that naive
   1/N often matches or beats optimised portfolios
   ([DOI 10.1093/rfs/hhm075](https://doi.org/10.1093/rfs/hhm075)). See also
   *Advances in Portfolio Risk Control: Risk! Parity?*
   ([SSRN 2259041](http://ssrn.com/abstract=2259041)) and Quantpedia's overview
   ([link](https://quantpedia.com/risk-parity-asset-allocation/)).
3. **Why drawdown throttling is dangerous.** Cutting exposure after a loss is a
   stop-loss at the portfolio level. The evidence is mixed at best: stop-loss
   rules can reduce tail risk but often reduce returns, especially when the
   underlying has positive drift and volatility clustering
   ([SSRN 2695383](http://ssrn.com/abstract=2695383)). Drawdown-control
   frameworks exist ([Macrosynergy](https://macrosynergy.com/research/drawdown-control/);
   [Boyd et al., Stanford](https://stanford.edu/~boyd/papers/pdf/multiperiod_portfolio_drawdown.pdf)),
   but they need a drawdown budget calibrated to the strategy's own volatility.
   My results in §6 are a clean example of the failure mode: with 45% annual
   volatility, a 10–15% drawdown threshold is almost always active.

The economic story for *this* pair is specific. Both sleeves hold TQQQ in the
same 165-day risk-on regime, so they agree most of the time and the blend is
100% TQQQ. They disagree when the ensemble's 20-day volatility budget or 1-minute
crash vote de-risks to BIL while the winner stays long (or when the winner's 4%
stop fires and the ensemble stays long). The blend is therefore a **partial
de-risking rule on disagreement**, not a diversifier across asset classes. That
is why it cuts drawdown cheaply but cannot raise the 5-year CAGR: 2021–2026 was
mostly a strong bull, and the ensemble's de-risking was a drag.

---

## 3. Exact rules

### Sleeves (all long-only QQQ/TQQQ/BIL, next-bar-open fills)

| Sleeve | Rules | Source |
|---|---|---|
| **Winner** (W) | QQQ prior close > 165-day SMA → 100% TQQQ, else BIL. On risk-on days, arm a 4% stop from the session open only when QQQ's first-minute close < its prior 20-day SMA × 1.01; if armed and TQQQ closes 4% below the open, sell at the next minute's open and stay BIL for the rest of the session and night. | `research/agents/daily-regime-minute-entry/strategy.py` |
| **Ensemble** (E) | QQQ 165-day trend gate; 20-day realised QQQ vol ≤ 1/3, else BIL; same-session crash vote (QQQ ≤ −3% from prior close and trend/momentum/RSI vote ≤ −2) exits TQQQ to BIL for the rest of the session. | `research/agents/ensemble-signals/strategy.py` |
| **Momentum** (M) | 165-day regime; hold TQQQ overnight and in the first hour; if QQQ first-hour return (09:30→10:29) < 0, move to cash at the 10:30 open and re-enter TQQQ at 15:59. | `research/agents/intraday-momentum/strategy.py` |

### Blends

Let `w_W(i)`, `w_E(i)`, `w_M(i)` be each sleeve's (n,3) target weight row at bar
*i*. All blends are convex combinations:

```
w_blend(i) = a_W(i)·w_W(i) + a_E(i)·w_E(i) + a_M(i)·w_M(i),   a_j ≥ 0, Σa_j = 1
```

- **WE75 (primary):** `a_W = 0.75`, `a_E = 0.25`, `a_M = 0`.
- **IV2 / IV3:** `a_j(i)` ∝ 1/σ_j(i), where σ_j is the trailing 20-day standard
  deviation of sleeve *j*'s standalone daily equity returns, **shifted one day**
  so day *d*'s allocation uses returns through day *d−1*. Weights are clipped to
  [0.30, 0.70] (IV2) or [0.15, 0.65] (IV3) and renormalised. The standalone
  sleeve equity paths are themselves causal.
- **WE50:** fixed 50/50, the mandate's reference case.

The standalone sleeve equity used for σ is computed with the same harness; a
sleeve's equity at bar *i* depends only on prices through *i* and its own past
weights, so using it to size the blend is causal.

### Drawdown throttle (tested, rejected)

`g(i) = step(dd(i))` with `dd(i) = 1 − equity(i)/running_peak(i)`, applied by
scaling the risky sleeves and putting the remainder in BIL. Tested thresholds
10/20/30% → g = 0.85/0.65/0.45, 15/25/35% → 0.80/0.60/0.40, and a linear
version. Also tested a **volatility target**: `g = clip(38–45% / trailing 20d
portfolio vol, 0.4, 1)`.

---

## 4. Parameters

| Parameter | Value | Why |
|---|---:|---|
| Ensemble weight in WE75 | 25% | Lower edge of the 75–95% region that passes target #2; chosen for the largest drawdown cut that still satisfies the 2 pp rule. 80–85% are the safer-margin alternatives |
| Rebalance band | 2% | Harness default; suppresses tiny allocation drift |
| Inverse-vol lookback | 20 days | Standard; 10–60 days all give similar 1 bp results |
| Inverse-vol clip | [0.15, 0.65] / [0.30, 0.70] | Prevents a single sleeve dominating; the unclipped version is similar |
| Sleeve parameters | as published | SMA 165, vol 20d/33.3%, crash −3%, stop 4%, arm MA20×1.01, first hour 60m |

I did **not** tune the winner or the ensemble. The only free parameter is the
ensemble weight, and the full curve is reported in §7.

---

## 5. Results

### 5.1 WE75, all costs

| Window | Cost | CAGR | Max DD (1m) | Sharpe | Vol | Fills | Turnover | Mean risky weight |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 10y | 0 bp | 59.31% | 40.62% | 1.266 | 45.0% | 903 | 14,786× | 79.3% |
| 10y | 1 bp | **58.42%** | **41.18%** | **1.253** | 45.0% | 903 | 14,160× | 79.3% |
| 10y | 2 bp | 58.05% | 41.74% | 1.241 | 45.0% | 903 | 13,561× | 79.3% |
| 10y | 5 bp | 54.91% | 43.39% | 1.203 | 45.0% | 905 | 11,925× | 79.3% |
| 10y | 10 bp | 50.63% | 46.04% | 1.140 | 45.0% | 905 | 9,644× | 79.3% |
| 5y | 0 bp | 48.73% | 32.17% | 1.139 | 43.3% | 425 | 1,023× | 71.3% |
| 5y | 1 bp | **47.92%** | **32.33%** | **1.126** | 43.3% | 425 | 1,005× | 71.3% |
| 5y | 2 bp | 47.10% | 32.49% | 1.114 | 43.3% | 425 | 987× | 71.3% |
| 5y | 5 bp | 44.70% | 32.96% | 1.075 | 43.3% | 427 | 935× | 71.3% |
| 5y | 10 bp | 40.77% | 33.74% | 1.011 | 43.3% | 427 | 855× | 71.3% |

Winner comparison: 1 bp 58.80%/44.56% (Sharpe 1.239) and 49.88%/33.49% (1.156);
5 bp 54.60%/47.08% and 45.89%/34.13%; 10 bp 49.50%/50.06% and 41.05%/34.93%.
WE75 has the higher 10-year Sharpe at every cost level; the 5-year Sharpe is
slightly lower (1.126 vs 1.156 at 1 bp).

### 5.2 Pass/fail

| Test | WE75 10y | WE75 5y |
|---|---|---|
| CAGR > TQQQ | 58.42 > 39.28 ✅ | 47.92 > 13.47 ✅ |
| Max DD < TQQQ | 41.18 < 81.68 ✅ | 32.33 < 81.68 ✅ |
| CAGR within 2 pp of winner | −0.38 pp ✅ | −1.96 pp ✅ (thin) |
| Max DD < winner | −3.38 pp ✅ | −1.16 pp ✅ |
| **Target #1: strict dominance** | ❌ (CAGR −0.38) | ❌ (CAGR −1.96) |
| **Target #2: lower DD, CAGR within 2 pp** | ✅ | ✅ |

Cost robustness of the 10-year window: at 5 bp WE75 **dominates** the winner
(54.91% vs 54.60%, DD 43.39% vs 47.08%); at 10 bp it dominates again (50.63% vs
49.50%, DD 46.04% vs 50.06%). On the 5-year window at 5 bp and 10 bp it has
lower DD with CAGR 1.19 pp and 0.28 pp lower — target #2 at both costs.

### 5.3 Yearly returns (1 bp)

| Year | WE75 | Winner | TQQQ |
|---|---:|---:|---:|
| 2017 | +117.9% | +118.8% | +114.5% |
| 2018 | +4.9% | +0.5% | −20.8% |
| 2019 | +46.1% | +47.9% | +148.2% |
| 2020 | +189.3% | +183.9% | +104.1% |
| 2021 | +57.0% | +60.6% | +81.1% |
| 2022 | −18.8% | −18.0% | −79.4% |
| 2023 | +141.2% | +149.0% | +192.0% |
| 2024 | +70.0% | +68.0% | +62.4% |
| 2025 | +39.4% | +43.3% | +32.1% |
| 2026* | +18.2% | +16.8% | +22.6% |

\* 2026 is through 2026-10-23. The 5-year window starts 2021-10-25, so its 2021
figure is partial: WE75 +24.1%, winner +26.7%, TQQQ +16.0%.

The blend is better in 2018 (+4.4 pp), 2020 (+5.4 pp), 2024 (+2.1 pp) and 2026
(+1.4 pp), and worse in the strong melt-up years 2019 (−1.8), 2021 (−3.6), 2023
(−7.8) and 2025 (−3.9). That is the expected shape: the ensemble sleeve is in BIL
when realised volatility is high, which is exactly when the winner's 3× TQQQ
run-up is strongest. The drawdown protection is bought with upside give-up, not
with a better return forecast.

### 5.4 Drawdown episodes

| | WE75 | Winner |
|---|---|---|
| 10y max DD | 41.18%, 2018-03-13 → 2019-06-05 | 44.56%, 2018-03-13 → 2019-06-05 |
| 5y max DD | 32.33%, 2026-06-03 → 2026-07-29 | 33.49%, 2026-06-22 → 2026-07-30 |

The 10-year improvement is concentrated in the episode both strategies find
hardest: the 2018 Q4 selloff and the 2019 whipsaw. The ensemble de-risks during
the Q4 2018 selloff through its volatility budget / crash vote, so the 25%
sleeve cuts the trough without sacrificing much of the recovery. The 5-year
improvement is the July 2026 pullback, where the blend de-risks a few weeks
earlier.

### 5.5 Rolling 3-year windows

Quarterly starts 2017-01-03 … 2023-10-01, 3-year windows on daily equity marks
(27 windows for the 10-year panel, 12 for the 5-year panel).

| Strategy | Return > TQQQ | DD < TQQQ | Return > winner | DD < winner | Both > winner |
|---|---:|---:|---:|---:|---:|
| **WE75 10y** | **24/27** | **27/27** | 7/27 | 25/27 | 7/27 |
| WE75 5y | 11/12 | 12/12 | 1/12 | 9/12 | 1/12 |
| Winner 10y | 23/27 | 27/27 | — | — | — |
| Winner 5y | 11/12 | 12/12 | — | — | — |

WE75 keeps the winner's perfect drawdown record against TQQQ and improves the
return hit-rate from 23/27 to 24/27, while cutting the headline drawdown in
25/27 windows. It does **not** beat the winner on both metrics in most windows —
that is the correct interpretation of a lower-volatility blend, not a failed
test. Against the winner itself, "better consistency" cannot mean beating it in
most windows (the winner is the higher-return object); the meaningful test is
the TQQQ hit-rate, which improves. The three 10-year windows where WE75 still
loses to TQQQ on return are the same strong-bull stretches that trouble the
winner.

---

## 6. What failed, and why it matters

### 6.1 Fixed 50/50 (the mandate's reference)

| Window | 1 bp | 5 bp |
|---|---:|---:|
| 10y | 57.59% / 39.15% | 54.77% / 40.21% |
| 5y | 45.75% / 31.58% | 43.28% / 32.15% |

The drawdown cut is large (5.4 pp on 10y, 1.9 pp on 5y) but the 5-year CAGR is
4.13 pp below the winner, so target #2 fails. Half the ensemble is too much: the
ensemble's 5-year CAGR is only 40.79% because its volatility budget sits in BIL
through much of the 2021–2026 bull. This is the clearest evidence that the
optimal weight is well below 50%.

### 6.2 Inverse-volatility blends with momentum

| Variant | 10y 1 bp | 5y 1 bp | 10y 5 bp | 5y 5 bp | 10y 10 bp | 5y 10 bp |
|---|---:|---:|---:|---:|---:|---:|
| IV2 (W/M, 20d, .30/.70) | 58.50 / 41.83 | 49.43 / 31.56 | 50.04 / 44.10 | 41.94 / 32.26 | 40.10 / 46.82 | 33.11 / 33.12 |
| IV3 (W/E/M, 20d, .15/.65) | 57.15 / 41.42 | 47.09 / 29.60 | 50.96 / 43.20 | 41.71 / 30.16 | 43.56 / 45.36 | 35.28 / 30.85 |

IV2 passes target #2 at 1 bp on both windows (−0.30 pp CAGR / −2.73 pp DD on
10y; −0.45 / −1.93 on 5y) and has the best 1 bp Sharpe of any blend (1.291 /
1.201). But it is **cost-fragile**: at 10 bp it gives up 9.4 pp of 10-year CAGR
and 7.9 pp of 5-year CAGR versus the winner. IV2 trades every session (2,667
fills over 10 years; the momentum sleeve alone is 1,995 fills and 41,225×
turnover), so a 5–10 bp cost assumption destroys the timing premium. It is not a
strategy to promote on a 1 bp backtest.

IV3 is the lowest-drawdown blend (29.60% on 5y) and is more cost-robust than IV2,
but its 5-year CAGR is 2.79 pp below the winner, so it fails target #2. The
inverse-vol allocation is stable across 10–60 day lookbacks (IV2 10y
58.4–59.0%, 5y 49.4–50.8%; IV3 10y 57.1–58.1%, 5y 46.9–48.2%), so the result is
not a single parameter. It is simply not enough return.

### 6.3 Drawdown throttles: a clean negative

| Variant | 10y 1 bp | 5y 1 bp |
|---|---:|---:|
| 50/50 + step 10/20/30% → .85/.65/.45 | 33.63% / 28.20% | 21.91% / 27.54% |
| 50/50 + step 15/25/35% → .80/.60/.40 | 34.71% / 30.10% | 26.79% / 24.09% |
| 70/30 + step 12/22/32% → .85/.65/.45 | 35.15% / 31.77% | 26.66% / 27.60% |
| 50/50 + vol target 42% | 53.37% / 35.72% | 45.07% / 26.86% |

The step throttles cut the drawdown but destroy 20–30 pp of CAGR. The reason is
mechanical: with 45% annualised volatility, the strategy is below its running
peak by more than 10% essentially all the time (mean throttle factor 0.69; the
throttle was active on 100% of bars). The thresholds are calibrated for a 10–15%
vol portfolio, not a 3× ETF. A volatility target is gentler but still fails:
42% target gives 53.37%/35.72% on 10y and 45.07%/26.86% on 5y, i.e. lower CAGR
with only a modest DD cut. Both results are consistent with the stop-loss
literature: portfolio-level de-risking helps only if it is rare and shallow.

### 6.4 Adding intraday mean reversion

A fixed 4-way blend (50% W, 30% E, 15% M, 5% mean-reversion) gave 58.06%/39.76%
(10y) and 46.78%/30.44% (5y), worse than the 3-way fixed blend (55/30/15) at
58.35%/39.52% and 47.45%/30.50% at similar drawdown. The mean-reversion sleeve's
5-year standalone CAGR is only 36.59% in this reproduction, so it dilutes return
without adding a distinct drawdown hedge. Dropped.

### 6.5 Why not strict dominance?

To dominate the winner at 1 bp a blend must beat 58.80% CAGR *and* 44.56% DD on
10y, and 49.88% / 33.49% on 5y. Any convex combination with BIL exposure has a
lower expected return in a bull market; the only way to raise return is a
timing/diversification bonus larger than the drag. The inverse-vol blends got
close (IV2: 58.50%/41.83% and 49.43%/31.56%) but the bonus vanished once the
look-ahead was removed. With no leverage allowed, the winner's 100% TQQQ exposure
in the 2021–2026 bull is hard to beat on return. **The honest conclusion is that
the winner is not dominated; the blend is a lower-risk substitute that becomes
the better strategy at realistic costs.**

---

## 7. Robustness: the fixed-weight curve

WE75 sits at the lower edge of a broad passing region, not at a single point.
All numbers are 1 bp.

| Winner weight | 10y CAGR / DD | 5y CAGR / DD | Target #2? |
|---:|---:|---:|:--:|
| 50% | 57.59 / 39.15 | 45.75 / 31.58 | 5y fails |
| 55% | 57.77 / 39.14 | 46.20 / 31.72 | 5y fails |
| 60% | 57.96 / 39.17 | 46.65 / 31.86 | 5y fails |
| 65% | 58.14 / 39.85 | 47.07 / 32.01 | 5y fails |
| 70% | 58.26 / 40.50 | 47.50 / 32.17 | 5y fails (−2.38 pp) |
| **75%** | **58.42 / 41.18** | **47.92 / 32.33** | **passes** |
| 80% | 58.47 / 41.87 | 48.33 / 32.49 | passes |
| 85% | 58.58 / 42.55 | 48.73 / 32.65 | passes |
| 90% | 58.71 / 43.22 | 49.12 / 32.82 | passes (5y −0.76 pp) |
| 95% | 58.74 / 43.89 | 49.51 / 32.99 | passes |
| 100% (winner) | 58.80 / 44.56 | 49.88 / 33.49 | — |

Every step from 75% to 95% passes target #2 on both windows at 1 bp, and the
result is monotone in the weight. The 5 bp results are similarly flat: 70/75/80%
give 10y 54.90/42.64, 54.91/43.39, 54.82/44.14 and 5y 44.42/32.79, 44.70/32.96,
44.95/33.13. All three dominate or match the winner at 5 bp on the 10-year
window, and all three have lower 5-year drawdown. I chose 75% because it is the
largest ensemble weight — and therefore the largest drawdown cut — that still
satisfies the 2 pp rule; 80–85% give a wider 5-year margin at a slightly smaller
drawdown cut. This is a monotone trade-off, not a single lucky grid point.

---

## 8. Caveats

1. **No strict dominance.** WE75 is a lower-risk substitute, not a free lunch.
   The 5-year CAGR gap of −1.96 pp is inside the 2 pp rule by only 0.04 pp; a
   different 5-year start date could flip it.
2. **One asset complex.** Both sleeves trade the same QQQ/TQQQ/BIL complex and
   share the 165-day regime. The diversification is in the intraday risk
   overlays, not across assets. A future high-volatility melt-up (vol > 1/3
   while QQQ rises) would see the ensemble in BIL and the blend lag the winner.
3. **Cost assumptions.** WE75 passes at 10 bp on both windows (10y
   50.63%/46.04%; 5y 40.77%/33.74%), but the 5-year margin over the winner's
   10 bp CAGR is −0.28 pp. The edge is not a 1 bp artifact, but it is not huge
   either. The momentum blends in §6.2 *are* a 1 bp artifact and are reported as
   such.
4. **2026 is partial** (through 2026-10-23). The 5-year drawdown is the July 2026
   episode, a single recent event; the 10-year result has more independent
   episodes (2018, 2020, 2022).
5. **Daily-reset 3× ETF.** TQQQ has path dependence and gap risk. The winner's
   4% stop and the ensemble's crash vote reduce but do not eliminate overnight
   gaps; 2020-03-12 and 2025-04-04 gapped through the triggers. A −20% overnight
   gap remains possible.
6. **No taxes, financing, borrow or market impact.** ~900 fills over 10 years
   create short-term gains and wash-sale exposure in a taxable account. A
   several-pp/yr tax drag would reduce the margin.
7. **Data.** Local adjusted 1-minute QQQ/TQQQ/BIL, 2016-01-04 → 2026-10-23.
   The 1-minute adjustment uses a daily factor, a small approximation. No new
   downloads were used.
8. **This is research, not financial advice.** The last five years contain one
   crash and one exceptional AI-led recovery; forward expectations should be
   lower than the backtest.

---

## 9. Reproduce

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents2\winner-ensemble-blend\strategy.py
```

`strategy.py` rebuilds the three sleeves from the round-1 modules, constructs
WE75, IV2 and IV3, runs every window and cost, checks causality by truncation,
and writes `result.json`. The event-driven simulator in `strategy.py` is an exact
re-implementation of `bt.simulate` (verified `max abs diff = 0.0` on the winner,
1.9e-9 on fractional blends) and is ~60× faster.

Files:

- `research/agents2/winner-ensemble-blend/strategy.py`
- `research/agents2/winner-ensemble-blend/result.json`
- `research/agents2/winner-ensemble-blend/report.md`

---

## 10. Sources

- Newfound, *Ensembles and Rebalancing* (2020) —
  [blog.thinknewfound.com](https://blog.thinknewfound.com/2020/02/ensembles-and-rebalancing)
- *Diversification Returns, Rebalancing Returns and Volatility Pumping* —
  [SSRN 2311240](https://ssrn.com/abstract=2311240)
- *Demystifying Rebalancing Premium and Extending Portfolio Theory* —
  [SSRN 2927791](https://ssrn.com/abstract=2927791)
- DeMiguel, Garlappi & Uppal (2009), *Optimal Versus Naive Diversification* —
  [DOI 10.1093/rfs/hhm075](https://doi.org/10.1093/rfs/hhm075)
- *Advances in Portfolio Risk Control: Risk! Parity?* —
  [SSRN 2259041](http://ssrn.com/abstract=2259041)
- Quantpedia, *Risk Parity Asset Allocation* —
  [quantpedia.com](https://quantpedia.com/risk-parity-asset-allocation/)
- *Stop-Loss Strategies with Serial Correlation, Regime Switching, and
  Transactions Costs* — [SSRN 2695383](http://ssrn.com/abstract=2695383)
- Macrosynergy, *Drawdown Control* —
  [macrosynergy.com](https://macrosynergy.com/research/drawdown-control/)
- Boyd et al., *Multi-period portfolio selection with drawdown control* —
  [Stanford PDF](https://stanford.edu/~boyd/papers/pdf/multiperiod_portfolio_drawdown.pdf)
- Moreira & Muir (2017), *Volatility-Managed Portfolios* —
  [SSRN 2659431](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431)
- Round-1 sources: Faber ([SSRN 962461](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461)),
  Gayed & Bilello ([SSRN 2741701](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701)).
