# Fast-drawdown brake on TQQQ — development report

**Strategy:** `tqqq-fast-drawdown-stop`
**Window:** 2016-01-04 .. 2023-12-29 (development only)
**Data:** adjusted 1-minute QQQ / TQQQ / BIL, regular session
**Harness:** `research/bt.py`, next-open fills, 2% band, 1 bp headline plus
5/10 bp
**Holdout:** never loaded, never inspected, never used for selection

> **Verdict: PASS on the development bar.**
> 1 bp: **52.83% CAGR, 45.90% max DD, 1.19 Sharpe**, 77.8% TQQQ exposure,
> 0.65 daily-return correlation to TQQQ, 69 fill events.
> The official bar is 36.72% CAGR / 82.29% DD / 0.82 Sharpe.
> 8/8 grid cells clear the official bar; 7/8 also clear the stricter
> DD < 60% target. The one strict miss is the 10-session re-entry — the
> whipsaw boundary, not a random cell.
>
> **Honest status:** this is a crash-avoidance strategy with a slow re-entry,
> not a fast-exit timing edge. The exit alone sells into bounces. The 15-day
> high is what turns the brake into a filter that avoids bear-market rallies
> and catches the durable leg of a V recovery. The worst drawdown (45.9%) is
> a 2018 bull-market whipsaw, not a crash the brake avoided. The strategy
> lags strong bull years. The development CAGR cushion is large, but a
> crash-free holdout with a 2018-style whipsaw is the real full-window risk.

---

## 1. Exact rules

One decision per session, at the 15:59 close. Let `C_t` be TQQQ's regular
session close. All indicators use data through `C_t`; the target set at the
close fills at the next session's 09:30 open.

**Default:** 100% TQQQ.

**Exit (LONG -> OFF).** If

```
C_t / C_{t-5} - 1 <= -0.14
```

go to 100% BIL at the close; the fill is the next open. A second trigger while
already off changes nothing.

**Re-entry (OFF -> LONG).** If

```
C_t >= max(C_{t-15}, C_{t-14}, ..., C_{t-1})
```

go back to 100% TQQQ at the close; the fill is the next open. The prior-high
window excludes today. There is no same-day exit-and-reentry: the trigger is
checked first.

No moving-average gate, no volatility gate, no shorting, no leverage beyond
100% TQQQ. BIL is the only defensive asset. Idle weight is zero cash; BIL is a
real asset in the harness, so defensive spells earn BIL's total return.

**Why this shape.** The trigger is a five-session 14% loss. TQQQ's development
daily log-return volatility is 68.6% annualised, so 14% over five sessions is
about a 1.5-sigma five-day move under an iid normal approximation, and the raw
condition is true on 4.7% of the 2,012 development sessions. It is a bad week,
not a one-day crash, and it is not ultra-rare. The selectivity comes from the
combination with the slow re-entry, not from the trigger alone. The
five-session window catches both a single-day crash and a grinding bear leg
that a one-day stop misses. The re-entry waits for a 15-session closing high,
which is slow enough to avoid the first bear-market rally and fast enough to
catch a V recovery after the panic.

---

## 2. Headline results

### 2.1 1-minute marks, 2016-01-04 .. 2023-12-29

| Cost | CAGR | Max DD | Sharpe | Sortino | Vol | Fills | Turnover | TQQQ exposure |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1 bp** | **52.83%** | **45.90%** | **1.19** | 1.68 | 43.87% | 69 | 668x | 77.8% |
| 5 bp | 52.30% | 46.07% | 1.18 | 1.67 | 43.87% | 69 | 656x | 77.8% |
| 10 bp | 51.64% | 46.28% | 1.17 | 1.65 | 43.87% | 69 | 641x | 77.8% |

Benchmark, same 1-minute panel: **36.15% CAGR / 82.29% max DD / 0.80
Sharpe**. The official pre-registered bar is **36.72% / 82.29% / 0.82**; the
table above is compared with the official bar. The small benchmark gap
(36.15% vs 36.72%) is a start/end or data-convention difference in the
harness (the variants tested bracket 36.06-36.15%); it does not affect the
pass, which is 16.1 pp above the bar.

