# Close-momentum weakness exit on a vol-targeted TQQQ core

**Verdict: passes the development bar at 1, 5 and 10 bp, with a qualified
holdout case.** The return engine is a high-exposure, volatility-targeted TQQQ
position. The intraday-close signal is a conditional exit: a negative full-day
QQQ return **in an already-elevated volatility regime** takes the book to cash
for the next 24 hours. That exit is what cuts the drawdown from the 72% of the
vol-only control to 54%.

Dev 2016-01-04..2023-12-29, 1-minute marks, next-open fills, 2% band:

| | CAGR | Max DD | Sharpe | Sortino | Exposure | Fills | Turnover |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Strategy, 1 bp** | **46.21%** | **53.87%** | **1.08** | 1.52 | 79.1% | 590 | 1,969x |
| Strategy, 5 bp | 44.19% | 55.32% | 1.05 | 1.48 | 79.1% | 589 | 1,836x |
| Strategy, 10 bp | 41.71% | 57.35% | 1.01 | 1.42 | 79.1% | 589 | 1,684x |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | — | 100% | 1 | 1x |
| TQQQ bar from the brief | 36.72% | 82.29% | 0.82 | — | 100% | — | — |

Daily-return correlation to TQQQ: **0.773**. Ending equity $2.08M from $100k
at 1 bp. The strategy beats the CAGR bar by **+9.5 pp** and cuts max drawdown
by **28.4 pp**, and it still clears the bar at 10 bp (41.71%). The drawdown is
2021-11-22 to 2022-11-09, the 2022 bear.

---

## 1. What it is

Universe: QQQ (signal), TQQQ (position), cash. One decision per session at the
close of the **15:29 ET** one-minute bar (15:30), filled at the **15:30 open**.
The target is held until the next 15:30 open, then re-decided.

```
r_k      = QQQ close(15:29) / QQQ open(09:30) - 1     # full intraday return
sigma_k  = annualised stdev of the last 10 completed QQQ daily log returns
           through session k-1 (lagged one session)
base_k   = min(1, 0.20 / sigma_k)
w_k      = 0                        if r_k <= 0 and sigma_k >= 0.20
         = base_k                   otherwise
```

The same 0.20 is the volatility target and the "elevated vol" line. Long only,
weights in [0, 1], idle weight cash at 0%. No intraday stop, no BIL sleeve, no
moving average, no overnight-gap selection, no 15:58→10:01 block. The 2015
daily QQQ closes are used only to warm the 10-day vol so the rule is live on
2016-01-04; the daily parquet is truncated at 2023-12-29 before any rolling
statistic is computed.

**Causality.** The signal uses the 15:29 close; the vol uses daily closes
through the prior session; the fill is the next open. Truncating the panel at
2022-01-03 leaves every prior weight identical (`prior_weights_unchanged =
true`).

**Why this is a close-momentum strategy and not the existing designs.** The
decision variable is one day's intraday return, not a 20/165-day moving
average and not a "sold close" filter. The exit is conditional on the vol
regime: a weak close in a calm tape is a dip and is held; a weak close in a
high-vol tape is a continuation signal and is exited. The holding period is a
continuous 24h position anchored at 15:30, not a fixed 15:58→10:01 block.

## 2. Results

### Yearly returns (daily-close compounding)

| Year | Strategy | TQQQ | Note |
|---|---:|---:|---|
| 2016 | **-2.7%** | +18.6% | whipsaw: see §7 |
| 2017 | +113.0% | +113.0% | full weight all year, no exits |
| 2018 | **+3.2%** | -23.5% | +26.7 pp |
| 2019 | +94.3% | +130.5% | lags a melt-up |
| 2020 | +96.8% | +99.8% | roughly matched |
| 2021 | +58.7% | +90.9% | lags |
| 2022 | **-46.3%** | -79.7% | +33.4 pp |
| 2023 | +168.2% | +204.9% | lags a melt-up |

The pattern is a crash filter: it wins 2018 and 2022, matches 2017/2020, and
lags the strong bull years. The full-window CAGR advantage comes from
compounding the much smaller 2022 loss, not from beating TQQQ every year.

