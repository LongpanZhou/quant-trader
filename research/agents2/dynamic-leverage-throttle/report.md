# Dynamic leverage throttle: 30% TQQQ core + 70% 65%-vol-target, with the winner's armed 4% minute stop

**Agent:** `dynamic-leverage-throttle` (round 2, agent 19)
**Dates:** 2017-01-03 → 2026-10-23 (10y, 9.80 years); 2021-10-25 → 2026-10-23 (5y, 4.99 years)
**Data:** local adjusted 1-minute QQQ / TQQQ / BIL only (`data/intraday-hf/`), regular session
**Harness:** `research/bt.py`; signal at bar `i`, fill at bar `i+1` open; 2% trade band;
long-only, weights sum to ≤ 1; 1 bp primary, 5 bp and 10 bp reported.

---

## Verdict

**The candidate meets README criterion 2 on both windows: lower max drawdown than
the winner with CAGR within 2 pp, and a higher Calmar ratio in both windows.**
It also strictly dominates the winner on the 5-year window. The 10-year CAGR
cushion is thin (1.75 pp of the allowed 2 pp), so this is a drawdown/Calmar win,
not a return win.

| Window | Cost | Candidate CAGR / max DD | Winner CAGR / max DD | TQQQ CAGR / max DD | Calmar cand / winner |
|---|---:|---:|---:|---:|---:|
| 10y | 1 bp | **57.05% / 41.32%** | 58.80% / 44.56% | 39.38% / 82.29% | **1.38 / 1.32** |
| 10y | 5 bp | **53.05% / 43.83%** | 54.60% / 47.08% | — | **1.21 / 1.16** |
| 10y | 10 bp | **48.17% / 46.81%** | 49.50% / 50.06% | — | **1.03 / 0.99** |
| 5y | 1 bp | **50.12% / 30.16%** | 49.88% / 33.49% | 14.29% / 82.29% | **1.66 / 1.49** |
| 5y | 5 bp | **46.19% / 30.87%** | 45.89% / 34.13% | — | **1.50 / 1.34** |
| 5y | 10 bp | **41.41% / 31.74%** | 41.05% / 34.93% | — | **1.30 / 1.18** |

Pass/fail:

| Test | 10y | 5y |
|---|---|---|
| CAGR > TQQQ (39.28% / 13.47% README) | **PASS** 57.05% | **PASS** 50.12% |
| Max DD < TQQQ (81.68%) | **PASS** 41.32% | **PASS** 30.16% |
| CAGR within 2 pp of winner | **PASS** −1.75 pp | **PASS** +0.24 pp |
| Max DD < winner | **PASS** −3.24 pp | **PASS** −3.33 pp |
| Strict dominance (higher CAGR *and* lower DD) | fail (CAGR −1.75 pp) | **PASS** |
| Calmar > winner | **PASS** 1.38 vs 1.32 | **PASS** 1.66 vs 1.49 |
| Still passes at 5 bp | **PASS** | **PASS** |
| Still passes at 10 bp | **PASS** | **PASS** |

The 10-year pass is marginal on the return band: 57.05% vs the 56.80% floor. The
neighbour table below shows the neighbouring core sizes (0.2 and 0.4) give
56.71% and 57.31%, so this is a plateau, but the 2 pp test is not cleared by a
wide margin. The drawdown improvement is the robust part: the candidate has a
lower 3-year drawdown than the winner in 25 of 27 rolling windows.

---

## 1. Idea

The round-1 winner holds 100% TQQQ in the risk-on regime and uses a minute stop
only on armed days. That leaves the *size* of the TQQQ position constant through
calm and turbulent markets. TQQQ is a daily-reset 3× fund whose multi-day log
return is approximately

```
log(LETF_T/LETF_0) ≈ 3·log(QQQ_T/QQQ_0) − 3·Σ r_t²
```

