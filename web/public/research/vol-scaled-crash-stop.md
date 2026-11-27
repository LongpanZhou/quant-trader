# A volatility-scaled crash stop: tighten in calm markets, cap at the round-1 4%

**Agent:** `vol-scaled-crash-stop` · Round 2 · 2026-11-25
**Mandate:** replace the round-1 winner's fixed 4% stop with an ATR- or
volatility-scaled distance, and test partial de-risking to QQQ instead of
all-or-nothing BIL. Keep the QQQ 165-day regime and the MA20 arm gate.

---

## Verdict

**The idea works, but only in one direction: scale the stop *down* when
volatility is low, and never scale it *up* in a crisis.** Replacing the fixed
4% stop with

```
stop_dist[d] = clip(0.70 * ATR14(TQQQ daily, through prior close), 2.5%, 4.0%)
```

beats the round-1 winner on both windows at 1 bp:

| Window | Winner CAGR | Winner DD | ATR stop CAGR | ATR stop DD | Δ CAGR | Δ DD |
|---|---:|---:|---:|---:|---:|---:|
| 10y (2017-01-03→2026-10-23) | 58.80% | 44.56% | **62.60%** | **40.94%** | +3.80 pp | −3.62 pp |
| 5y (2021-10-25→2026-10-23) | 49.88% | 33.49% | **54.88%** | **33.49%** | +5.00 pp | 0.00 pp |

- **Strict dominance on the 10-year window**: higher CAGR *and* lower max
  drawdown (the same 2018-03→2019-06 episode, 3.6 pp shallower).
- **On the 5-year window the CAGR is +5.0 pp and the max drawdown is identical**
  — the same 2026-06-22 → 2026-07-30 peak and trough, and the same value to
  floating-point precision (0.3349147966113107 vs 0.3349147966113109; a 1-ULP
  difference, not an economic one). It is identical *by construction*: on all
  eight stop days of the 2026 June–July slide the capped ATR distance is exactly
  4.00%, so the exits are the winner's (Section 4.4). This is a CAGR win plus a
  drawdown tie, **not** a 5-year drawdown improvement — I do not claim one.
  Read literally, the README's "strict dominance" test therefore does not pass
  on the 5y window (a tie is not "lower"); economically the strategy is never
  worse and is 5 pp/yr better.
- It still beats TQQQ buy-and-hold (39.28% / 81.68% on 10y, 13.47% / 81.68% on
  5y) by a wide margin, and passes at 1, 5 and 10 bp.
- **Consistency**: in 28 rolling 3-year windows the ATR stop has a higher CAGR
  than the winner in **28/28**, a lower drawdown in **26/28**, and both in
  **26/28**; it beats TQQQ on both in 24/28. Median edge vs the winner:
  +5.1 pp CAGR, −0.95 pp DD.
- **Partial de-risking to QQQ fails.** 50% QQQ / 50% BIL after the stop costs
  ~2.5 pp of CAGR and *raises* the 10y max drawdown (42.73% vs 40.94% for the
  same stop with all-BIL); the 5y drawdown is 0.13 pp lower. All-or-nothing BIL
  is the better crash exit. (The combination still beats the winner, because the
  stop improvement is large enough to pay for the worse exit; but it is strictly
  dominated by the same stop with a full BIL exit.)
- **Uncapped volatility scaling fails.** Letting the ATR distance widen to 6%
  in high-vol regimes loses the 5y protection (39.00% DD). On 2024-08-02 the
  uncapped stop wanted 5.21% — wider than the day's entire −4.44% range — so it
  never fired and rode a −16.0% overnight gap. The 4% cap fired at 10:12 and
  avoided it. That mechanism is why the cap is part of the headline strategy.

The stop distance is not fixed: it is 2.5% in calm markets (83% of
armed 2017 sessions) and 4.0% in stress (87% of armed 2020 sessions), with a
median of 3.23% on armed days. The round-1 stop was a good *crisis* stop and a
poor *calm-market* stop; the ATR scale fixes the second without touching the
first.

---

## 1. Idea and prior work

The round-1 winner is a slow daily regime (QQQ above its 165-day SMA → TQQQ,
else BIL) plus a 4% intraday crash stop that is armed only when QQQ is at or
below its 20-day MA. Its stop is a tail hedge: 153 stop events in the 2017–2026
window, mean exit→next-open move −0.48% (a saving, before costs) but a median
of only −0.39% and 54% of events negative (i.e. unnecessary ex post); the edge
is concentrated in a handful of gap nights. Two literatures suggested the fixed
distance was the weak part:

1. **Stop-losses add value when returns are conditionally negatively skewed /
   momentum-like** (Kaminski & Lo, *Journal of Financial Markets* 18, 2014).
   The same paper shows a 0/1 stop always lowers expected return under a random
   walk, so the level matters: too tight and you pay the whipsaw, too wide and
   you keep the tail.