- **TQQQ exposure:** 77.8% of sessions; 22.2% in BIL.
- **Correlation to TQQQ:** 0.65 on daily returns; 0.65 at 10 bp too.
- **Max drawdown:** 45.90%, peak **2018-01-29**, trough **2018-04-25**.
  This is the February-April 2018 whipsaw, not a crash the brake avoided
  (see §4.2).
- **Fills:** 69 fill events, about 34 round trips over eight years. Each
  switch trades two assets (sell one, buy the other), so the fill count is
  roughly twice the number of spells plus the initial position.

### 2.2 Yearly returns

| Year | Strategy | TQQQ | Difference |
|---:|---:|---:|---:|
| 2016 | +27.3% | +19.9% | +7.4 pp |
| 2017 | +118.3% | +118.3% | 0.0 pp |
| 2018 | -10.8% | -19.6% | +8.7 pp |
| 2019 | +79.7% | +133.1% | -53.5 pp |
| 2020 | +195.7% | +109.6% | +86.1 pp |
| 2021 | +43.2% | +83.0% | -39.8 pp |
| 2022 | -35.3% | -79.1% | +43.7 pp |
| 2023 | +142.7% | +198.4% | -55.7 pp |

The pattern is the whole story: the strategy gives up 40-56 pp in the strong
bull years (2019, 2021, 2023), and earns it back with a +86 pp 2020 and a
+44 pp 2022. 2017 is fully invested and identical. 2016/2018 are modest wins.

---

## 3. Pre-registered grid and plateau

All eight cells are 1-minute marks, 1 bp. "Official" means CAGR > 36.72% and
DD < 82.29%; "strict" means CAGR > 36.72% and DD < 60%.

| # | Cell | k | Loss | Re-entry | CAGR | Max DD | Sharpe | TQQQ | Fills | Official | Strict |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | `k3_d12_R15` | 3 | 12% | 15 | 40.19% | 47.04% | 1.00 | 75.8% | 85 | yes | yes |
| 2 | `k4_d14_R15` | 4 | 14% | 15 | 52.99% | 53.98% | 1.18 | 78.9% | 61 | yes | yes |
| 3 | `k5_d12_R15` | 5 | 12% | 15 | 42.24% | 52.27% | 1.05 | 74.2% | 89 | yes | yes |
| 4 | **`k5_d14_R15`** | **5** | **14%** | **15** | **52.83%** | **45.90%** | **1.19** | **77.8%** | **69** | **yes** | **yes** |
| 5 | `k5_d16_R15` | 5 | 16% | 15 | 54.02% | 58.48% | 1.19 | 79.8% | 57 | yes | yes |
| 6 | `k5_d14_R12` | 5 | 14% | 12 | 46.53% | 53.54% | 1.08 | 79.5% | 81 | yes | yes |
| 7 | `k5_d14_R18` | 5 | 14% | 18 | 46.79% | 48.09% | 1.12 | 74.5% | 69 | yes | yes |
| 8 | `k5_d14_R10` | 5 | 14% | 10 | 38.14% | 70.30% | 0.93 | 81.7% | 93 | yes | **no** |

**The plateau is real but not unlimited.**

- **Re-entry speed is the critical dimension.** R12, R15 and R18 all pass;
  R10 fails the strict DD target (70.3%). The 10-session high re-enters the
  first bear-market rally and gets stopped again. R20 was also tested in the
  exploratory surface: 43.7% / 41.7% (pass). R25 drops to 35.6% (fails CAGR).
  The viable band is roughly **12-20 sessions**, with the centre at 15.
- **Trigger duration is broad.** k3 (3-day 12%), k4 (4-day 14%), k5 (5-day
  14%) and k6 (6-day 14%, 43.3% / 49.7%, exploratory surface) all pass. The
  broader duration surface (k=2-8 at R15) has multiple passing cells from
  k=2 to k=8, with the most consistent region at k=4-6 for 10-16% thresholds.