(Cheng & Madhavan 2009; ProShares prospectus), so the drag and crash risk grow
with realised variance. Sizing the position inversely to recent volatility is
the standard remedy (Moreira & Muir 2017; Harvey et al. 2018). The literature
also warns that volatility-managed portfolios can fail out of sample
(Cederburg et al. 2020), which is why the implementation here is deliberately
mild: a permanent core plus a tempered, capped adjustment rather than an
all-or-nothing vol switch.

A second lesson from round 1 is that hard drawdown throttles are harmful:
selling after the drawdown has happened misses the rebound (the `vol-kelly`
agent's V3 and the `drawdown-stop-overlay` results both showed this, and my
`dd60` variant reproduces it). The throttle therefore responds to *volatility*,
not to losses.

The core/satellite formulation is also the fractional-Kelly logic. For excess
mean `μ` and variance `σ²`, the growth-optimal fraction is `f* = μ/σ²`; with a
roughly constant Sharpe ratio, `f* ∝ 1/σ`. Full Kelly is too aggressive under
parameter uncertainty, so fractional Kelly is the practical choice (Thorp 2006).
My direct Kelly test was much too conservative (see §6), but the 30/70 blend is
a robust, shrunk version of the same inverse-vol idea: 30% of the book always
holds TQQQ, and 70% follows the 65%-vol target.

---

## 2. Data and conventions

- Local adjusted 1-minute QQQ/TQQQ/BIL bars, 09:30–16:00 ET, no new downloads.
- **Daily bars** are the 15:59 close of each session. All signals use data through
  the **prior** close and are mapped to the next session; the first bar's target
  fills at 09:31 (next bar open), so there is no same-bar or same-close fill.
- **Realised volatility:** 20-day standard deviation of TQQQ daily close-to-close
  log returns × √252. I deliberately use daily closes rather than 1-minute
  realised variance: 1m RV on TQQQ has a median annualised value near 95%
  because of bid-ask bounce, which would make a 45–65% target bind almost
  always. The daily-close estimator has a median of 51% and is the state
  variable that matches the held exposure. (The 1m-RV version is a robustness
  check in the round-1 `vol-kelly` report; it is not used here.)
- **Max drawdown** is measured on the 1-minute equity path (conservative;
  `bt.stats` with 252×390 bars/year). Daily-mark drawdown is also reported.
- **Calmar** = CAGR / max drawdown (1m path).
- **Benchmarks:** TQQQ buy-and-hold on the same close series. The harness gives
  39.38% / 82.29% (10y) and 14.29% / 82.29% (5y); the README quotes 39.28% /
  81.68% and 13.47% / 81.68%. Pass/fail uses the stricter README numbers; the
  conclusion is unaffected.

---

## 3. Exact rules

Let `C_t` be QQQ's daily close, `SMA165_t` its 165-day SMA, `MA20_t` its 20-day
SMA, and `v20_t` TQQQ's annualised 20-day realised volatility, all through the
close of day `t`.

1. **Regime.** If `C_t > SMA165_t`, the next session is risk-on; otherwise hold
   100% BIL for the session and overnight.
2. **Size (risk-on only).**
   ```
   w_TQQQ = 0.30 + 0.70 × min(1, 0.65 / v20_t)
   w_BIL  = 1 − w_TQQQ
   ```
   No QQQ sleeve in the primary; no leverage above 100% TQQQ.
3. **Arm the stop.** On a risk-on day, arm a 4% stop from the session open only
   when QQQ's first-minute close is below `MA20_{t} × 1.01`.
4. **Stop.** While armed, if TQQQ's 1-minute close is 4% below the session open,
   sell the whole book at the next minute's open and stay in BIL for the rest of
   the session and the following night. Re-enter at the next session's open if
   the daily regime is still risk-on.
5. Nothing else. Long-only, one state machine, no shorts.

### Parameters

