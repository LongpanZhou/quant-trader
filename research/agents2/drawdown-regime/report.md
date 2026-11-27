# Drawdown-based regime on the 165-day QQQ → TQQQ winner

**Agent:** `drawdown-regime` (round 2, agent 25) · **Date:** 2026-11-25
**Mandate:** use QQQ's drawdown from its 52-week high, its underwater duration,
or its recovery speed as an *additional* regime filter on top of the 165-day SMA
that already defines the round-1 winner. De-risk when QQQ is 5 / 10 / 15% below
its high even while above the SMA; re-enter on a recovery threshold; combine
with the 4% minute stop.

---

## Verdict

**The mandate's central idea fails, and the failure is structural, not a
parameter problem.** Every position-level drawdown overlay I tested loses more
return than drawdown:

| Variant (1 bp) | 10y CAGR / DD | 5y CAGR / DD | vs winner |
|---|---:|---:|---|
| Round-1 winner (reference) | **58.80% / 44.56%** | **49.88% / 33.49%** | — |
| Exit to BIL at dd ≤ −5% | 25.43% / 48.18% | 10.02% / 48.18% | fails both axes |
| Exit to BIL at dd ≤ −10% | 35.52% / **55.92%** | 31.17% / **43.20%** | fails both axes |
| Exit to BIL at dd ≤ −15% | 56.27% / 44.56% | 45.25% / 33.49% | CAGR −2.5 / −4.6 pp, **DD unchanged** |
| Half to BIL at dd ≤ −5% | 43.02% / 37.80% | 29.74% / 37.80% | DD −6.8 pp, CAGR −15.8 pp |
| Half to BIL at dd ≤ −10% | 47.44% / 47.39% | 40.68% / 35.05% | DD *worse*, CAGR −11 pp |
| Exit to BIL after 120 sessions underwater | 52.56% / 49.04% | 40.90% / 33.49% | fails both axes |
| De-lever to QQQ (beta 1) at dd ≤ −8% | 45.58% / 42.48% | 37.85% / 32.82% | fails both axes |

The exit at −10% is *worse on drawdown* than doing nothing (55.92% vs 44.56%),
because it sells after the fall, re-enters near the old high, and then eats the
next leg down. That is the whipsaw cost that Strahle (2025) documents on SPY.

**One drawdown-based overlay does clear the round-2 bar**: keep the position,
but halve the minute stop from 4% to 2% while QQQ is at least 8% below its
52-week high.

| | 10y CAGR / DD | 5y CAGR / DD |
|---|---:|---:|
| Winner, 1 bp | 58.80% / 44.56% | 49.88% / 33.49% |
| **`dd08_stop2`, 1 bp** | **61.57% / 40.34%** | **51.75% / 31.63%** |
| Winner, 5 bp | 54.60% / 47.08% | 45.89% / 34.13% |
| **`dd08_stop2`, 5 bp** | **56.78% / 43.23%** | **47.29% / 32.39%** |
| Winner, 10 bp | 49.50% / 50.06% | 41.05% / 34.93% |
| **`dd08_stop2`, 10 bp** | **51.00% / 46.64%** | **41.89% / 33.35%** |

That is **strict dominance at every cost level**, plus lower drawdown in every
one of the 82 rolling 3-year windows. But the CAGR improvement is **not
statistically significant** (block-bootstrap p = 0.26), the placebo controls
show a tight stop helps almost anywhere *except* the −5%…−8% band, and
walk-forward parameter selection is unstable. I therefore report it as a formal
pass with a strong risk-profile improvement and a weak return edge — **not** as
a reason to retire the winner.

At 1 bp the companion variant `dd08_stop2_75` (2% stop **and** 25% BIL in the
deep state) meets target #2 at every cost level: 57.55% / 41.29% and
48.90% / 30.59% at 1 bp, i.e. −1.25 pp / −3.27 pp and −0.98 pp / −2.90 pp versus
the winner. It is the safer choice if the DD reduction matters more than CAGR.

---

## 1. Idea and prior evidence