### Sub-periods

| Period | Strategy CAGR / DD | TQQQ CAGR / DD |
|---|---:|---:|
| 2016-2019 | 47.0% / 36.6% | 49.0% / 58.6% |
| 2020-2021 | 75.1% / 33.5% | 93.5% / 72.7% |
| 2022-2023 | +19.3% / 48.7% | -21.7% / 81.1% |

The strategy **lags TQQQ on CAGR in both 2016-2019 and 2020-2021**, while
cutting drawdown by 22 pp and 39 pp. The full-window CAGR edge is concentrated
in 2022-2023, where it makes +19.3% a year while TQQQ compounds at -21.7% a
year. That is a real but regime-dependent edge.

### Costs and turnover

590 fills over 8 years (~74/year). Turnover is 1,969x initial equity because
the book compounds 20x; the notional-weighted number is large but the fill
count is low. Cost sensitivity is 46.21% → 44.19% → 41.71% at 1/5/10 bp, a
4.5 pp drag at 10 bp. The edge survives.

## 3. Pre-registered grid: the plateau

All 8 cells, 1/5/10 bp. Bar: CAGR > 36.72%, DD < 82.29%; target DD < 60%.

| line | window | CAGR 1 bp | CAGR 5 bp | CAGR 10 bp | Max DD | Sharpe | Exposure |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **0.20** | **10** | **46.21%** | **44.19%** | **41.71%** | 53.87% | 1.08 | 79.1% |
| 0.18 | 10 | 37.14% | 34.96% | 32.30% | 46.36% | 0.97 | 74.6% |
| 0.22 | 10 | 53.28% | 51.40% | 49.07% | 51.17% | 1.16 | 82.3% |
| 0.20 | 5 | 35.79% | 33.88% | 31.52% | 66.29% | 0.89 | 82.0% |
| 0.20 | 15 | 52.66% | 50.48% | 47.81% | 43.58% | 1.19 | 77.0% |
| 0.20 | 20 | 46.09% | 43.97% | 41.38% | 42.51% | 1.09 | 76.6% |
| 0.18 | 20 | 39.15% | 36.99% | 34.35% | 38.69% | 1.02 | 72.8% |
| 0.22 | 20 | 47.43% | 45.55% | 43.17% | 47.73% | 1.07 | 80.2% |

**7/8 clear the CAGR bar at 1 bp; 5/8 clear it at 10 bp; all 8 clear the DD
bar and 7/8 are below 60%.** The centre is not the best cell (window 15 is
52.66%), which is the honest test that the result is a surface and not a
single lucky cell. The two weak corners are the 5-day window (35.79% / 66.29%)
and the low-vol-line cells at 10 bp (32-34%). The 10-day window is the
standard fast-vol choice; it was not chosen because it was best.

## 4. Neighbour tests

| Variant | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| **Centre** | **46.21%** | **53.87%** | **1.08** |
| signal = last 30 min | 40.59% | 67.95% | 0.99 |
| signal = last 60 min | 32.18% | 68.38% | 0.85 |
| exit threshold -25 bp | 41.67% | 60.17% | 1.00 |
| exit threshold +25 bp | 45.03% | 57.71% | 1.08 |
| decision 15:58 (fill 15:59) | 27.17% | 65.10% | 0.77 |
| vol window 30 | 45.98% | 41.77% | 1.09 |
| line 0.21 | 48.08% | 54.08% | 1.09 |

The full-day signal is the working one: the last 30/60-minute returns are
weaker and have higher drawdowns. The 15:30 decision clock matters — moving it
to 15:58 (missing the last 30 minutes and the close) drops CAGR to 27.17%.
The ±25 bp threshold and the 0.21 line are a plateau. The vol window is the
one real choice: 5 days is too noisy, 10-30 days is the working range.

## 5. Controls: what is doing the work?