2. **Stop distance should scale with volatility.** This is the standard
   ATR/Chandelier construction — exit `N × ATR` below the recent high or entry
   ([Chandelier exit](https://quantarenas.com/strategy/trend-17-chandelier-exit),
   [volatility-adjusted stop comparison](https://volatilitybox.com/research/volatility-adjusted-stop-losses)) —
   and it is the trading-desk version of volatility-managed portfolios
   (Moreira & Muir, *Journal of Finance* 2017). The rationale is volatility
   clustering: a 2% move is two hours of normal travel in a calm market and
   twenty minutes in a crisis, so a fixed percentage is either noise-tight or
   uselessly wide depending on the regime
   ([volatility clustering](https://arrowalgo.com/volatility-clustering),
   [regime note](https://blockcircle.com/blog/volatility-clustering-and-what-it-means-for-risk-management)).

The counter-evidence is real and kept me honest: Cesar Alvarez's large stop-loss
study found ATR-scaled stops produced roughly the same result as percentage
stops and that *trailing* ATR stops underperformed
([summary](https://bettersystemtrader.com/037-cesar-alvarez-studies-stop-losses));
a 20,000-trade FX study finds a sweet spot at 1.3–1.8× ATR and shows sub-1.0×
ATR stops collapse under microstructure noise
([FXNX](https://fxnx.com/en/blog/stop-loss-distance-vs-hit-rate-20-000-trade-study)).
So the prior is "ATR scaling is not magic"; the interesting question is whether
it helps *this* overlay, where the event being hedged is an overnight gap rather
than trade-by-trade expectancy.

It does — but asymmetrically, and that is the finding. For a crash overlay the
volatility relationship is the opposite of the trading-desk intuition: in high
volatility you must **not** widen the stop, because high-volatility regimes are
exactly when the gap nights happen. The right scaling is one-sided: tight in
calm markets, capped at the level that was already validated in crises.

One calibration detail is specific to TQQQ. Three-times daily leverage
multiplies both the distance and the drag: TQQQ's daily volatility is ~3× QQQ's
and it trailed 3× QQQ by ~22 log points a year over 2016–2026, about 15 of them
from volatility
([FinLab](https://finlab.finance/en/blog/leveraged-etf-decay)). A 2.5–4% stop on
TQQQ is therefore only a 0.8–1.3% stop on the index — a normal intraday move —
and the slow regime, not the stop, is what handles the multi-month decay. The
stop only has to handle the intraday/overnight tail.

---

## 2. Exact rules

```
For each session d (09:30–15:59 ET):
  SMA165[d] = mean(QQQ daily close, d-165 … d-1)
  MA20[d]   = mean(QQQ daily close, d-20  … d-1)
  ATR14[d]  = mean true range of TQQQ daily bars, d-14 … d-1, / TQQQ close[d-1]
  dist[d]   = min(max(0.70 × ATR14[d], 0.025), 0.040)

  risk_on = QQQ close[d-1] > SMA165[d]
  armed   = QQQ close of the 09:30 bar < MA20[d] × 1.01

  if not risk_on:
      hold BIL all session
  else:
      base  = TQQQ open of session d
      state = TQQQ
      for each minute i:
          if armed and state == TQQQ and TQQQ close[i] < base × (1 − dist[d]):
              state = BIL            # target set at bar i, fills at open[i+1]
          weight[i] = state
      # after the stop: BIL for the rest of the session and the night;
      # next session restarts in TQQQ if the regime is still on
```

- One position at a time: 100% TQQQ or 100% BIL. No leverage beyond 100% TQQQ,
  no shorts, no intraday re-entry.
- The stop is measured from the **session open** (as in the winner); it is armed
  only below the 20-day MA (+1%); it exits at the **next bar's open**; it stays
  out for the rest of the session and the night.
- ATR is computed from the 1-minute panel aggregated to daily bars, so it uses
  the same adjusted prices as the fills. `ATR14[d]` uses bars through day d−1's
  close only. The regime uses day d−1's close. The arm gate uses the 09:30 bar's
  close of day d. Nothing uses a bar after the one that sets the weight.
- `0.70 × ATR14` is the only new free parameter. The 2.5% floor and the 4.0%
  cap are bounding choices: 4.0% is the round-1 stop (inherited, not fitted),
  and 2.5% is the smallest distance that is still ~16× TQQQ's 1-minute ATR
  (median 1m ATR14 ≈ 0.16%), i.e. outside minute-level microstructure noise.

### Why not a literal "2× or 3× ATR"?

The mandate suggests 2×/3× ATR stops. A raw ATR multiple is meaningless without
fixing the bar size, and the natural readings are all wrong for a session-open
stop:

| ATR definition | median ATR | 3× ATR |
|---|---:|---:|
| 1-minute ATR(14) | ~0.16% | ~0.47% — fires on noise, dozens of times a day |
| 5-minute ATR(14) | ~0.33% | ~1.0% — fires on almost every armed day (tested: 502 stops, 49.4% CAGR) |
| daily ATR(14) | ~4.2% | ~12.7% — never fires before the regime flips |

Only the daily formulation is on the right scale, and there a *fraction* of one
ATR (≈0.7) is the session-scale stop. I therefore test 0.45–0.95× daily ATR(14),
the equivalent 5-minute formulation (6–11× ATR5m, since a daily range is
≈√78 ≈ 8.8 five-minute ranges), and 1.0–1.6× 20-day realized daily volatility.
The literal 3× ATR5m is reported as a negative control.

---

## 3. Results

### 3.1 Headline (1 bp, 1-minute marks)

| Metric | ATR stop 10y | Winner 10y | ATR stop 5y | Winner 5y |
|---|---:|---:|---:|---:|
| CAGR | **62.60%** | 58.80% | **54.88%** | 49.88% |
| Max drawdown (1m marks) | **40.94%** | 44.56% | 33.49% | 33.49% |
| Sharpe (annualized 1m) | 1.30 | 1.24 | 1.24 | 1.16 |
| Sortino | 1.83 | 1.74 | 1.77 | 1.64 |
| Volatility | 45.49% | 46.12% | 42.80% | 43.39% |
| Fills | 857 | 657 | 421 | 337 |
| Turnover (× start equity) | 26,784× | 17,331× | 1,881× | 1,295× |
| Time in TQQQ | 77.3% | 79.0% | 69.2% | 70.6% |
| Max-DD peak → trough | 2018-03-13 → 2019-06-05 | same | 2026-06-22 → 2026-07-30 | same |

Benchmark TQQQ: 39.28% / 81.68% (10y) and 13.47% / 81.68% (5y) on daily bars;
the harness's 1-minute benchmark for the same windows is 39.38% / 82.29% and
14.29% / 82.29%.

### 3.2 Cost sensitivity

| Variant | Costs | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---|---:|---:|---:|---:|
| winner (fixed 4%) | 1 bp | 58.80% | 44.56% | 49.88% | 33.49% |
| winner (fixed 4%) | 5 bp | 54.60% | 47.08% | 45.89% | 34.13% |
| winner (fixed 4%) | 10 bp | 49.50% | 50.06% | 41.05% | 34.93% |
| **ATR ×0.70 cap 4%** | **1 bp** | **62.60%** | **40.94%** | **54.88%** | **33.49%** |
| **ATR ×0.70 cap 4%** | **5 bp** | **57.01%** | **44.25%** | **49.75%** | **34.13%** |
| **ATR ×0.70 cap 4%** | **10 bp** | **50.29%** | **48.12%** | **43.57%** | **34.93%** |
| ATR ×0.55 cap 4% | 1 bp | 65.25% | 41.99% | 57.55% | 33.51% |
| ATR ×0.55 cap 4% | 5 bp | 58.79% | 45.49% | 51.35% | 34.46% |
| ATR ×0.55 cap 4% | 10 bp | 51.07% | 49.58% | 43.95% | 35.63% |
| ATR ×0.85 cap 4% | 1 bp | 59.00% | 44.91% | 48.22% | 33.49% |
| ATR ×0.85 cap 4% | 5 bp | 54.01% | 47.74% | 43.72% | 34.13% |
| ATR ×0.85 cap 4% | 10 bp | 48.00% | 51.08% | 38.29% | 34.93% |
| ATR ×0.70 cap 6% (uncapped) | 1 bp | 59.79% | 41.95% | 51.18% | 39.00% |
| ATR ×0.70 cap 6% (uncapped) | 5 bp | 54.68% | 42.41% | 46.35% | 39.58% |
| ATR ×0.70 cap 6% (uncapped) | 10 bp | 48.52% | 42.99% | 40.54% | 40.30% |
| fixed 4% → 50% QQQ | 1 bp | 56.97% | 43.19% | 47.65% | 33.36% |
| fixed 4% → 50% QQQ | 5 bp | 52.76% | 45.86% | 43.67% | 34.05% |
| fixed 4% → 50% QQQ | 10 bp | 47.66% | 49.01% | 38.85% | 34.90% |
| ATR ×0.70 → 50% QQQ | 1 bp | 60.15% | 42.73% | 51.78% | 33.36% |
| ATR ×0.70 → 50% QQQ | 5 bp | 54.58% | 43.54% | 46.70% | 34.05% |
| ATR ×0.70 → 50% QQQ | 10 bp | 47.89% | 47.59% | 40.59% | 34.90% |

Each extra basis point costs ~1.0–1.4 pp of CAGR because the ATR stop trades
more than the winner (857 vs 657 fills over 10y, ~5 extra round trips a year).
**It still beats the winner on both CAGR and DD at 5 bp and 10 bp in both
windows** (5y DD is a tie at every cost level). The margin at 10 bp is +0.8 pp
CAGR / −1.9 pp DD on 10y, so the edge is thin at retail costs but it survives.

### 3.3 Yearly returns (calendar year, 1 bp)

| Year | ATR stop | Winner | TQQQ |
|---|---:|---:|---:|
| 2017 | 100.44% | **118.76%** | 114.54% |
| 2018 | **9.69%** | 0.47% | −20.76% |
| 2019 | **51.47%** | 47.94% | 148.23% |
| 2020 | 183.91% | 183.91% | 104.14% |
| 2021 | **75.49%** | 60.61% | 81.05% |
| 2022 | **−16.87%** | −17.99% | −79.39% |
| 2023 | 147.04% | **149.04%** | 192.05% |
| 2024 | **77.75%** | 67.96% | 62.43% |
| 2025 | **57.29%** | 43.29% | 32.10% |
| 2026 | 13.10% | **16.76%** | 22.62% |

- 2020 is **identical** (183.91% both): the cap binds on 87% of armed 2020 days,
  both strategies record the same 14 stops, and the two equity paths coincide —
  the crash behaviour is unchanged.
- The big give-up is 2017 (−18.3 pp): a tight 2.5% stop in a calm melt-up
  whipsaws (16 stops vs 7). The strategy still ends 2017 at +100%.
- The payoff years are 2018 (+9.2 pp), 2021 (+14.9 pp), 2024 (+9.8 pp) and
  2025 (+14.0 pp) — mid-volatility, choppy years where a −3% TQQQ move from the
  open is a real break and the 4% stop was too slow.
- 2026 is slightly worse (−3.7 pp), consistent with the identical-but-not-better
  2026 drawdown.

5y-window stub years: 2021 ATR 32.44% vs winner 26.68%; 2026 13.10% vs 16.76%.

### 3.4 Rolling 3-year windows (quarterly starts, 756 trading days)

| Variant | Window | n | CAGR>TQQQ | DD<TQQQ | both>TQQQ | CAGR>winner | DD<winner | both>winner | median CAGR edge | median DD edge |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ATR ×0.55 | 10y | 28 | 25 | 28 | 25 | 28 | 25 | 25 | +8.59 pp | −1.13 pp |
| ATR ×0.55 | 5y | 8 | 8 | 8 | 8 | 8 | 7 | 7 | +7.13 pp | −1.13 pp |
| **ATR ×0.70** | **10y** | **28** | **24** | **28** | **24** | **28** | **26** | **26** | **+5.06 pp** | **−0.95 pp** |
| **ATR ×0.70** | **5y** | **8** | **8** | **8** | **8** | **8** | **8** | **8** | **+5.86 pp** | **−0.95 pp** |
| ATR ×0.85 | 10y | 28 | 23 | 28 | 23 | 22 | 6 | 6 | +3.07 pp | 0.00 pp |
| ATR ×0.70 cap 6% | 10y | 28 | 22 | 28 | 22 | 13 | 9 | 6 | −0.99 pp | +1.78 pp |
| fixed 4% → 50% QQQ | 10y | 28 | 22 | 28 | 22 | 1 | 10 | 1 | −2.63 pp | +0.24 pp |
| ATR ×0.70 → 50% QQQ | 10y | 28 | 24 | 28 | 24 | 24 | 18 | 15 | +1.47 pp | −0.40 pp |

The headline has a higher 3-year CAGR than the winner in **all 28** windows and
a lower drawdown in **26 of 28**; the two exceptions are the 2017 windows
(where the tight stop whipsawed). The worst 3-year window is 2017-04→2020-03 at
29.92% CAGR / 38.83% DD vs the winner's 28.89% / 41.62% — still ahead. It beats
TQQQ on both in 24/28.

### 3.5 Sub-periods (compounded calendar returns, 1 bp)

| Period | ATR stop | Winner | TQQQ |
|---|---:|---:|---:|
| 2017–2019 | 233.02% | 225.14% | 321.98% |
| 2020–2022 | 314.17% | 273.97% | −23.82% |
| 2023–2026 | 681.14% | 599.82% | 668.41% |

### 3.6 Pass/fail against the README criteria

| Criterion | 10y | 5y |
|---|---|---|
| Beats TQQQ on CAGR and DD | ✅ (+23.3 pp / −40.7 pp) | ✅ (+41.4 pp / −48.2 pp) |
| Criterion 1: higher CAGR **and** lower DD than winner | ✅ | ❌ CAGR higher, **DD tie** |
| Criterion 2: lower DD, CAGR within 2 pp | ✅ | ❌ DD tie, CAGR +5.0 pp |
| Criterion 3: better rolling 3-year consistency | ✅ 26/28 windows beat the winner on both | ✅ 8/8 |
| Passes at 5 bp | ✅ 57.01% / 44.25% | ✅ 49.75% / 34.13% |
| Passes at 10 bp | ✅ 50.29% / 48.12% | ✅ 43.57% / 34.93% |

By the letter of the README, the 5-year DD tie means neither criterion 1 nor 2
is literally satisfied. I report it as "dominance with a drawdown tie" rather
than pretending the tie is an improvement. Criterion 3 is satisfied
unambiguously.

---

## 4. Why it works

### 4.1 The stop distance is a regime map

Effective stop distance on armed risk-on days, by year (median / share at the
2.5% floor / share at the 4% cap):

| Year | Median | At floor | At cap |
|---|---:|---:|---:|
| 2017 | 2.50% | 83% | 0% |
| 2018 | 2.97% | 24% | 33% |
| 2019 | 3.53% | 27% | 41% |
| 2020 | 4.00% | 5% | 87% |
| 2021 | 3.62% | 18% | 39% |
| 2022 | 3.82% | 0% | 22% |
| 2023 | 3.37% | 5% | 18% |
| 2024 | 3.05% | 20% | 20% |
| 2025 | 3.19% | 18% | 20% |
| 2026 | 3.64% | 21% | 37% |

(Armed days are, by construction, the weak-short-term-trend days, so the
conditional distances are wider than the unconditional ATR would suggest. Over
2017–2026 the armed-day median is **3.23%**, with 26% of armed days at the 2.5%
floor and 30% at the 4% cap; the unconditional median is 2.96%.)

### 4.2 The 2024-08-02 case: why the cap matters

This is the cleanest natural experiment in the sample.

| Day | ATR14 | 0.70×ATR | Capped | TQQQ open | Intraday low | Close | Next open |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-08-01 | 6.40% | 4.48% | 4.00% | 33.59 | 30.22 (−10.0%) | 31.02 (−7.7%) | 29.21 |
| 2024-08-02 | 7.45% | 5.21% | 4.00% | 29.21 | 27.92 (−4.4%) | 28.77 (−1.5%) | **24.16 (−16.0%)** |

- **Capped (4.00%)**: triggers on 2024-08-02 at 10:12 at ≈28.0, is out overnight,
  and avoids the −16.0% gap to 24.16.
- **Uncapped (5.21%)**: needs 27.69; the day's low is 27.92, so it never fires and
  eats the whole gap.
- This single event is why the uncapped variant's 5y max drawdown is 39.00%
  (2024-07-10 → 2024-08-05) while the capped version's is 33.49% (2026-06-22 →
  2026-07-30, the same episode as the winner).

The economic point: the ATR filter is a *volatility regime* filter, and the
regime that produces the widest ATR is the regime in which the gap risk lives.
Using it to widen the stop is backwards for a tail hedge.

### 4.3 Where the extra return comes from

The capped stop fires 204 times in the 2017–2026 test window vs 153 for the
fixed 4% — about 5 extra stops a year (216 vs 160 including the 2016 warm-up),
concentrated in calm/trending years: 2017 (16 vs 7), 2019 (18 vs 11), 2021
(32 vs 23), 2023 (21 vs 15), 2024 (25 vs 19), 2025 (22 vs 16). In 2020 and 2022
— the crash years — the two stop counts are identical (14 vs 14, 4 vs 4),
because the cap binds on the high-volatility days when those stops occur.

So the ATR stop is not a better crash hedge; it is the *same* crash hedge plus
a second, calmer signal. In ATR units the winner's fixed 4% is ≈1.1 ATR on
armed 2017 days (ATR ≈3.6%) but only ≈0.7 ATR in 2020 and 2022 (ATR 5.5–6%+).
So the fixed stop is *too slow* exactly where calm-market breaks happen, and
about right in crises. The ATR scale holds the stop at a constant ≈0.7 ATR below
the open in every regime; in low-volatility uptrends a −2.5% to −3.5% TQQQ move
is then a genuine 0.7-ATR break rather than noise, and exiting those days avoids
a slow bleed that the 4% stop sleeps through. The per-event saving is similar
(mean exit→next-open move −0.46% for the capped ATR stop vs −0.48% for the fixed
4%; median −0.32% vs −0.39%), but there are 33% more events. 2020's identical
yearly return (183.91% both) is the cleanest proof that the crash behaviour is
unchanged.

### 4.4 The 2026 identity

On the 2026-06-09 … 2026-07-31 slide that sets the 5y max drawdown, both
strategies stop on exactly the same eight sessions and at exactly 4.00%:

```
2026-06-09 10:44, 2026-06-24 15:01, 2026-06-25 09:46, 2026-07-02 11:06,
2026-07-15 10:42, 2026-07-27 10:23, 2026-07-29 10:40, 2026-07-31 10:07
```

That is the mechanical reason the 5y max drawdown is identical: the cap restores
the round-1 behaviour precisely in the episode that sets it.

---

## 5. Parameter surface (robustness)

All rows: same regime, same arm gate, same fills, 1 bp, all-BIL exit.

| Stop | 10y CAGR | 10y DD | 5y CAGR | 5y DD | Stops | Fills |
|---|---:|---:|---:|---:|---:|---:|
| fixed 2.50% (control) | 53.75% | 43.02% | 44.60% | 43.02% | 300 | 1,169 |
| fixed 2.75% (control) | 53.09% | 45.14% | 44.11% | 35.22% | 273 | — |
| fixed 3.00% (control) | 54.05% | 48.43% | 44.36% | 37.66% | 246 | 973 |
| fixed 3.50% (control) | 59.89% | 46.41% | 50.59% | 30.45% | 197 | 793 |
| **fixed 4.00% (winner)** | **58.80%** | **44.56%** | **49.88%** | **33.49%** | 160 | 657 |
| ATR ×0.45, cap 4% | 63.80% | 45.34% | 55.60% | 33.26% | 275 | 1,069 |
| ATR ×0.55, cap 4% | 65.25% | 41.99% | 57.55% | 33.51% | 250 | 977 |
| ATR ×0.65, cap 4% | 62.48% | 39.66% | 53.95% | 33.49% | 226 | 897 |
| **ATR ×0.70, cap 4%** | **62.60%** | **40.94%** | **54.88%** | **33.49%** | 216 | 857 |
| ATR ×0.75, cap 4% | 60.50% | 42.41% | 52.74% | 33.49% | 208 | 825 |
| ATR ×0.85, cap 4% | 59.00% | 44.91% | 48.22% | 33.49% | 195 | 781 |
| ATR ×0.95, cap 4% | 59.03% | 42.73% | 48.70% | 33.49% | 183 | 737 |
| ATR ×0.70, floor 1.5% | 64.21% | 40.15% | 53.65% | 33.49% | 225 | 885 |
| ATR ×0.70, floor 3.0% | 61.19% | 45.50% | 53.18% | 33.49% | 198 | 801 |
| ATR ×0.70, cap 6% (uncapped) | 59.79% | 41.95% | 51.18% | 39.00% | 199 | 797 |
| ATR30 ×0.70–1.00 | 51.3–66.2% | 40.2–43.1% | — | — | 144–214 | 593–849 |
| intraday range14 ×0.70 | 63.35% | 40.48% | 55.34% | 34.16% | 235 | 929 |
| Wilder ATR14 ×0.70 | 61.91% | 40.26% | 52.92% | 33.49% | 221 | 877 |
| ATR20 ×0.70 | 60.46% | 41.88% | 51.76% | 33.49% | 223 | 885 |
| ATR10 ×0.70 | 61.69% | 40.87% | 50.78% | 33.49% | 214 | 853 |
| ATR5m ×6, cap 4% | 64.68% | 46.29% | 60.68% | 30.95% | 259 | 1,021 |
| ATR5m ×7, cap 4% | 63.83% | 44.39% | 54.56% | 32.41% | 239 | 941 |
| ATR5m ×8, cap 4% | 63.53% | 39.68% | 51.42% | 31.60% | 226 | 893 |
| vol20 ×1.20, clip 3–6% | 56.88% | 43.30% | 47.04% | 41.69% | 158 | 645 |
| ATR5m ×3 literal (negative) | 49.42% | 43.58% | — | — | 502 | 1,889 |

Reading the surface:

- **k ∈ [0.55, 0.75] is the passing plateau** on both windows: 10y CAGR
  60.5–65.3% with DD 39.7–42.4%, 5y CAGR 52.7–57.6% with DD 33.49–33.51%.
  k = 0.70 is the centre, not the peak (the peak is 0.55, and 0.45 already
  breaks the 10y DD at 45.34%). k = 0.85 is a wash on 10y DD (44.91% vs
  44.56%) and k = 0.95 recovers to 42.73% — the wide end is noisy, another
  reason not to read the exact k as an optimum.
- **The cap is what makes the 5y robust.** Every capped row lands at 33.49% on
  the 5y DD regardless of k; the uncapped row jumps to 39.00%. Without the cap
  the design is a 10y improvement that gives back the 5y protection.
- **The floor matters in the other direction**: floor 1.5% is slightly better
  (64.21% / 40.15%), floor 3.0% breaks the 10y DD (45.50%). 2.5% is a deliberate
  middle.
- **A fixed tighter stop cannot clear both windows.** Fixed 2.50% gives 53.75% /
  43.02% (10y) and 44.60% / 43.02% (5y); fixed 3.50% is the best fixed level on
  the 5y (50.59% / 30.45%) but fails the 10y DD (46.41%); the winner's fixed 4%
  passes the 5y and is mediocre on 10y. **No fixed level passes both windows
  simultaneously — the ATR scale does.** That is the cleanest evidence that the
  gain is the *conditional* distance (tight in calm, wide-but-capped in stress),
  not simply a tighter level.
- **Estimator choice is secondary.** Holding the 0.70 multiplier and the 4% cap
  fixed, daily ATR10/14/20, Wilder ATR14, and the 14-day intraday high-low range
  all land within 60.5–63.4% CAGR / 40.3–41.9% DD on 10y and 50.8–55.3% /
  33.5–34.2% on 5y (`robust.json`). That is expected: a daily range is ≈8.8× a
  5-minute range, so 7–8× on 5m ATR and 0.8× on daily ATR are nearly the same
  distance. The 5m family is noisier at the tight end (×6 gives 10y DD 46.29%,
  ×8 gives 39.68%), which is the same k-sensitivity seen above, not a different
  estimator failing.
- **3–6% volatility scaling does not work here** (vol20 ×1.2: 5y DD 41.69%),
  for the same reason as the uncapped ATR: it widens in 2026/2022 instead of
  tightening.

---

## 6. What did NOT work

### 6.1 Partial de-risking to QQQ

Replacing the all-BIL exit with 50% QQQ / 50% BIL after the stop (held for the
rest of the day and overnight, re-entering TQQQ next session):

| Variant | 10y CAGR | 10y DD | 5y CAGR | 5y DD | Fills |
|---|---:|---:|---:|---:|---:|
| fixed 4% → 100% BIL (winner) | 58.80% | 44.56% | 49.88% | 33.49% | 657 |
| fixed 4% → 50% QQQ | 56.97% | 43.19% | 47.65% | 33.36% | 972 |
| ATR ×0.70 cap 4% → 100% BIL | **62.60%** | **40.94%** | **54.88%** | 33.49% | 857 |
| ATR ×0.70 cap 4% → 50% QQQ | 60.15% | 42.73% | 51.78% | 33.36% | 1,275 |

Partial de-risking is dominated in every comparison that matters:

- With the fixed 4% stop it buys 1.4 pp of 10y DD for 1.8 pp of CAGR; on the 5y
  it buys 0.13 pp of DD for 2.2 pp of CAGR. That is a bad trade and it misses
  the "within 2 pp" bar on the 5y window by 0.23 pp.
- With the ATR stop it is worse on *both* 10y metrics (60.15% / 42.73% vs
  62.60% / 40.94%): keeping half the position in QQQ after the stop both lowers
  the return and raises the drawdown, because QQQ keeps falling through the
  crash the stop is designed to sidestep. On the 5y it gains 0.13 pp of DD for
  3.1 pp of CAGR.
- The ATR + 50% QQQ combination does still beat the winner on both windows
  (60.15% / 42.73% vs 58.80% / 44.56%, and 51.78% / 33.36% vs 49.88% / 33.49%)
  — the stop improvement is big enough to pay for the worse exit. But it is
  strictly dominated by the same stop with a full BIL exit, so there is no
  reason to prefer it.
- Other partial flavours are worse still: 100% QQQ after the stop (55.02% /
  46.22% 10y), 50% TQQQ / 50% BIL (53.34% / 49.20%), 50% QQQ only intraday and
  BIL overnight (56.89% / 44.49%), and a two-stage 50%-at-4%/BIL-at-8% ladder
  (57.09% / 42.62%). Full exit beats every partial exit.

This is consistent with the trend-following literature on partial exits: a
half-exit is the average of "stay in" and "get out", so it cannot beat the
better of the two, and in a crash the better of the two is "get out"
([Enlightened Stock Trading](https://enlightenedstocktrading.substack.com/p/is-taking-partial-profits-in-trend),
[tradejournal.ai](https://tradejournal.ai/blog/scaling-out-partial-profits)).
The stop's value is a small number of gap nights; halving the exit halves the
only thing it does well.

### 6.2 Uncapped volatility scaling

Covered above: ATR ×0.70 with a 6% cap gives 59.79% / 41.95% (10y) but 51.18% /
39.00% (5y). The extra 5y drawdown is the 2024-08-05 gap. Any design that
*widens* the stop when ATR rises will eventually miss the gap it exists to
avoid.

### 6.3 Literal 2–3× ATR on 1m/5m bars

`3 × ATR5m(14) ≈ 1.0%` produces 502 stop events and 1,889 fills over the sample,
with 49.42% CAGR and 43.58% DD — it is a noise detector that pays 10 bp of
turnover for the privilege. `2 × ATR1m` would be ~0.31% and is not a strategy.
A "2×ATR" rule is only meaningful once the bar size and the reference point are
specified; the economically sensible version of it for a session-open stop is
0.6–0.9 × *daily* ATR, which is what the headline uses.

### 6.4 Fixed tighter stops

A fixed 2.5% stop (the ATR stop's median) gives 53.75% / 43.02% (10y) and
44.60% / 43.02% (5y); a fixed 3.5% stop gives 59.89% / 46.41% (10y) and 50.59% /
30.45% (5y). Each fixed level wins one window and loses the other — 3.5% looks
excellent on 5y and fails the 10y drawdown, 2.5% the reverse. Tightening alone
is not the edge; conditioning the distance on volatility is what clears both
windows at once.

---

## 7. Limitations

1. **The 5y "win" is a CAGR win, not a drawdown win.** The 5y max drawdown is
   unchanged at 33.49% because the 2026 episode is identical by construction.
   The drawdown improvement is a 10-year-window result (−3.6 pp).
2. **The 10y DD improvement is not uniform across parameters.** k = 0.45 and
   floor = 3.0% give 45.3–45.5%, slightly worse than the winner's 44.56%. The
   passing region is k ∈ [0.55, 0.75] with floor 2.5% — wide, but not universal.
3. **The 4% cap is inherited from the round-1 winner, which was itself selected
   in-sample.** That is deliberate (it is the validated crisis stop, and it is
   what makes the 2026 result identical), but it means the cap is not an
   out-of-sample discovery.
4. **Turnover is ~30% higher** (857 vs 657 fills over 10y; 26,784× vs 17,331×
   notional). Each basis point of slippage costs the ATR version ~1.4 pp of CAGR
   vs ~1.0 pp for the winner, so at 10 bp the edge is down to +0.8 pp CAGR /
   −1.9 pp DD on 10y. It survives, but it is thin.
5. **It can lag badly in calm melt-ups.** 2017 is −18.3 pp behind the winner
   (+100.4% vs +118.8%) because the 2.5% stop whipsaws in a low-vol grind. The
   full-period result depends on the choppy years (2018, 2021, 2024, 2025)
   showing up often enough.
6. **Crash concentration.** As with the winner, the improvement is concentrated
   in a few episodes (2018-02-05, 2020-03, 2024-08-02). The mean per-event
   saving is small (−0.46%) and 55% of events are "unnecessary" ex post; the
   value is in the left tail.
7. **One instrument, one sample.** TQQQ, 2017–2026, two large crashes. The
   2024-08-02 example is a single day; the cap is a structural argument, not a
   statistically estimated optimum.
8. **No taxes, no borrow, no market impact.** ~70 fills a year is
   tax-inefficient in a taxable account; 1 bp is optimistic for a stop that can
   fill through the trigger.
9. **BIL carry** is included via BIL's price; no separate cash yield is added.

---
## 8. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents2\vol-scaled-crash-stop\strategy.py
```

`strategy.py` rebuilds the 1-minute panel from `data/intraday-hf` (cached to
`panel_cache.npz` on first run), computes the daily ATR from the same adjusted
prices, applies the rules above, and writes `result.json` with 1/5/10 bp
metrics, yearly returns, rolling 3-year windows and pass/fail flags for seven
variants. The exploratory scripts in this folder document every number quoted
above: `sweep1.py`/`sweep2.py`/`sweep3.py` (distance surface), `cap.py`/`cap2.py`
(cap and partial de-risking surface), `plateau.py`, `robust.py` (estimator
robustness), `atr5m.py`, `fixed5y.py`, `diag.py`/`events_final.py` (stop-event
anatomy), `facts.py`, `aug2024.py`, `why5y.py`, `report_numbers.py`. No core
repository file was modified.

## References

- Kaminski, K. M., & Lo, A. W. (2014). *When do stop-loss rules stop losses?*
  Journal of Financial Markets 18, 234–254.
  [SSRN 968338](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=968338)
- Moreira, A., & Muir, T. (2017). *Volatility-Managed Portfolios.* Journal of
  Finance 72(4). [SSRN 2659431](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431)
- Alvarez, C. *Stop loss types tested: which work best for systematic traders.*
  [Better System Trader #037](https://bettersystemtrader.com/037-cesar-alvarez-studies-stop-losses)
- *Stop-Loss Distance vs Hit Rate: 20,000-Trade Study.*
  [FXNX](https://fxnx.com/en/blog/stop-loss-distance-vs-hit-rate-20-000-trade-study)
- *Volatility-Adjusted Stop Losses: ATR, Chandelier, and Keltner Methods.*
  [Volatility Box](https://volatilitybox.com/research/volatility-adjusted-stop-losses)
- *Chandelier Exit strategy backtest.*
  [Quant Arenas](https://quantarenas.com/strategy/trend-17-chandelier-exit)
- *Volatility Clustering: What It Is and How to Trade It.*
  [Arrow Algo](https://arrowalgo.com/volatility-clustering)
- *Is Taking Partial Profits in Trend Following a Rational Idea?*
  [Enlightened Stock Trading](https://enlightenedstocktrading.substack.com/p/is-taking-partial-profits-in-trend)
- *Scaling Out of Trades: Does Taking Partial Profits Help or Hurt?*
  [TradeJournal](https://tradejournal.ai/blog/scaling-out-partial-profits)
- FinLab. *Leveraged ETF decay in 14 funds, 2016–2026.*
  [link](https://finlab.finance/en/blog/leveraged-etf-decay)