| Parameter | Value | Rationale |
|---|---:|---|
| Regime SMA | 165 trading days | Winner's parameter; not re-optimised |
| Arm MA / buffer | 20 days / +1% | Winner's parameter |
| Stop | 4% below session open | Winner's parameter |
| Vol window | 20 trading days | Standard vol-targeting lookback (Harvey et al.) |
| Vol target | 65% annualised | Middle of the mandated 45/55/65 grid |
| Permanent core | 30% TQQQ | Round value; surface is flat for 20–40% |
| Trade band | 2% | Harness default, same as winner |
| Costs | 1 bp primary; 5/10 bp reported | One-way on traded notional |

Average **target** TQQQ weight: **93.9%** over the 10y window and **93.6%** over
the 5y window; the target is capped at 100% on 66% / 62% of sessions, and the
minimum is 46% / 56%. So the throttle is mild on average and bites only in the
high-volatility tails — that is why the CAGR cost is small.

---

## 4. Results

### 4.1 Headline, 1 bp

| Window | Strategy | CAGR | Max DD (1m) | DD (daily marks) | Vol | Sharpe | Sortino | Calmar | Fills | Turnover | End equity |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **10y** | **Candidate** | **57.05%** | **41.32%** | 38.30% | 43.41% | 1.26 | 1.78 | **1.38** | 983 | 15,095× | $8,348,603 |
| 10y | Winner | 58.80% | 44.56% | 41.62% | 46.12% | 1.24 | 1.74 | 1.32 | 657 | 17,331× | $9,304,770 |
| 10y | TQQQ | 39.38% | 82.29% | — | 66.61% | 0.84 | — | 0.48 | — | — | $2,590,606 |
| **5y** | **Candidate** | **50.12%** | **30.16%** | 29.46% | 42.30% | 1.18 | 1.68 | **1.66** | 465 | 1,264× | $760,774 |
| 5y | Winner | 49.88% | 33.49% | 33.08% | 43.39% | 1.16 | 1.64 | 1.49 | 337 | 1,295× | $754,799 |
| 5y | TQQQ | 14.29% | 82.29% | — | 66.90% | 0.54 | — | 0.17 | — | — | $194,866 |

The candidate has slightly *lower* turnover than the winner despite more fills:
the daily resize often trades TQQQ against BIL in offsetting directions, and the
2% band suppresses most small changes. The 160 minute stops are unchanged
(the arm rule and stop level are identical to the winner).

### 4.2 Cost sensitivity

| Window | Cost | Candidate CAGR / DD / Calmar | Winner CAGR / DD / Calmar |
|---|---:|---:|---:|
| 10y | 1 bp | 57.05% / 41.32% / 1.38 | 58.80% / 44.56% / 1.32 |
| 10y | 5 bp | 53.05% / 43.83% / 1.21 | 54.60% / 47.08% / 1.16 |
| 10y | 10 bp | 48.17% / 46.81% / 1.03 | 49.50% / 50.06% / 0.99 |
| 5y | 1 bp | 50.12% / 30.16% / 1.66 | 49.88% / 33.49% / 1.49 |
| 5y | 5 bp | 46.19% / 30.87% / 1.50 | 45.89% / 34.13% / 1.34 |
| 5y | 10 bp | 41.41% / 31.74% / 1.30 | 41.05% / 34.93% / 1.18 |

The candidate keeps the 2 pp / lower-DD property at 5 bp and 10 bp on both
windows. The 5-year strict dominance also survives every cost level.

### 4.3 Yearly returns

| Year | Candidate | Winner | TQQQ |
|---:|---:|---:|---:|
| 2017 | +113.13% | +113.13% | +114.54% |
| 2018 | **−6.45%** | −9.33% | −20.76% |
| 2019 | +38.88% | +41.43% | +148.23% |
| 2020 | +142.89% | **+168.98%** | +104.14% |
| 2021 | +44.63% | +47.85% | +81.05% |
| 2022 | **−18.43%** | −19.89% | −79.39% |
| 2023 | **+138.52%** | +135.52% | +192.05% |
| 2024 | +51.61% | +56.29% | +62.43% |
| 2025 | +33.62% | +34.79% | +32.10% |
| 2026 | **+12.67%** | +9.04% | +22.62% |