| Control | CAGR | Max DD | Sharpe | Exposure |
|---|---:|---:|---:|---:|
| **Strategy** | **46.21%** | **53.87%** | **1.08** | 79.1% |
| Vol target only (no close exit) | 44.09% | 72.15% | 0.98 | 90.1% |
| Close exit only (no vol target/gate) | 13.62% | 55.46% | 0.51 | 54.7% |
| Constant weight at the same 79.5% mean | 32.49% | 72.66% | 0.80 | 79.5% |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 100% |

This is the most important table in the report. The **vol-targeted core is the
return engine** (44.09%); the close rule adds **+2.1 pp of CAGR and cuts 18.3
pp of drawdown**. The close exit without the vol gate is far too conservative
(13.62%). The constant-exposure control shows the result is not just
de-levering: at the same average weight, static TQQQ earns 32.49% with a 72.7%
drawdown. The timing and vol scaling together add +13.7 pp CAGR and -18.8 pp
DD versus the static control.

Honest reading: this is a risk-managed TQQQ position whose drawdown target is
met by the close rule, not a close-momentum strategy that generates the return
from the signal alone.

## 6. Placebo, cuts, causality

**Placebo (200 draws).** Keep the vol-target base and the same number of exit
days (313), but draw the exit days at random from the 690 high-vol sessions.
Real 46.21%, placebo mean 39.76%, median 39.45%, 95th percentile 53.80%,
**p = 0.22**. On drawdown: real 53.87%, placebo mean 61.99%, 5th percentile
47.87%, **p = 0.22**. The close timing is directionally favorable (+6.5 pp
over the random-exit mean, -8.1 pp DD) but **not statistically
distinguishable from random exits inside the high-vol set**. The vol regime
does most of the work; the close sign is a modest overlay. This is weaker
evidence than the point estimate suggests and should be read as such.

**Cut tests** (daily returns with one year removed):

| Cut | Strategy CAGR / DD | TQQQ ex-year CAGR / DD |
|---|---:|---:|
| ex-2016 | 54.25% / 52.06% | 38.66% / 81.68% |
| ex-2020 | **38.55% / 52.06%** | 27.84% / 81.68% |
| ex-2022 | 67.93% / 35.72% | 77.75% / 69.89% |
| ex-2023 | **33.69% / 52.06%** | 21.49% / 81.68% |

Excluding 2020 the strategy still clears the absolute bar (38.55%), by 1.8 pp.
Excluding 2023 it does not (33.69%), though it still beats TQQQ by 12.2 pp on
that cut. Excluding 2022 (a strategy win) it lags TQQQ, as expected. The full
window is not one year, but the 2023 dependence is real.

**Causality:** truncating at 2022-01-03 leaves all prior weights unchanged.
The 15:29 signal and the lagged vol are causal.

## 7. The honest weakness: 2016 and the whipsaw

The close rule is a *momentum* rule in a tape with strong daily reversal. In a
V-shaped crash it sells the bottom and re-enters higher. January 2016 is the
clean example: the strategy lost **-30.2%** while TQQQ lost -16.0%, because it
exited after the down days of 13, 19, 21, 25, 27 and 28 January, each followed
by a rebound (the 24h forward returns on those exit days were +5.2%, +1.9%,
+7.3%, +0.7%, +4.3%, +5.8%). The year finished -2.7% versus TQQQ's +18.6%.

That is the cost of the rule, not a data bug. It is why the strategy's edge is
regime-dependent: it shines in prolonged bears (2018, 2022) and suffers in
sharp reversals (2016). The high-vol gate limits the damage (the vol-only
control made +14.8% in 2016) but does not eliminate it.

The exit days are also **not negative-mean on average**:

| 24h TQQQ forward | Mean | Hit rate |
|---|---:|---:|
| All sessions | +20.6 bp | — |
| Exit days | **+6.8 bp** | 48.6% |
| High-vol non-exit days | +26.6 bp | 45.9% |
| Calm days | +22.2 bp | — |