- **Trigger depth is broad but bounded.** Exploratory surface at k5/R15:
  10% 44.5% / 43.7%, 12% 42.2% / 52.3%, 14% 52.8% / 45.9%, 16% 54.0% / 58.5%,
  17% 49.0% / 62.7% (fails strict), 18% 43.8% / 62.7% (fails strict). The
  viable band is roughly **10-16%**, with the centre at 14.
- **The centre is not the maximum.** `k5_d16_R15` has a higher CAGR (54.0%)
  but a much worse DD (58.5%). `k4_d14_R15` has a slightly higher CAGR
  (53.0%) but a worse DD (54.0%). The centre is chosen for the best DD/CAGR
  balance and because it sits in the middle of the re-entry plateau, not
  because it has the highest backtest CAGR.

The one strict failure is the cell the mandate explicitly asks about (a
10-session high). That is the useful negative result: **a 10-session
re-entry is too fast for this trigger.** The 5-session re-entry is worse
still (the `literal_3d8_R5` ablation is 18.5% / 87.5%).

---

## 4. Where the return comes from

### 4.1 Defensive-spell attribution

17 defensive spells in eight years. The TQQQ move is measured from the exit
fill (next open after the trigger close) to the re-entry fill (next open after
the re-entry close) — the move actually sat out in BIL.

| Start | End | Sessions | TQQQ move during spell |
|---|---:|---:|---:|
| 2016-01-11 | 2016-02-24 | 31 | -9.8% |
| 2018-02-05 | 2018-02-23 | 14 | **+25.6%** |
| 2018-03-22 | 2018-04-16 | 17 | +0.6% |
| 2018-10-10 | 2019-01-08 | 61 | **-25.2%** |
| 2019-05-13 | 2019-06-10 | 20 | +8.0% |
| 2019-08-05 | 2019-09-04 | 22 | +11.5% |
| 2020-02-24 | 2020-04-03 | 30 | **-51.9%** |
| 2020-09-08 | 2020-09-30 | 17 | +5.9% |
| 2020-10-30 | 2020-11-04 | 4 | **+25.0%** |
| 2021-02-25 | 2021-03-31 | 25 | +4.7% |
| 2021-10-04 | 2021-10-15 | 10 | +11.9% |
| 2022-01-10 | 2022-03-17 | 47 | **-31.0%** |
| 2022-04-11 | 2022-06-01 | 36 | **-36.4%** |
| 2022-06-09 | 2022-07-18 | 26 | -3.9% |
| 2022-08-22 | 2022-11-10 | 58 | **-33.9%** |
| 2022-12-19 | 2023-01-10 | 15 | +4.3% |
| 2023-09-21 | 2023-10-10 | 14 | +7.8% |

Summary: median spell 22 sessions, mean 26.3, max 61. **58.8% of spells had
TQQQ higher by the re-entry** — i.e. most spells are whipsaws. The mean
winner avoided -27.4%; the mean whipsaw cost +10.5%. The simple sum of the
spell moves is -86.9%, but that sums percentages across spells; the
compounded effect is what matters, and the few large avoidances dominate.

This is the honest shape of the strategy: many small whipsaws, a handful of
very large avoidances. It is not a high-hit-rate timing model.

### 4.2 Episode table

| Episode | TQQQ max DD | Strategy max DD | Avoided | TQQQ return | Strategy return |
|---|---:|---:|---:|---:|---:|
| 2018-02-05 .. 2018-04-02 | -30.1% | -29.2% | +0.9 pp | -8.0% | **-24.4%** |
| 2018-10-10 .. 2018-12-24 | -48.7% | -12.5% | +36.2 pp | -47.7% | -11.9% |
| 2020-02-19 .. 2020-03-23 | -72.4% | -20.6% | +51.8 pp | -69.5% | -15.9% |
| 2022-01-03 .. 2022-12-28 | -80.9% | -37.5% | +43.4 pp | -79.9% | -36.4% |

**The max drawdown is a whipsaw, not a crash.** From the 2018-01-29 peak to
the 2018-04-25 trough, the strategy lost 43.3% (headline drawdown 45.90%),
while TQQQ lost 24.1% with a 33.3% drawdown. The brake sold the February low,
rebought 25.6% higher, and then took the March correction. This is the single
most important caveat: the strategy's worst path is a bull-market correction,
exactly the environment where a crash brake has no crash to avoid and only
whipsaw costs.