Three literatures shaped the design.

**Drawdown-based de-risking has a known cost.** Strahle (2025) tests exactly
this rule family on SPY 2000–2025: fixed drawdown thresholds, linear scaling and
moving averages. All three cut volatility and max drawdown (fixed thresholds
less than moving averages), but CAGR fell from 8.03% to 5.27–7.41%, and **none
improved Sharpe or Sortino**. The two stated causes are precisely the ones I
measure below: "remaining underexposed during recoveries, an effect exacerbated
by fast recoveries, and whipsaws during shallow drawdowns that reversed before
losses could be meaningfully limited." Only the Calmar ratio improved, and for
fixed thresholds only marginally (0.18 vs 0.15).
<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7542498>
(summary mirrored by Quantpedia: <https://quantpedia.com/strategies/asset-class-trend-following>)

Van Hemert, Ganz, Harvey, Rattray, Sanchez Martin & Yawitch (2020) reach the
same conclusion in the *Journal of Portfolio Management*: "drawdown-based rules
can be used as a risk reduction technique, but this affects both expected
returns and risk." <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3583864>
<https://www.man.com/insights/drawdowns>

**Buying weakness at a momentum horizon loses.** AQR's *Hold the Dip* (2025)
tests 196 dip-buying rules on the S&P 500 from 1965: 60%+ have lower
risk-adjusted returns than buy-and-hold, average alpha is +0.5%/yr and only 8%
is significant; during the four worst drawdowns since 2000, dip-buying lost
18.4% on average while trend-following gained 28.6%. Their explanation — "value
investing at a momentum horizon" — is the mirror image of my finding that
*selling* a drawdown in an uptrend is also fighting momentum.
<https://alphaarchitect.com/is-trend-following-better-than-buy-the-dip/>
<https://www.aqr.com/Insights/Research/Alternative-Thinking/Hold-the-Dip>
Bonini, Shohfi & Simaan (2024), *European Financial Management* 30(4), find no
reliable dip-buying outperformance: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3835376>

**Stops only add value when returns have momentum.** Kaminski & Lo (2014) show
the "stopping premium" is positive only under positive serial correlation;
otherwise a stop is a cost. This is the licence for a stop that is *tighter*
when the market is already in a drawdown (crashes are momentum), and for *not*
using a position-level drawdown exit in ordinary pullbacks (which mean-revert).
<https://doi.org/10.1016/j.finmar.2013.07.001>

Theory (Grossman & Zhou 1993; Chekhlov, Uryasev & Zabarankin 2005) also treats a
drawdown constraint as costly insurance, not as alpha:
<https://doi.org/10.1111/j.1467-9965.1993.tb00044.x>,
<https://math.columbia.edu/~chekhlov/ChekhlovUryasevZabarankin--03-2004.pdf>

---

## 2. Data, harness, no look-ahead

- Local adjusted 1-minute QQQ / TQQQ / BIL from `data/intraday-hf`, regular
  session only, via `research/bt.py` (`bt.panel`, 500 calendar days of warm-up).
  1,057,023 bars, 2,718 sessions (2016-01-04 → 2026-10-23). Test windows:
  10y = 2017-01-03 → 2026-10-23; 5y = 2021-10-25 → 2026-10-23.
- Signals at bar *i* use only bars ≤ *i*; fills at bar *i+1*'s open; slippage on
  traded notional; 2% rebalance band; long-only; weights sum to ≤ 1.
- The drawdown is computed on **daily closes through session k−1**:

  ```
  dd(k) = QQQ_close(k-1) / max(QQQ_close(k-252 .. k-1)) - 1
  ```

  so it is known before session k opens. `strategy.py` asserts this identity at
  the last session (`check_no_lookahead`).
- BIL is the risk-off asset and earns its own (small) carry; no separate cash
  rate is added.
- Fast exact simulator: `fastsim.py` reproduces `bt.simulate` to the cent
  (identical 657 fills and zero equity difference on the winner), which made the
  ~100-variant grid practical.

---

## 3. Exact rules

### 3.1 Base (round-1 winner, reproduced exactly)

```
For each session d:
  risk_on = QQQ_close(d-1) > SMA165(d-1)
  if not risk_on: hold BIL all session
  else:
    armed = QQQ first-minute price < MA20(d-1) * 1.01
    base  = TQQQ open of session d
    hold TQQQ unless (armed and TQQQ close < base * (1 - stop))
    after a stop: BIL for the rest of the session and the night;
                  next session restarts in TQQQ if risk_on
```

Reproduction check: **58.80% / 44.56%** (10y) and **49.88% / 33.49%** (5y) at
1 bp, 657 and 337 fills — exactly the published winner.

### 3.2 Drawdown overlays (tested)

```
dd_state(k):                              # daily, known before the open
  if not risk_on(k): out
  elif currently blocked:
      unblock when dd(k) >= -reenter
  else:
      block when dd(k) <= -exit
  while blocked: weight_TQQQ = scale   (0 = all BIL, 0.5 = half BIL)
```

| Name | exit | re-enter | blocked weight |
|---|---:|---:|---:|
| `dd05_bil` | −5% | −2% | 0 |
| `dd10_bil` | −10% | −5% | 0 |
| `dd15_bil` | −15% | −10% | 0 |
| `dd05_half` | −5% | −2% | 0.5 |
| `dd10_half` | −10% | −5% | 0.5 |
| `uw120_bil` | ≥120 sessions underwater | ≤10 sessions | 0 |
| `dd08_qqq` | −8% | −4% | 100% QQQ instead of TQQQ |

### 3.3 Conditional stop (the variant that works)

```
stop = 2% if dd(k) <= -8% else 4%          # everything else identical to the base
```

The arming rule (QQQ first minute < MA20 × 1.01) is unchanged, so the 2% stop is
still only used in weak short-term trends. Stop events rise from 160 to 180 over
the 2016–2026 panel; fills from 657 to 737 over 10y (turnover 21,215× vs
17,331×).

`dd08_stop2_75` adds `weight_TQQQ = 0.75` (rest BIL) while dd ≤ −8%.

---

## 4. Results

### 4.1 Headline, 1 bp (1-minute equity marks)

| Variant | 10y CAGR | 10y DD | 10y Sharpe | 5y CAGR | 5y DD | 5y Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| TQQQ buy & hold (README bar) | 39.28% | 81.68% | 0.83 | 13.47% | 81.68% | 0.53 |
| Winner | 58.80% | 44.56% | 1.24 | 49.88% | 33.49% | 1.16 |
| `dd08_stop2` | **61.57%** | **40.34%** | **1.30** | **51.75%** | **31.63%** | **1.19** |
| `dd08_stop2_75` | 57.55% | 41.29% | 1.27 | 48.90% | **30.59%** | 1.17 |
| `dd05_bil` | 25.43% | 48.18% | 0.85 | 10.02% | 48.18% | 0.46 |
| `dd10_bil` | 35.52% | 55.92% | 0.94 | 31.17% | 43.20% | 0.88 |
| `dd15_bil` | 56.27% | 44.56% | 1.22 | 45.25% | 33.49% | 1.12 |
| `dd08_qqq` | 45.58% | 42.48% | 1.13 | 37.85% | 32.82% | 1.01 |

Ending equity on $100k for `dd08_stop2`: **$11.02M** (10y) and **$802.9k** (5y)
versus $9.30M / $754.8k for the winner.

### 4.2 Cost sensitivity

| Costs | `dd08_stop2` 10y | 5y | `dd08_stop2_75` 10y | 5y | Winner 10y | 5y |
|---|---:|---:|---:|---:|---:|---:|
| 1 bp | **61.57 / 40.34** | **51.75 / 31.63** | 57.55 / 41.29 | 48.90 / 30.59 | 58.80 / 44.56 | 49.88 / 33.49 |
| 5 bp | **56.78 / 43.23** | **47.29 / 32.39** | 53.14 / 43.99 | 44.72 / 31.29 | 54.60 / 47.08 | 45.89 / 34.13 |
| 10 bp | **51.00 / 46.64** | **41.89 / 33.35** | 47.80 / 47.23 | 39.68 / 32.18 | 49.50 / 50.06 | 41.05 / 34.93 |

`dd08_stop2` dominates the winner at the *same* cost on both windows at all
three levels. `dd08_stop2_75` meets the "lower DD, CAGR within 2 pp" bar at all
three levels.

### 4.3 Yearly returns (calendar year, 1 bp)

| Year | Winner | `dd08_stop2` | `dd08_stop2_75` | `dd10_bil` | `dd05_bil` | TQQQ |
|---|---:|---:|---:|---:|---:|---:|
| 2017 | 118.8% | 118.8% | 118.8% | 118.8% | 100.9% | 114.5% |
| 2018 | 0.5% | **5.4%** | 3.7% | −15.8% | 5.7% | −20.8% |
| 2019 | 47.9% | 48.2% | 50.0% | 47.9% | 5.1% | 148.2% |
| 2020 | 183.9% | 183.1% | 144.7% | 45.8% | 128.3% | 104.1% |
| 2021 | 60.6% | **70.7%** | 70.3% | 53.5% | 9.1% | 81.1% |
| 2022 | −18.0% | −18.0% | −17.3% | −15.3% | −9.7% | −79.4% |
| 2023 | 149.0% | **161.7%** | 144.1% | 105.1% | 57.2% | 192.0% |
| 2024 | 68.0% | 62.0% | 56.5% | 23.1% | 44.7% | 62.4% |
| 2025 | 43.3% | 43.3% | 43.3% | 43.3% | −5.9% | 32.1% |
| 2026 | 16.8% | **22.5%** | 22.7% | −3.8% | −21.6% | 22.6% |

`dd08_stop2` beats the winner in 5 years (2018, 2019, 2021, 2023, 2026), ties
in 3 (2017, 2022, 2025) and loses in 2 (2020, −0.8 pp; 2024, −6.0 pp). It beats
TQQQ in 5 of 10 years (2017, 2018, 2020, 2022, 2025) and loses only in the
melt-ups (2019, 2021, 2023) and by a hair in 2024/2026.

(The harness's own TQQQ 1-minute benchmark from the window start is 39.38% /
82.29% and 14.29% / 82.29%; the README's 39.28% / 81.68% and 13.47% / 81.68% use
a pre-window starting price. Pass/fail uses the stricter README bar.)

The de-risking variants show the expected failure shape: they save money in
2022 but give up the recovery — `dd10_bil` makes 45.8% in 2020 versus 183.9%,
and `dd05_bil` makes 5.1% in 2019 and −5.9% in 2025.

### 4.4 Yearly max drawdown (1-minute marks)

| Year | Winner | `dd08_stop2` | `dd10_bil` | `dd05_bil` |
|---|---:|---:|---:|---:|
| 2017 | 17.1% | 17.1% | 17.1% | 16.4% |
| 2018 | 41.0% | **38.1%** | 47.2% | 24.2% |
| 2019 | 32.0% | **30.3%** | 32.0% | 33.9% |
| 2020 | 39.3% | **34.7%** | 49.9% | 20.6% |
| 2021 | 41.5% | **37.8%** | 44.1% | 30.3% |
| 2022 | 21.8% | 21.8% | 18.7% | 12.5% |
| 2023 | 26.6% | **25.6%** | 26.6% | 25.9% |
| 2024 | 29.4% | **28.4%** | 43.2% | 19.4% |
| 2025 | 24.1% | 24.1% | 24.1% | 31.5% |
| 2026 | 33.5% | **31.6%** | 41.2% | 48.2% |

`dd08_stop2` has a lower yearly max drawdown in every year where it differs
(equal in 2017, 2022, 2025) — this is the most consistent feature of the result.

### 4.5 Max-drawdown episodes

| Variant | 10y peak → trough | depth | 5y peak → trough | depth |
|---|---|---:|---|---:|
| Winner | 2018-03-13 → 2019-06-05 | 44.56% | 2026-06-22 → 2026-07-30 | 33.49% |
| `dd08_stop2` | 2018-03-13 → 2019-06-06 | **40.34%** | 2026-06-22 → 2026-07-30 | **31.63%** |
| `dd10_bil` | 2020-09-02 → 2021-03-25 | 55.92% | 2024-07-10 → 2024-09-12 | 43.20% |
| `dd15_bil` | 2018-03-13 → 2019-06-05 | 44.56% | 2026-06-22 → 2026-07-30 | 33.49% |

The 10y episode is the 2018/2019 whipsaw, not COVID; the 5y episode is the
June–July 2026 selloff. `dd10_bil`'s worst episode moves to a *different* and
deeper event (the 2020–21 growth scare), because the rule sold the September
2020 low and re-entered near the high.

### 4.6 Rolling 3-year windows

82 monthly-stepped 3-year windows from 2017-01 to 2026-10 (the round-1 report
used 27 quarterly windows; monthly steps give a denser consistency check).

| | Winner | `dd08_stop2` | `dd08_stop2_75` |
|---|---:|---:|---:|
| Median CAGR | 62.1% | **63.3%** | 57.8% |
| Worst 3y CAGR | 27.3% | **35.4%** | 33.2% |
| Median max DD | 41.5% | **37.8%** | 38.0% |
| Worst max DD | 44.6% | **40.3%** | 41.3% |
| Beats TQQQ on CAGR **and** DD | 70/82 | **73/82** | 63/82 |
| vs winner: higher CAGR | — | **73/82** | 13/82 |
| vs winner: lower DD | — | **82/82** | 82/82 |
| vs winner: both | — | **73/82** | 13/82 |

The most useful number is the **worst** 3-year CAGR: 35.4% versus 27.3%. The
tighter stop in deep drawdowns truncates the bad windows rather than boosting
the good ones. The worst relative window is 2023-06 → 2026-06 (76.3% vs 80.2%,
DD 28.4% vs 29.4%); the best is 2017-09 → 2020-09 (80.2% vs 69.4%).

---

## 5. Why the position-level drawdown rule fails

Three independent pieces of evidence.

### 5.1 The drawdown is largely redundant with the 165-day SMA

| Threshold | All sessions | Regime ON | Share already in BIL |
|---|---:|---:|---:|
| dd ≤ −5% | 811 | 384 | 53% |
| dd ≤ −8% | 547 | 142 | 74% |
| dd ≤ −10% | 454 | 89 | **80%** |
| dd ≤ −15% | 304 | 48 | **84%** |

By the time QQQ is 10% below its 52-week high, the SMA regime has already put
the strategy in BIL four sessions out of five. The overlay can only trade the
residual 20%, and it pays a full round trip to do so.

### 5.2 Where it *does* bind, forward returns are higher, not lower

Forward TQQQ returns after regime-ON sessions, by drawdown bucket:

| dd bucket | sessions | fwd 5d | hit | fwd 20d | hit | QQQ fwd 20d |
|---|---:|---:|---:|---:|---:|---:|
| 0 … −3% | 1,409 | +0.88% | 61% | +2.67% | 64% | +1.09% |
| −3 … −5% | 333 | +1.12% | 56% | +6.86% | 72% | +2.55% |
| −5 … −8% | 242 | +1.16% | 60% | +8.32% | 77% | +3.06% |
| **−8 … −12%** | **82** | **+5.52%** | **72%** | **+11.47%** | **87%** | **+4.22%** |
| −12 … −20% | 45 | −2.19% | 56% | +0.19% | 53% | +0.89% |
| ≤ −20% | 15 | +6.17% | 73% | +9.99% | 73% | +3.81% |

The deepest bucket that still contains many regime-ON sessions (−8…−12%) has
the **best** forward returns of any bucket: +11.5% over 20 days with an 87% hit
rate. De-risking there is selling the highest-expected-return state. Only
−12…−20% is poor, and it has just 45 ON sessions (the SMA is out for most of
that range).

This is the mirror image of the AQR dip-buying result: at a weeks-to-months
horizon, a drawdown is a momentum phenomenon (bad) only when the trend is
already broken; inside an intact trend it is a mean-reversion phenomenon (good).
The 165-day SMA already separates those two cases, which is why the drawdown
adds nothing.

### 5.3 The drawdowns that matter are too shallow or too late

- **10y max DD (2018-03-13 → 2019-06-06):** the regime is ON for 229 of 311
  sessions, and the deepest QQQ drawdown *while invested* is only **−10.36%**
  (one single session at ≤ −10%). A −10% gate can therefore do almost nothing;
  a −5% gate binds on 61 sessions and destroys the return (25.43% CAGR).
- **5y max DD (2026-06-22 → 2026-07-30):** all 29 sessions are regime-ON, but
  QQQ's deepest drawdown is **−11.25%** and only 5 sessions are at ≤ −8%. A −15%
  rule never fires; a −10% rule fires on the last day (2026-07-30), at the
  equity trough. This is why `dd15_bil` leaves the 5y DD *exactly* at 33.49%.

So the 5% threshold is too shallow (it whipsaws in every normal pullback) and
the 10–15% thresholds are too deep (they fire after the damage, if at all).

---

## 6. The variant that does work, and its honest weaknesses

`dd08_stop2` wins because it acts **inside the session** rather than by moving
the book days later: when the market is already 8% below its high, a 2% TQQQ
drop from the open is a much better crash signal than a 4% one.

### 6.1 Attribution is fat-tailed

Daily log-return difference versus the winner over 10y: **+16.95 pp total**,
but the five largest single days sum to **60.95 pp gross**:

| Day | diff |
|---|---:|
| 2020-03-09 | +22.97 pp |
| 2020-03-02 | −12.28 pp |
| 2020-02-27 | +8.87 pp |
| 2020-03-04 | −8.83 pp |
| 2020-09-21 | −8.01 pp |

By year: 2018 +4.76, 2020 −0.28, 2021 +6.10, 2023 +4.96, 2024 −3.60,
2026 +4.82 pp. The 2020 net is zero despite four ±9–23 pp days — that year is
pure path noise. The genuine, repeatable part is the *drawdown* reduction, not
the return.

A 20-day block bootstrap on the daily difference: mean **+0.69 bp/day**, sd
**1.05 bp**, one-sided **p(≤ 0) = 0.26**. The CAGR edge is not statistically
distinguishable from zero.

### 6.2 Placebo controls (10y / 5y CAGR / DD, 1 bp)

| Condition for the 2% stop | 10y | 5y |
|---|---:|---:|
| always (no condition) | 53.15 / 43.77 | 37.95 / 43.77 |
| dd between 0 and −5% | 61.26 / 42.15 | 50.94 / 32.04 |
| dd between −3 and −8% | 49.97 / 44.87 | 39.35 / 44.87 |
| dd between −5 and −8% | 48.34 / 46.29 | 35.31 / 46.29 |
| **dd ≤ −8%** | **61.57 / 40.34** | **51.75 / 31.63** |
| dd ≤ −6% | 58.07 / 43.58 | 48.74 / 35.62 |
| underwater ≥ 60 sessions | 61.00 / 41.95 | 52.58 / 33.49 |

Two uncomfortable facts. First, an *unconditional* 2% stop is much worse
(37.95% 5y CAGR), so the condition genuinely matters. Second, a 2% stop near the
high (dd 0…−5%) also beats the winner — the benefit is not unique to deep
drawdowns. The only clearly toxic band is −5%…−8%, the shallow correction that
usually V-recovers. The economic story ("crashes are momentum, pullbacks are
mean reversion") survives, but it is a *band* story, not a monotone one.

### 6.3 Parameter surface (10y / 5y CAGR / DD, 1 bp)

| dd threshold \ stop | 1.5% | 2.0% | 2.5% |
|---|---|---|---|
| −6% | — | 58.07 / 43.58 | 48.74 / 35.62 |
| −7% | 56.32 / 40.19 | 60.36 / 40.23 | 57.92 / 40.99 |
| **−8%** | 59.62 / 40.00 | **61.57 / 40.34** | 58.63 / 45.54 |
| −9% | — | 58.89 / 44.08 | 57.06 / 47.31 |
| −10% | — | 58.69 / 43.34 | 56.74 / 47.31 |
| −15% | — | 60.08 / 44.56 | 60.23 / 44.56 |

The 7–8% region with a 1.5–2.0% stop is a plateau (10y DD 40.0–40.3%, CAGR
56.3–61.6%). Outside it the result decays quickly: at −9% the 5y DD is 32.95%
and at −10% or deeper it is unchanged at 33.49% — the rule stops binding on the
2026 event.

### 6.4 Sub-periods and walk-forward (1 bp)

| Period | Winner CAGR / DD | `dd08_stop2` CAGR / DD |
|---|---:|---:|
| 2017–2019 | 48.85 / 44.56 | 51.34 / 40.34 |
| 2020–2022 | 56.73 / 41.50 | 59.80 / 37.82 |
| 2023–2026 | 67.48 / 33.49 | 70.22 / 31.63 |
| 2017 – 2021-10 | 69.29 / 44.56 | 73.13 / 40.34 |
| 2021-10 – 2026-10 | 49.70 / 33.49 | 51.56 / 31.63 |

Better on both axes in all five sub-periods. But when the (threshold, stop) pair
is *selected* on one half and applied to the other:

| Fit | Selected | Test | OOS result | Winner |
|---|---|---|---|---|
| 2017–2021 | (7%, 2.0%) | 2022–2026 | 47.72 / 33.30 | 49.70 / 33.49 |
| 2022–2026 | (8%, 2.5%) | 2017–2021 | 65.53 / 45.54 | 69.29 / 44.56 |

Out-of-sample the rule is neutral-to-slightly-worse. The *fixed* 8%/2% rule
works in both halves, but a procedure that re-picks the parameters every few
years would not have captured it. That, plus p = 0.26, is why I do not call this
a new winner.

---

## 7. Pass / fail summary

Against TQQQ buy-and-hold (39.28% / 81.68% 10y, 13.47% / 81.68% 5y): the
surviving rule and the milder overlays pass, but **the two deepest exit rules do
not**. `dd05_bil` (25.43% 10y CAGR) and `dd10_bil` (35.52%) both fall below
TQQQ's 39.28% 10y CAGR, even though their drawdowns are below 81.68%. That makes
the negative result stronger: exiting on a drawdown can underperform the
leveraged asset it is trying to protect against.

Against the round-1 winner, at the same cost level:

| Variant | 1 bp | 5 bp | 10 bp |
|---|---|---|---|
| `dd08_stop2` | **strict dominance** | **strict dominance** | **strict dominance** |
| `dd08_stop2_75` | lower DD, CAGR within 2 pp | same | same |
| `dd05_bil` | fail | fail | fail |
| `dd10_bil` | fail (worse DD) | fail | fail |
| `dd15_bil` | fail (DD unchanged) | fail | fail |
| `dd05_half` | fail (CAGR −15.8 pp) | fail | fail |
| `dd10_half` | fail | fail | fail |
| `uw120_bil` | fail | fail | fail |
| `dd08_qqq` | fail | fail | fail |

`dd08_stop2` therefore satisfies round-2 criterion #1 (strict dominance) on
both windows at all three cost levels, and `dd08_stop2_75` satisfies criterion
#2.

---

## 8. Limitations

1. **Not statistically significant.** The daily return difference has a
   one-sided p-value of 0.26. The drawdown reduction is consistent (82/82
   rolling windows) but the return improvement is within noise.
2. **The threshold is suspiciously well placed.** 8% sits just below the 11.25%
   maximum drawdown of the 2026 episode; at −9% only two sessions in that
   episode bind, and at −10% or deeper the 5y drawdown reduction disappears
   entirely. A future drawdown that stops at −7% would not trigger the rule at
   all.
3. **Placebo sensitivity.** A 2% stop near the high also improves the result;
   the benefit is not monotone in drawdown depth. The −5…−8% band is actively
   harmful, which is a fragile shape.
4. **Crash-path dependence.** Four 2020 days contribute ±9–23 pp each and net
   to zero; a different intraday path in March 2020 could move the 10y CAGR by
   several points either way.
5. **One sample, two crashes.** 2020 and 2026 dominate the drawdown side; 2018
   and 2023 dominate the return side. There is no out-of-sample decade.
6. **Costs.** 737 fills over 10y is ~74/year; at 10 bp the drag is ~10 pp of
   CAGR. The strategy is tax-inefficient and the 1 bp row is optimistic for a
   retail stop.
7. **Data.** The 2026 tape (June–July selloff) is the entire 5y drawdown; daily
   QQQ/TQQQ betas are consistent (2.97 in 2026 vs 2.97 in 2023–25), but the
   minute fills on the worst days are the ones that matter and cannot be
   cross-checked against another venue.
8. **`dd08_stop2_75` meets criterion #2 mainly by holding less risk**, not by
   timing: it is 25% BIL for 5% of sessions. Its value is the 30.59% 5y DD.

---

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents2\drawdown-regime\strategy.py
```

`strategy.py` rebuilds the panel (using the read-only round-1 cache if present,
otherwise `bt.panel`), asserts the no-look-ahead identity of the drawdown,
evaluates all ten variants at 1/5/10 bp, computes yearly returns, yearly
drawdowns, the forward-return table and the block bootstrap, and writes
`result.json`.

Supporting files (exploration only): `ddlib.py` (panel, regime, state
machines), `fastsim.py` (exact fast simulator), `explore.py` (drawdown map),
`sweep1.py` … `sweep6.py` (mandate variants, throttle, conditional stop,
controls), `robust.py` (sub-periods, rolling windows, walk-forward),
`attrib.py` (day-level attribution), `diag.py`, `facts.py`, `show*.py`.

No core repository file was modified. `research/bt.py` is imported for
`stats`/`benchmark`/`yearly` only.

---

## 10. References

1. Strahle, O. (2025). *How Does Reducing Exposure During Drawdowns Impact
   Portfolio Performance?* SSRN 7542498.
   <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7542498>
   (figures via Quantpedia: <https://quantpedia.com/strategies/asset-class-trend-following>)
2. van Hemert, O., Ganz, M., Harvey, C. R., Rattray, S., Sanchez Martin, E., &
   Yawitch, D. (2020). *Drawdowns.* Journal of Portfolio Management / SSRN
   3583864. <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3583864>
   <https://www.man.com/insights/drawdowns>
3. AQR Capital Management (2025). *Hold the Dip.* Alternative Thinking 2025(4).
   <https://www.aqr.com/Insights/Research/Alternative-Thinking/Hold-the-Dip>
   Summary: <https://alphaarchitect.com/is-trend-following-better-than-buy-the-dip/>
4. Bonini, S., Shohfi, T., & Simaan, M. (2024). *Buy the dip?* European
   Financial Management 30(4), 2033–2070.
   <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3835376>
5. Kaminski, K. M., & Lo, A. W. (2014). *When do stop-loss rules stop losses?*
   Journal of Financial Markets 18, 234–254.
   <https://doi.org/10.1016/j.finmar.2013.07.001>
6. Grossman, S. J., & Zhou, Z. (1993). *Optimal investment strategies for
   controlling drawdowns.* Mathematical Finance 3(3), 241–276.
   <https://doi.org/10.1111/j.1467-9965.1993.tb00044.x>
7. Chekhlov, A., Uryasev, S., & Zabarankin, M. (2005). *Portfolio optimization
   with drawdown constraints.*
   <https://math.columbia.edu/~chekhlov/ChekhlovUryasevZabarankin--03-2004.pdf>
8. Faber, M. T. (2007). *A Quantitative Approach to Tactical Asset Allocation.*
   SSRN 962461. <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461>