(5y window: 2021 is partial, candidate +22.52% vs winner +23.86% vs TQQQ
+16.02% from 2021-10-25; 2022–2026 are the same rows.)

The candidate beats the winner in **2018, 2022, 2023 and 2026**, and loses
mostly in **2020** (−26.1 pp vs the winner) — the V-shaped COVID recovery, when
volatility stayed high while TQQQ compounded violently. It also lags in 2021
and 2024, both strong, relatively low-vol bull runs where the vol cap binds
only briefly. This is the expected shape: the throttle gives up some melt-up
participation to cut the left tail.

### 4.4 Half periods

| Period | Candidate CAGR / DD / Calmar | Winner CAGR / DD / Calmar |
|---|---:|---:|
| 2017-01-03 → 2021-12-31 | 69.64% / 41.32% / 1.69 | 74.05% / 44.56% / 1.66 |
| 2022-01-03 → 2026-10-23 | **44.93% / 30.16% / 1.49** | 44.34% / 33.49% / 1.32 |

The entire CAGR give-up is in the first half (mostly 2020). In the recent
four-plus years the candidate beats the winner on **both** return and drawdown.

---

## 5. Rolling 3-year windows

Quarterly starts from 2017-04-01 to 2023-10-01, 27 windows. Each window is
simulated independently at 1 bp with the same weight paths.

| Count | Candidate | Winner |
|---|---:|---:|
| Return > TQQQ | 22 / 27 | 23 / 27 |
| Drawdown < TQQQ | **27 / 27** | **27 / 27** |
| Return > winner | 5 / 27 | — |
| Drawdown < winner | **25 / 27** | — |
| Both return > and DD < winner | 3 / 27 | — |
| Calmar > winner | 12 / 27 | — |

Two windows have *equal* drawdown to the winner (2021-04 and 2021-07, both
26.6%), so the 25/27 count is 25 strictly lower plus 2 ties, never higher.

Selected windows (candidate / winner / TQQQ, CAGR and max DD):

| Start | Candidate | Winner | TQQQ |
|---|---:|---:|---:|
| 2017-04 | 32.3 / 41.3 | 28.9 / 44.6 | 17.6 / 72.7 |
| 2018-04 | 44.7 / 39.6 | 48.3 / 41.5 | 57.6 / 72.7 |
| 2018-07 | 57.4 / 39.6 | 63.5 / 41.5 | 64.1 / 72.7 |
| 2019-01 | 82.0 / 39.6 | 91.5 / 41.5 | 112.2 / 72.7 |
| 2019-10 | 68.6 / 39.6 | 75.4 / 41.5 | 7.3 / 78.9 |
| 2020-04 | 69.1 / 39.6 | 79.5 / 41.5 | 37.6 / 82.3 |
| 2021-04 | 72.4 / 26.6 | 72.1 / 26.6 | 10.1 / 82.3 |
| 2021-10 | 62.8 / 28.8 | 63.7 / 29.4 | 6.0 / 82.3 |
| 2022-10 | 78.6 / 28.8 | 80.3 / 29.4 | 76.4 / 62.2 |
| 2023-01 | 79.7 / 28.8 | 81.3 / 29.4 | 84.0 / 62.2 |
| 2023-10 | 66.1 / 30.2 | 66.6 / 33.5 | 65.6 / 62.2 |