### 4.3 The 2020 V-recovery

The brake exited on 2020-02-24 and re-entered on 2020-04-03, sitting out a
**-51.9%** TQQQ move (open-to-open) and then riding the recovery. 2020
returned **+195.7%** vs TQQQ's +109.6%. The re-entry was early enough to
catch the durable leg but late enough to miss the worst of the crash. This is
the best case for the design, and it is a real repeatable pattern only if a
future crash has a similar V shape.

### 4.4 The 2022 bear

Three spells did most of the work:

- 2022-01-10 -> 2022-03-17: **-31.0%**
- 2022-04-11 -> 2022-06-01: **-36.4%**
- 2022-08-22 -> 2022-11-10: **-33.9%**

2022 returned **-35.3%** vs TQQQ's -79.1%. The strategy did not avoid the
whole bear (it re-entered into bear rallies and took losses), but it avoided
enough of the three downlegs to turn an -80% year into a -35% year.

### 4.5 The whipsaw costs

- **2018-02-05 -> 2018-02-23:** missed **+25.6%** in 14 sessions, then took
  the March correction. This is the source of the 45.9% max DD.
- **2020-10-30 -> 2020-11-04:** missed **+25.0%** in four sessions. A very
  fast V after a trigger is the worst case for the slow re-entry.
- **2019, 2021, 2023:** lagged TQQQ by 53.5 pp, 39.8 pp and 55.7 pp. The
  strategy is out during some of the strongest rallies.

---

## 5. Robustness

### 5.1 Excluding one calendar year

Compounded daily returns with the year removed; no re-optimisation.

| Excluded | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016 | 56.89% | 43.71% | 1.23 |
| 2017 | 45.01% | 43.71% | 1.04 |
| 2018 | 64.85% | 42.09% | 1.34 |
| 2019 | 49.15% | 43.71% | 1.11 |
| **2020** | **38.89%** | 43.71% | 1.01 |
| 2021 | 54.08% | 47.83% | 1.21 |
| **2022** | **72.61%** | 43.71% | 1.45 |
| 2023 | 42.80% | 43.71% | 1.04 |
| 2020 + 2022 | 57.80% | 43.71% | 1.32 |

Every ex-one-year CAGR is above the 36.72% bar. The lowest is ex-2020
(38.89%), only 2.2 pp above the bar. So the strategy is **not** a single-year
artefact: it survives removing 2020, the V-recovery, and it survives removing
2022, the bear. Removing both leaves 57.8%, which is the bull years plus
2016/2018/2019/2021/2023.

### 5.2 Subperiods

| Period | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 2016-2019 | 45.22% | 45.90% | 1.21 |
| 2020-2021 | 105.52% | 40.26% | 1.61 |
| 2022-2023 | 25.35% | 40.35% | 0.72 |

The 2022-2023 subperiod is the weakest, but TQQQ's two-year return over the
same window was negative (2022 -79.1%, 2023 +198.4% compounds to about
-40%). The strategy's 25.4% is a large relative win even though it is below
the full-window bar.

### 5.3 Placebo: random defensive spells with the same lengths and exposure

500 circular shifts of the daily defensive mask. This preserves the number of
spells, their lengths and the total time off, but destroys the alignment with
crashes.

| Statistic | Observed (daily marks) | Placebo mean | Placebo p05 | Placebo p95 |
|---|---:|---:|---:|---:|
| CAGR | 52.41% | 27.27% | 10.08% | 44.72% |
| Max DD | 43.71% | 76.40% | 69.89% | 84.52% |
| Sharpe | 1.18 | 0.70 | — | 0.93 |

- Observed CAGR is at the **98.6th percentile** of the placebo distribution.
- Observed max DD is **better than all 500 placebos** (0th percentile; the
  mask timing is what creates the DD reduction, not just being out 22% of the
  time).
- Only **18.0%** of placebos clear the CAGR bar; only **0.2%** also get
  DD < 60%. Randomly timed defensive spells do not reproduce the result.