The rule exits days with a *lower but still positive* mean. It is a variance
and tail filter, not a bad-day oracle. The tail benefit is real: on the 20
worst 24h TQQQ returns the full-weight log loss is -1.85; at the strategy's
weights it is -0.79, so ~57% of the worst-20 log loss is avoided. Three of the
ten worst days were exited outright (2020-03-11 -22.9%, 2020-03-13 -16.2%,
2022-06-10 -16.1%); several others were held at 0.20-0.73 weight. It is not
clairvoyant: 2020-09-02 (-18.1%) and 2020-06-10 (-15.7%) were held at full
weight.

## 8. How this differs from the existing work

| Existing | Difference |
|---|---|
| `overnight-drift-filter` (new mandate) | That uses a 20-day SMA trend haircut of 0.5 every day and a 15:58 decision. This uses a **one-day full-intraday return**, a **vol-gated full exit**, and a 15:30 decision. The signal and the exit are different; the vol-target core is the shared family resemblance, and I do not claim otherwise. |
| `revisit/time-of-day` | Selects a 15:58→10:01 block only after a *sold* close, holds ~30% of nights, exits at 10:01. This holds a continuous 24h position, has no sold-close filter, no 10:01 exit, and exits only on vol-gated weakness. |
| `revisit/overnight-crash-filter` | A selective night-continuation / day-reversal system with a 3-sigma gap budget. This has no gap budget, no day-reversal leg, and a 24h hold. |
| Old 165-day SMA + 4% stop base | No 165-day SMA, no stop, no BIL. |

It is **not a diversifier**: daily correlation to TQQQ is 0.773. It is a
risk-managed way to hold the same underlying, which is what the CAGR/DD bar
asks for.

## 9. Honest verdict and holdout risk

**Pass on the stated dev bar.** 46.21% vs 36.72% CAGR, 53.87% vs 82.29% DD,
1.08 vs 0.82 Sharpe at 1 bp, and it survives 5 bp (44.19%) and 10 bp (41.71%).
The 8-cell grid, the constant-exposure control and the causality check are the
parts I trust most.

What I do **not** claim:

- **The close signal is not the return engine.** The vol-targeted core earns
  44.09% by itself; the close rule adds 2.1 pp and cuts 18.3 pp of drawdown.
  The placebo p-value is 0.22 on both CAGR and DD. Read the close rule as a
  tail/variance overlay, not as an alpha signal.
- **The exit days are not negative on average.** They are +6.8 bp versus
  +26.6 bp for high-vol non-exit days. The gain is compounding and tail
  avoidance, not a negative conditional mean.
- **The 2016 whipsaw is real.** January 2016 lost 30.2% versus TQQQ's 16.0%;
  the year lost 2.7% versus +18.6%. A V-shaped crash in the holdout would hurt.
- **2022 still loses 46.3%.** This is a 3x product; it is not low-risk.
- **Ex-2023 CAGR is 33.69%**, below the absolute bar (though 12.2 pp above
  TQQQ on the same cut). The full-window number depends on 2023 being in the
  sample.
- **The holdout risk is asymmetric.** The strategy historically matches
  (2017) or lags (2019, 2021, 2023) strong-bull years. The full 2016-2026 bar
  is 37.54%; the 10 bp dev CAGR is 41.71%, only 4.2 pp above it. A weak
  holdout can erase the edge. The strategy's case rests on the holdout
  containing at least one 2018/2022-type drawdown, or on the vol-targeted
  core matching the bull.
- **It is not a new source of return.** It is TQQQ with a vol target and a
  crash filter. Correlation 0.773.

My recommendation to the lead: take it to the holdout as a **qualified pass**,
not a clean one. It is the best of the close-momentum designs I tested, it
survives costs, and its DD is genuinely below 60%; but the signal's
incremental statistical evidence is weak, and the 2016 whipsaw is the failure
mode to watch.

## 10. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\intraday-close-momentum\strategy.py
```

Outputs `result.json` in the same directory: dev 1/5/10 bp, benchmark, yearly,
sub-periods, the 8-cell grid, neighbours, controls, exit-day forward returns,
the worst-10 table, placebo, cut tests and the causality flag.