Honest reading: the candidate **does not** beat the winner in more rolling
windows (5/27 return, 3/27 both). It matches the winner's 27/27 drawdown edge
over TQQQ and improves the drawdown in 25/27 windows. That is a consistency
improvement in risk, not in return. README criterion 3 ("materially more windows
beating both TQQQ and the winner") is **not** met.

---

## 6. Variants tested (1 bp)

All variants use the same 165-day regime, the same armed 4% minute stop, the
same fills and band. "10y" and "5y" are CAGR / max DD.

| Variant | 10y | 5y | Assessment |
|---|---:|---:|---|
| **Primary: 30% core + 70% × 65% vol target** | **57.05 / 41.32** | **50.12 / 30.16** | best compliant Calmar |
| Vol target 45%, no core | 49.50 / 32.21 | 43.75 / 24.69 | too much CAGR loss |
| Vol target 55%, no core | 53.40 / 36.51 | 47.65 / 27.37 | too much CAGR loss |
| Vol target 65%, no core | 56.14 / 39.92 | 50.08 / 28.84 | best Calmar (1.41 / 1.74); 10y CAGR −2.66 pp, outside 2 pp |
| Vol target 80%, no core | 58.13 / 43.31 | 50.32 / 31.07 | passes 2 pp rule, but DD gain only 1.25 pp |
| 20% core + 80% × 65% target | 56.71 / 40.77 | 49.94 / 29.89 | misses 10y 2 pp by 0.09 pp |
| 40% core + 60% × 65% target | 57.31 / 41.82 | 50.04 / 30.49 | passes; slightly lower Calmar |
| 30% core, 30-day vol | 57.26 / 42.17 | 50.96 / 29.74 | better 5y, worse 10y DD |
| Drawdown throttle: `1 − 0.5·|DD60|`, floor 25% | 57.40 / 43.56 | 48.70 / 32.99 | no Calmar gain; confirms buy-the-dip cost |
| Trend strength: `0.5 + 0.5·trend/4%`, floor 50% | 53.35 / 42.39 | 43.46 / 33.46 | clean negative; lags recoveries |
| Fractional Kelly: 0.5·μ60/σ²60, cap 100% | 25.35 / 45.38 | 18.03 / 39.46 | clean negative; far too little exposure |
| Winner: 100% TQQQ | 58.80 / 44.56 | 49.88 / 33.49 | reference |

Notes on the failures:

- **Drawdown throttle.** Cutting exposure as the drawdown from a 60/120/252-day
  high deepens reduces both return and Calmar. The 10y DD falls only from 44.56%
  to 43.56%, while CAGR falls 1.4 pp. This is the same result the round-1
  `vol-kelly` agent found with its equity-drawdown throttle, and it is why the
  primary rule uses volatility, not losses.
- **Trend strength.** Scaling with `QQQ/SMA165 − 1` is procyclical: it is
  smallest exactly at the start of recoveries (2019, 2020, 2023), when forward
  returns are highest. Every band/floor combination lost 2–12 pp of CAGR with
  little drawdown benefit.
- **Fractional Kelly.** Daily TQQQ μ/σ² estimates imply a fraction well below
  1 for most of the sample (μ is noisy and σ² is large), so the strategy sits at
  20–30% exposure and returns 15–28% CAGR. It also skips stop checks on days
  when the target is zero. Full Kelly is worse (48% DD). Direct Kelly is not a
  usable sizing rule at daily frequency on a 3× ETF.
- **Pure vol target 65%** is the Calmar-max variant (1.41 / 1.74) and has strict
  5y dominance, but its 10y CAGR (56.14%) is 2.66 pp below the winner, outside
  the 2 pp band. If the reader weights Calmar over the 2 pp rule, this is the
  better choice; I did not promote it because the README criterion is explicit.

### Neighbour surface (pure vol target)

| Target | 10y CAGR / DD / Calmar | 5y CAGR / DD / Calmar |
|---:|---:|---:|
| 58% | 54.52 / 37.53 / 1.45 | 48.87 / 27.72 / 1.76 |
| 60% | 55.07 / 38.45 / 1.43 | 49.36 / 27.96 / 1.77 |
| 62% | 55.51 / 39.01 / 1.42 | 49.81 / 28.26 / 1.76 |
| 65% | 56.14 / 39.92 / 1.41 | 50.08 / 28.84 / 1.74 |
| 68% | 56.46 / 40.78 / 1.38 | 50.03 / 29.60 / 1.69 |
| 72% | 57.04 / 41.80 / 1.36 | 50.15 / 30.14 / 1.66 |
| 80% | 58.13 / 43.31 / 1.34 | 50.32 / 31.07 / 1.62 |

The surface is monotone: higher target → more CAGR, more DD, lower Calmar.
There is no single lucky cell; the primary's core blend sits on the same
frontier with a small, smooth shift toward return.

---

## 7. Causality / no-look-ahead

- All daily signals use the prior close and fill at the next bar's open.
- Truncation test: rebuild every signal and the full weight path using data only
  through 2022-01-03, then compare all prior weights with the full-sample path.
  Result: **identical, max absolute difference 0.0**.
- The stop uses the current minute close and fills at the next minute open,
  exactly as verified for the round-1 winner.

---

## 8. Honest assessment and caveats

1. **This is a risk-reduction trade, not alpha.** The 10-year CAGR is 1.75 pp
   below the winner; the gain is a 3.24 pp lower max drawdown and a higher
   Calmar (1.38 vs 1.32). The 5-year window is the only strict dominance.
2. **The 10-year 2 pp pass is thin.** 57.05% vs a 56.80% floor. A 30% core is
   the round middle of a plateau (56.71% at 20%, 57.31% at 40%), but a slightly
   different vol window or sample would flip the test. Do not treat the 10y
   pass as statistically established.
3. **The 2020 cost is structural.** The vol target stays below 100% during the
   fastest part of the COVID rebound; 2020 returns 142.9% vs the winner's 169.0%.
   A future V-shaped recovery with sustained high vol would produce the same
   lag.
4. **One crash sample.** The 1-minute data starts in 2016, so there is no 2000
   or 2008 test. The drawdown improvement is measured on 2018–2019, 2020 and
   2022–2024 episodes only.
5. **Volatility estimation is noisy.** A 20-day daily-close estimator is
   standard but laggy at turns. The 30-day variant improves the 5y but worsens
   the 10y DD; a 10-day variant cuts the 5y CAGR to 46.66%. The 20-day choice
   is the literature default, not a fitted optimum.
6. **Costs and turnover.** 15,095× turnover over 10 years is high; at 10 bp the
   10y CAGR falls to 48.17%. Taxes, borrow costs and market impact beyond the
   linear slippage model are not included. The candidate's turnover is slightly
   below the winner's, so it is not more cost-sensitive.
7. **Long-only, no extra leverage.** The maximum TQQQ weight is 100%; the only
   leverage is TQQQ's embedded 3×. No shorting or margin.
8. **Rolling consistency is risk-only.** The candidate does not beat the winner
   in more rolling return windows (5/27 vs the winner's 23/27 vs TQQQ). Its
   drawdown is lower in 25/27 and never higher. If the objective is "beat the
   winner more often", this strategy does not deliver that.

---

## 9. Pass/fail summary

**Versus TQQQ buy-and-hold:** PASS on both windows at 1, 5 and 10 bp.
(10y 57.05% vs 39.28%, DD 41.32% vs 81.68%; 5y 50.12% vs 13.47%, DD 30.16% vs
81.68%.)

**Versus the round-1 winner:** meets README criterion 2 on both windows —
lower max DD with CAGR within 2 pp — and has a higher Calmar in both. Strict
dominance is achieved on the 5-year window only. At 5 bp and 10 bp the same
pattern holds: within 2 pp on 10y with lower DD, strict dominance on 5y.

**Not achieved:** README criterion 1 (strict dominance on both windows) and
criterion 3 (materially more rolling windows beating both TQQQ and the winner).
The result is a genuine but modest improvement in the risk profile of the
winner, concentrated in the high-volatility tails.

---

## 10. Reproduce

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research/agents2/dynamic-leverage-throttle/strategy.py
```

`strategy.py` caches the 1-minute panel as `panel.npz`, builds all signals, runs
the 10y/5y windows at 1/5/10 bp, the 27 rolling 3-year windows, the variant
table, the half periods and the truncation causality check, then writes
`result.json`. The `explore.py`, `variants1.py` and `rolling.py` files are the
scratch exploration scripts (grids and the first-pass rolling comparison); they
are not needed to reproduce the headline result.

---

## Sources

- Moreira, A. & Muir, T. (2017). "Volatility-Managed Portfolios." *Journal of
  Finance* 72(4), 1611–1644. https://doi.org/10.1111/jofi.12513 ·
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431
- Harvey, C. R., Hoyle, E., Korgaonkar, R., Rattray, S., Sargaison, M. &
  Van Hemert, O. (2018). "The Impact of Volatility Targeting." *Journal of
  Portfolio Management* 45(1), 14–33. https://doi.org/10.3905/jpm.2018.45.1.014 ·
  https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf
- Cederburg, S., O'Doherty, M. S., Wang, F. & Yan, X. S. (2020). "On the
  performance of volatility-managed portfolios." *Journal of Financial
  Economics* 138(1), 95–117. https://doi.org/10.1016/j.jfineco.2020.04.015
- Bongaerts, D., Kang, X. & van Dijk, M. (2020). "Conditional Volatility
  Targeting." *Financial Analysts Journal* 76(4).
  https://doi.org/10.1080/0015198X.2020.1790853
- Grossman, S. J. & Zhou, Z. (1993). "Optimal Investment Strategies for
  Controlling Drawdowns." *Mathematical Finance* 3(3), 241–276.
  https://doi.org/10.1111/j.1467-9965.1993.tb00044.x
- Thorp, E. O. (2006). "The Kelly Criterion in Blackjack, Sports Betting, and
  the Stock Market." https://gwern.net/doc/statistics/decision/2006-thorp.pdf
- Kelly criterion, fractional Kelly and parameter uncertainty:
  https://en.wikipedia.org/wiki/Kelly_criterion
- Moskowitz, T. J., Ooi, Y. H. & Pedersen, L. H. (2012). "Time Series
  Momentum." *Journal of Financial Economics* 104(2), 228–250.
  https://doi.org/10.1016/j.jfineco.2011.11.003
- Cheng, M. & Madhavan, A. (2009). "The Dynamics of Leveraged and Inverse
  Exchange-Traded Funds." *Journal of Investment Management* 7(4).
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995
- ProShares, *TQQQ UltraPro QQQ Summary Prospectus* (daily 3× objective and
  holding-period risk).
  https://www.proshares.com/globalassets/proshares/prospectuses/tqqq_summary_prospectus.pdf
- Man Group, "The Impact of Volatility Targeting."
  https://man.com/insights/the-impact-of-volatility-targeting
- Drawdown-control implementation note (exposure as a decreasing function of
  drawdown): https://quantmemo.com/concepts/drawdown-control
- Round-1 internal reports: `research/agents/daily-regime-minute-entry/report.md`,
  `research/agents/vol-kelly-overlay/report.md`,
  `research/agents/drawdown-stop-overlay/report.md`.

---

## Files

- `strategy.py` — runnable implementation, all tables and `result.json`.
- `result.json` — machine-readable metrics: 10y/5y at 1/5/10 bp, yearly
  returns, 27 rolling windows, variant table, half periods, causality check,
  pass/fail flags.
- `report.md` — this document.
- `explore.py`, `variants1.py`, `rolling.py` — scratch exploration (panel
  cache, first-pass grids, rolling comparison).