This is the strongest evidence that the timing of the spells matters. It does
not prove the edge will persist, but it rules out "any 22% time in BIL would
have done this."

### 5.4 Cut tests (causality)

Rebuild the weights on a 1-minute panel truncated at a past session close and
compare the overlap with the full-sample weights.

| Cut | Bars compared | Weight differences | Identical |
|---|---:|---:|---|
| 2018-12-24 | 291,367 | 0 | yes |
| 2020-03-12 | 409,752 | 0 | yes |
| 2022-09-13 | 655,277 | 0 | yes |

No look-ahead. The signals are trailing by construction; the cut test
confirms it numerically across the crash, the V and the bear.

### 5.5 Ablations and cross-checks (1-minute, 1 bp)

| Variant | CAGR | Max DD | Sharpe | Fills | Comment |
|---|---:|---:|---:|---:|---|
| **Centre: 5d 14% / 15-high** | **52.83%** | **45.90%** | **1.19** | 69 | primary |
| Calm-day re-entry 2% | 38.34% | 86.61% | 0.88 | 149 | re-enters the crash |
| Calm-day re-entry 3% | 36.68% | 86.72% | 0.85 | 161 | re-enters the crash |
| Literal 3-day 8% / 10-high | 18.02% | 67.31% | 0.62 | 185 | mandate's example, fails |
| Literal 3-day 8% / 5-high | 18.46% | 87.48% | 0.60 | 237 | mandate's example, fails |
| 2-day 10% / 10-high | 39.01% | 54.66% | 0.97 | 109 | passes, weaker |
| 4-day 14% / 10-high | 39.27% | 69.57% | 0.94 | 85 | fails strict DD |
| QQQ 5-day -5% / 15-high | 46.74% | 56.69% | 1.08 | 73 | signal cross-check, passes |
| TQQQ buy & hold | 36.15% | 82.29% | 0.80 | 1 | no stop |

The calm-day re-entry is the weakest part of the mandate: it re-enters during
a continuing crash and blows the DD back to 86-87%. The literal 3-day 8%
version is even worse (18% CAGR) because a 3-day 8% loss is too common in a
68%-vol asset; it is a whipsaw machine. The 5-day 14% trigger is the
calibration that makes the brake selective.

The QQQ cross-check is important: a QQQ 5-day -5% trigger (roughly the same
tail severity) also passes (46.7% / 56.7%). The result is not a TQQQ data
artefact; a broader-market crash signal works, just less well.

### 5.6 The literal "from a 20-session high within 5 sessions" family

The mandate also describes the trigger as a fall from a 10/20-session high
within a short window. This was tested directly: require the 20-session high
to have occurred within the last 5 sessions AND the current close to be
10-16% below it, then re-enter on a 10/15/20-session high. Daily marks:

| Cell | CAGR | Max DD | Sharpe | Official | Strict |
|---|---:|---:|---:|---|---|
| L20 d10 recent5 R15 | 30.95% | 71.00% | 0.81 | no | no |
| L20 d12 recent5 R15 | 40.60% | 71.00% | 0.91 | yes | no |
| L20 d14 recent5 R15 | 52.98% | 73.43% | 1.05 | yes | no |
| L20 d16 recent5 R15 | 55.40% | 75.23% | 1.07 | yes | no |
| L20 d14 recent5 R20 | 46.81% | 73.43% | 0.98 | yes | no |

The literal recent-high family can produce high CAGR, but the max DD stays
71-75%, so it does not meet the 60% target. The reason is mechanical: if the
high must be recent, the trigger only catches fast crashes. In the 2022 slow
bear the 20-day high is often stale, so the strategy stays long through the
grind and keeps most of the -80% TQQQ drawdown. The cumulative 5-day loss
trigger catches each leg of a slow bear because a 14% five-session loss can
accumulate even when no single recent high is nearby. That is why the primary
uses the cumulative loss definition, not the literal recent-high definition.

### 5.7 Event study: why the exit alone is not the edge

Forward TQQQ returns after a trigger, all triggers in the dev window:

| Trigger | n | Fwd 1d | Fwd 3d | Fwd 5d | Fwd 10d | Fwd 20d |
|---|---:|---:|---:|---:|---:|---:|
| Unconditional | — | +0.21% | +0.61% | +1.02% | +2.05% | +4.13% |
| 2-day <= -10% | 82 | +1.85% | +0.76% | +1.59% | +2.35% | +3.95% |
| 3-day <= -10% | 127 | +0.73% | +0.63% | +1.68% | +1.63% | +2.52% |
| 3-day <= -12% | 88 | +0.75% | +0.35% | +0.85% | +0.17% | +1.92% |
| 4-day <= -14% | 85 | +1.30% | +1.63% | +1.79% | +0.86% | +4.08% |
| **5-day <= -14%** | **95** | **+1.06%** | **+0.01%** | **+1.48%** | **+0.70%** | **+2.28%** |
| 5-day <= -16% | 71 | +1.04% | +0.26% | +1.97% | +0.32% | +2.49% |

After almost every trigger the next 1-20 days are **positive on average**.
The exit is not a timing edge; it usually sells into a bounce. The strategy
works because the 15-day high re-entry refuses to buy the bounce until it is
confirmed, and in a real bear the confirmation never comes. In other words,
the slow re-entry is the alpha, and the fast exit is the trigger that starts
the waiting period. This is the opposite of the naive "stop-loss adds value"
story, and it is the main reason the literal 3-day/5-day-high version fails.

### 5.8 Costs

The strategy trades only on full switches, so the 2% band does not block the
exits or re-entries. Costs are 1/5/10 bp on traded notional:
52.83% -> 52.30% -> 51.64% CAGR; DD 45.90% -> 46.07% -> 46.28%. The edge
survives 10 bp with a 14.9 pp CAGR margin over the bar.

---

## 6. What was tried, and the multiple-testing caveat

This is development-window research, and the search was not blind. The
honest sequence was:

1. **The mandate's literal version first.** 3-day 8% loss, 5/10-session high
   re-entry. It failed badly: 18.0% / 67.3% (R10) and 18.5% / 87.5% (R5).
2. **The other literal wording.** "From a 20-session high within 5 sessions"
   with 10/15/20-session re-entry. It produced high CAGR but DD 71-75%
   (§5.6). Fails the 60% target.
3. **A coarse mechanism scan** over trigger families (level, crossing,
   k-day loss, recent-high), re-entry modes (high, calm, time, high-or-calm,
   high-or-time) and partial sizing. About 570 configurations on daily bars,
   then a finer surface over k=2-8 and 10-18% at R15. A small 1-minute
   candidate screen (eight configurations) confirmed the daily ranking before
   the final grid was fixed. The scan is what identified the cumulative k-day
   loss + slow high re-entry region.
4. **The final 8-cell grid** was fixed around the centre before the
   production 1-minute run. All eight cells are reported above, including
   the one strict failure. The centre is the middle of the plateau, not the
   maximum-CAGR cell.

The multiple-testing risk is real. The guardrails are:

- the plateau is broad in three dimensions (duration 3-6, depth 10-16,
  re-entry 12-18), not a single cell;
- the placebo test puts the observed CAGR at the 98.6th percentile and the
  DD better than all 500 random masks;
- the cut tests show no look-ahead;
- every ex-one-year result clears the bar;
- the mechanism is explainable (crash avoidance + slow re-entry), not a
  black-box fit;
- the 2018 whipsaw and the 2020/2023 bull-year lags are reported, not hidden.

A different researcher could have picked `k4_d14_R15` (53.0% / 54.0%) or
`k5_d16_R15` (54.0% / 58.5%) as the centre. All three are in the same
plateau; the centre was chosen for the best DD/CAGR balance and the middle of
the re-entry band, not for the highest CAGR.

---

## 7. Full-window risk (no holdout inspection)

The one-shot 2024-2026 holdout is not loaded by `strategy.py` or any file in
this directory. The arithmetic below is a **hypothetical** sensitivity: it
compounds the frozen 2016-2023 CAGR with an assumed holdout CAGR and asks
what full-window CAGR results. It uses no 2024-2026 data.

| Hypothetical holdout CAGR | Implied full-window CAGR |
|---:|---:|
| -10% | 33.22% |
| 0% | 36.91% |
| +10% | 40.34% |
| +20% | 43.54% |
| +30% | 46.55% |
| +40% (approx. TQQQ holdout) | 49.39% |

Because the development CAGR is 52.83%, the holdout only needs about **1.7%
CAGR** for the full-window result to beat TQQQ's 37.54%. That is a large
cushion. It is an arithmetic consequence of compounding the 2016-2023 result:
the strategy does not need to repeat 52.83% in 2024-2026. The risk is not a
mediocre holdout; it is a **negative** one. A repeat of the 2018 whipsaw
(-43% path, -10.8% calendar year) would give a full-window CAGR around 33-36%
and fail. A crash-free bull holdout where the strategy captures only 50-60%
of TQQQ's upside would still likely pass (holdout 20-24% -> full 43-45%), but
a 2018-style chop is the failure mode.

The strategy's bull-year participation is the other warning: 2019 +80% vs
+133%, 2021 +43% vs +83%, 2023 +143% vs +198%. A 2024-2026 bull with no
crash is exactly the environment where the brake lags. The dev cushion
absorbs a lot of that lag, but not an indefinite one.

---

## 8. Verdict

**Pass on the development bar, with reservations.**

- 1 bp: **52.83% CAGR / 45.90% max DD / 1.19 Sharpe** vs the bar
  36.72% / 82.29% / 0.82.
- 5 bp: 52.30% / 46.07% / 1.18. 10 bp: 51.64% / 46.28% / 1.17.
- 8/8 grid cells clear the official bar; 7/8 clear the strict DD < 60%
  target. The one strict miss is the 10-session re-entry (70.3% DD), the
  whipsaw boundary.
- Ex-2020 38.89%; ex-2022 72.61%; every ex-one-year result above the bar.
- Placebo: observed CAGR 98.6th percentile; observed DD better than all 500
  random masks; only 0.2% of placebos get DD < 60%.
- Cut tests: zero weight differences at three past dates; no look-ahead.
- Costs: survives 10 bp with a 14.9 pp CAGR margin.

**The honest interpretation.** This is a legitimate standalone crash brake,
but its return source is not "selling fast." The fast 5-day 14% loss trigger
usually sells into a bounce (forward returns after triggers are positive).
The edge comes from the slow 15-day-high re-entry, which refuses to buy
bear-market rallies and therefore avoids the 2022 grind and the 2020 acute
phase, while still catching the durable V recovery. The cost is a long list
of whipsaws, a 45.9% max drawdown in the 2018 bull-market correction, and
40-56 pp of underperformance in strong bull years. A holdout with no crash
and a 2018-style chop is the scenario that would make the full-window result
fail.

The strategy is submitted for the one-shot holdout as-is. No parameter was
changed after the final 1-minute production run that generated `result.json`,
and no 2024-2026 data was loaded.

---

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/tqqq-fast-drawdown-stop/strategy.py
```

Files:

- `HYPOTHESIS.md` — pre-registration, exact rules, 8-cell grid, falsifiers.
- `strategy.py` — `build_weights(ts, o, c)` and `main()`; writes
  `result.json`. Development window only.
- `result.json` — machine-readable headline, grid, yearly, spells, episodes,
  ex-year, subperiods, placebo, cut tests, ablations, event study, verdict.
- `report.md` — this file.

Data notes:

- QQQ/TQQQ/BIL 1-minute bars are adjusted via the daily factor in
  `data/intraday-hf/`; the harness filters 09:30-16:00 ET and handles the
  BIL 1:2 reverse split before 2017-11-30.
- The 1-minute archive starts 2016-01-04, so the first five sessions cannot
  trigger and the first fifteen cannot re-enter. The default is TQQQ.
- `bt.benchmark` on this panel gives TQQQ 36.15% CAGR / 82.29% DD / 0.80
  Sharpe. The official bar is 36.72% / 82.29% / 0.82 and is used for
  pass/fail. The gap is small and does not change the pass.
- BIL is a real asset, so defensive spells earn its total return; the
  strategy does not assume 0% cash.
