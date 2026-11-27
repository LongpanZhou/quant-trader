# Event-risk overlay on the 165-day regime + 4% stop winner

**Agent:** `event-risk-overlay` (round 2, agent 14) · **Date:** 2026-11-25
**Question:** can de-risking around ex-ante macro/calendar events (FOMC, CPI, NFP,
monthly OpEx, pre-holiday) lower the winner's drawdown without giving up more than
2 pp of CAGR — or dominate it outright?

## Verdict

**Partial pass, and the interesting part is a clean negative for four of the five
event families.**

- FOMC, CPI, NFP and pre-holiday sessions are **not** days to be out of TQQQ: their
  *intraday* returns are −33, +25, +13 and +12 bp respectively (non-event: +5 to
  +9 bp). De-risking them costs return. CPI de-risking alone costs ~1.3%/yr.
- **Monthly option-expiry (third-Friday) sessions are different.** Their
  open→close TQQQ return is **−64 bp vs +9 bp on other sessions** (t = 2.77 on the
  TQQQ→QQQ intraday swap, 97 risk-on events, 59% hit rate). The effect is present in
  all three sub-periods and the OpEx set sits at the **99.3rd percentile** of 600
  random same-size session sets.
- Exploiting it by holding BIL for the OpEx *session* (keeping the overnight TQQQ
  leg) gives **67.06% / 40.65%** on the 10y window vs the winner's 58.80% / 44.56% —
  **strict dominance at 1, 5 and 10 bp** — and **53.83% / 35.88%** on the 5y window
  vs 49.88% / 33.49%: **+3.95 pp CAGR but +2.39 pp drawdown**, so it does *not* meet
  the "lower DD on both windows" target at 1-minute marks.
- Rolling 3-year consistency does improve materially: **27 of 28** rolling 3-year
  windows beat the winner on both CAGR and drawdown (winner mean 62.9% / worst DD
  41.6%; overlay 74.4% / 37.4%).

The honest summary: a real, economically interpretable OpEx-day flow effect, worth
~+4.6%/yr of log return, that converts into a large 10-year improvement and a
marginal 5-year one. The 5-year drawdown is 1.2 pp worse even measured from the
winner's own peak (34.69% vs 33.49%), so this is **not** a clean win on the stated
criterion.

## 1. Headline results

All numbers are the repo harness (`research/bt.py`): next-bar-open fills, 2%
rebalance band, slippage on traded notional, 1-minute equity marks, long-only.
Window 10y = 2017-01-03 → 2026-10-23, 5y = 2021-10-25 → 2026-10-23.

| Variant | Cost | 10y CAGR | 10y DD | 10y Sharpe | 5y CAGR | 5y DD | 5y Sharpe |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Winner (baseline)** | 1 bp | 58.80% | 44.56% | 1.24 | 49.88% | 33.49% | 1.16 |
| | 5 bp | 54.60% | 47.08% | 1.18 | 45.89% | 34.13% | 1.09 |
| | 10 bp | 49.50% | 50.06% | 1.11 | 41.05% | 34.93% | 1.01 |
| **V1 opex_flat_bil** | 1 bp | **67.06%** | **40.65%** | **1.36** | **53.83%** | 35.88% | **1.23** |
| | 5 bp | **60.50%** | **43.05%** | **1.27** | **48.16%** | 36.70% | **1.16** |
| | 10 bp | **52.67%** | **47.33%** | **1.16** | **41.37%** | 37.74% | **1.05** |
| V2 opex_qqq | 1 bp | 64.09% | 41.25% | 1.32 | 52.41% | 35.11% | 1.21 |
| | 5 bp | 57.44% | 44.85% | 1.23 | 46.53% | 35.93% | 1.14 |
| | 10 bp | 49.51% | 49.04% | 1.12 | 39.50% | 36.99% | 1.02 |
| V3 opex_half_bil | 1 bp | 63.00% | 42.01% | 1.30 | 51.97% | 34.68% | 1.20 |
| | 5 bp | 57.64% | 45.08% | 1.23 | 47.15% | 35.41% | 1.15 |
| | 10 bp | 51.18% | 48.69% | 1.14 | 41.33% | 36.34% | 1.04 |
| V4 opex_fomc_flat | 1 bp | **69.08%** | 43.15% | **1.40** | **54.84%** | 34.16% | **1.26** |
| | 5 bp | **60.96%** | 44.23% | **1.29** | 47.94% | 34.79% | 1.17 |
| | 10 bp | **51.37%** | **46.05%** | **1.15** | 39.75% | 35.57% | 1.02 |
| V5 all_events_qqq (control) | 1 bp | 60.14% | 41.61% | 1.31 | 51.99% | **32.09%** | 1.21 |
| | 5 bp | 46.94% | 47.50% | 1.11 | 40.26% | 32.90% | 1.01 |
| | 10 bp | 31.97% | 54.04% | 0.86 | 26.86% | 35.26% | 0.91 |

Daily-mark drawdown, 1 bp (comparable to the repo's published daily baseline):

| | 10y daily DD | 5y daily DD |
|---|---:|---:|
| Winner | 41.62% | 33.08% |
| V1 opex_flat_bil | 37.44% | 35.50% |
| V2 opex_qqq | 38.12% | 34.73% |
| V3 opex_half_bil | 38.92% | 34.30% |
| V4 opex_fomc_flat | 40.07% | **30.55%** |
| V5 all_events_qqq | 39.04% | **29.25%** |

Fill counts (10y): winner 657, V1 981 (+324 ≈ 33/yr), V4 1,205, V5 2,107.

### Pass / fail

| | vs TQQQ (CAGR & DD, both windows, 1/5/10 bp) | vs winner, 10y | vs winner, 5y | Target met? |
|---|---|---|---|---|
| **V1 opex_flat_bil** | ✅ all six | ✅ **strict dominance** at 1/5/10 bp (+8.26/+5.91/+3.17 pp CAGR, −3.92/−4.02/−2.73 pp DD) | ❌ CAGR +3.95/+2.27/+0.31 pp, DD **+2.39/+2.57/+2.80 pp** | **No** — 10y yes, 5y no |
| V2 opex_qqq | ✅ all six | ✅ strict dominance at 1/5/10 bp | ❌ DD +1.62/+1.81/+2.05 pp | No |
| V3 opex_half_bil | ✅ all six | ✅ strict dominance at 1/5/10 bp | ❌ DD +1.19/+1.28/+1.41 pp | No (CAGR within 2 pp at 5/10 bp but DD worse) |
| V4 opex_fomc_flat | ✅ all six | ✅ strict dominance at 1/5/10 bp | ⚠️ near-miss: DD **+0.64 to +0.67** pp, CAGR +4.95/+2.05/−1.31 pp | No (misses by 0.67 pp) |
| V5 all_events_qqq | ❌ fails 10y at 10 bp | ✅ at 1 bp only; ❌ at 5/10 bp | ✅ at 1 bp only; ❌ at 5 bp | No |

TQQQ buy-and-hold reference: 39.28% / 81.68% (10y), 13.47% / 81.68% (5y).

Only V5 meets "strict dominance on both windows", and only at 1 bp; it dies at 5 bp
because it churns 2,107 fills. That is a useful negative: **the naive "de-risk every
event day to QQQ" overlay is a cost illusion**.

## 2. Yearly returns (1 bp, 10y window)

| Year | Winner | V1 opex_bil | V2 opex_qqq | V3 opex_half | V4 opex+fomc | V5 all_events | TQQQ |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2017 | 118.8% | 116.5% | 116.7% | 117.7% | **128.5%** | 114.2% | 114.5% |
| 2018 | 0.5% | **12.1%** | 7.9% | 6.2% | **17.8%** | −1.5% | −20.8% |
| 2019 | 47.9% | **56.5%** | 53.5% | 52.2% | 58.8% | 41.7% | 148.2% |
| 2020 | 183.9% | **216.4%** | 204.6% | 200.1% | 202.6% | 188.5% | 104.1% |
| 2021 | 60.6% | **73.6%** | 69.0% | 67.1% | 59.4% | 61.2% | 81.1% |
| 2022 | −18.0% | −18.0% | −18.0% | −18.0% | −18.0% | −17.1% | −79.4% |
| 2023 | 149.0% | **180.0%** | 169.0% | 164.3% | 164.0% | 126.4% | 192.0% |
| 2024 | 68.0% | 75.6% | 72.9% | 72.0% | **87.0%** | 73.5% | 62.4% |
| 2025 | 43.3% | 48.0% | 46.3% | 45.8% | 48.0% | 49.0% | 32.1% |
| 2026 | 16.8% | 12.4% | 13.8% | 14.6% | **27.4%** | 37.0% | 22.6% |

V1 beats the winner in **7 of 10** calendar years (2022 is a tie because the regime
was off on every OpEx day that year); the two losses are 2017 (−2.3 pp) and 2026
(−4.4 pp).

5y-window yearly (2021 is Q4 only), V1 vs winner:
2021 23.4% vs 26.7%, 2022 −18.0% vs −18.0%, 2023 180.0% vs 149.0%, 2024 75.6% vs
68.0%, 2025 48.0% vs 43.3%, 2026 12.4% vs 16.8%.

## 3. Rolling 3-year windows (quarterly starts, 28 windows, daily marks)

| Strategy | mean CAGR | worst DD | windows beating winner on **both** |
|---|---:|---:|---:|
| Winner | 62.9% | 41.6% | — |
| **V1 opex_flat_bil** | **74.4%** | **37.4%** | **27 / 28** |
| V2 opex_qqq | 70.3% | 38.1% | 27 / 28 |
| V3 opex_half_bil | 68.7% | 38.9% | 27 / 28 |
| V4 opex_fomc_flat | 72.5% | 40.1% | 13 / 28 |
| V5 all_events_qqq | 61.9% | 39.0% | 5 / 28 |

Only one 3-year window loses to the winner on both counts (the 2026-window
starting 2023-10), and V1's worst 3-year drawdown is 4.2 pp shallower than the
winner's.

## 4. The event study (the actual finding)

Risk-on sessions only, 2017-01-03 → 2026-10-23, TQQQ returns in bp. `c2o` =
overnight (prior close → open), `o2c` = intraday (open → close). "swap" is the log
gain from holding QQQ instead of TQQQ for the intraday leg only.

| Event | n | TQQQ c2c | TQQQ c2o | TQQQ o2c | QQQ o2c | swap gain | t | hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FOMC (scheduled) | 65 | +37.6 | +70.0 | **−33.0** | −10.8 | +26.3 | 1.04 | 55% |
| CPI | 96 | +78.6 | +53.4 | +25.0 | +8.9 | −13.0 | −0.72 | 46% |
| NFP | 93 | +39.5 | +25.9 | +13.4 | +4.8 | −3.8 | −0.16 | 44% |
| **OpEx (3rd Friday)** | 97 | **−44.1** | +20.7 | **−64.1** | −21.4 | **+45.4** | **2.77** | **59%** |
| Pre-holiday | 73 | +58.3 | +47.2 | +11.6 | +4.1 | −5.5 | −0.33 | 44% |
| *non-event* | 1,942 | — | — | +5.5 to +9.2 | +3.4 | — | — | — |

Three things stand out:

1. **The overnight leg is uniformly strong.** Every event family has a positive
   close→open return. De-risking that leg would destroy the strategy — TQQQ's drift
   is overnight. Any event overlay must therefore be *intraday only*; this is why
   the "exit at the prior close" variants were discarded early.
2. **CPI days are strongly positive** (+78.6 bp close-to-close, +53.4 bp overnight).
   Avoiding them is the single most expensive thing you can do. De-risking CPI costs
   ~1.3%/yr of log return.
3. **OpEx day is negative and it is an intraday phenomenon.** The overnight into the
   third Friday is normal (+20.7 vs +17.9 bp); the session itself is −64 bp vs
   +9 bp. QQQ shows the same shape at 1/3 the size (−21.4 vs +3.4 bp), which is what
   you would expect from a 3× fund.

### Where in the OpEx day?

Mean TQQQ return from the 09:30 open to time *T*, risk-on OpEx days vs other days:

| to | OpEx | other | diff |
|---|---:|---:|---:|
| 10:00 | −31.3 | +5.7 | −37.0 |
| 11:00 | −47.7 | +5.5 | −53.2 |
| 12:00 | −52.1 | +9.5 | −61.5 |
| 13:00 | −51.9 | +9.4 | −61.3 |
| 14:00 | −53.2 | +10.8 | −64.1 |
| 15:30 | −67.6 | +12.4 | −79.9 |
| 16:00 | −78.3 | +12.4 | −90.7 |

The gap opens immediately (the first 30 minutes alone are −37 bp) and widens into
the close, i.e. the loss is a persistent drift, not a single event. The last 30
minutes contribute a further −11 bp. Staying out for the whole session is the
natural implementation; there is no narrow "sweet spot" to overfit.

## 5. Exact rules

Base strategy is the round-1 winner, unchanged:

```
SMA165[d] = mean(QQQ daily close, d-165 … d-1)
MA20[d]   = mean(QQQ daily close, d-20  … d-1)
risk_on   = QQQ close[d-1] > SMA165[d]
if not risk_on:  hold BIL all session
else:            hold TQQQ, and if QQQ 09:30 < MA20[d]*1.01 (armed) and
                 TQQQ close < session_open*0.96 -> sell next minute,
                 stay BIL for the rest of the session and the night
```

Overlay (V1, the primary):

```
if session d is a monthly option-expiry session (third Friday, holiday-shifted):
    keep the overnight TQQQ position
    at the 09:30 bar of d: target TQQQ = 0, BIL = 1   -> fill at 09:31 open
    at the 15:58 bar of d: target TQQQ = 1, BIL = 0   -> fill at 15:59 open
    (if the base strategy is already in BIL, nothing changes)
```

- De-risk asset: BIL (V1, V3, V4) or QQQ (V2, V5).
- V3 keeps 50% TQQQ and 50% BIL intraday instead of going fully flat.
- V4 also applies the same treatment to scheduled FOMC decision days.
- V5 (control) applies it to FOMC + CPI + NFP + OpEx + pre-holiday, into QQQ.
- No leverage, no shorts, one position at a time, weights sum to ≤ 1.
- Fills are next-bar opens; slippage 1/5/10 bp on traded notional.

Two fills per overlaid session (TQQQ→BIL at 09:31, BIL→TQQQ at 15:59). Every one of
the 130 OpEx sessions in the loaded sample is flagged (12 fall in the 2016 warm-up
and change nothing since the regime is already off); 118 fall inside the 10-year
test window and 97 of those are risk-on, where the overlay actually moves the
position. Observed cost: +324 fills vs the winner (657 → 981).

## 6. Calendar construction and look-ahead audit

This is the part that decides whether the result is real, so it is documented in
full. Code: `cal.py`.

| Event | Source | Why it was known in advance |
|---|---|---|
| **FOMC** (65 risk-on days) | `federalreserve.gov/monetarypolicy/fomccalendars.htm` (press-conference + minutes URLs of the form `fomcpresconfYYYYMMDD`, 2012-2026) and `fomchistorical2016/2017/2018/2020.htm` | The Fed publishes the next year's meeting calendar roughly 12 months ahead; the 2026 dates were public in mid-2025. The decision day is day 2 of each scheduled meeting. |
| **CPI** (96) | `bls.gov/schedule/news_release/cpi.htm`, one archived snapshot per year (2017…2026) via web.archive.org | BLS publishes the whole following calendar year's release schedule in advance. Release time 08:30 ET. |
| **NFP** (93) | `bls.gov/schedule/news_release/empsit.htm`, same archive method | Same: annual schedule published in advance, 08:30 ET. |
| **OpEx** (97) | Deterministic: 3rd Friday of each month; if that Friday is an exchange holiday it rolls back to the prior session (e.g. 2026-06-19 Juneteenth → 2026-06-18) | Pure calendar arithmetic; the NYSE holiday calendar is published years ahead. |
| **Pre-holiday** (73) | Deterministic: last trading session before a full-day NYSE holiday (New Year, MLK, Presidents, Good Friday via computus, Memorial, Juneteenth from 2022, July 4, Labor, Thanksgiving, Christmas) | Same. |

Explicit exclusions and caveats:

- **FOMC emergency meetings are excluded** (2020-03-03, 2020-03-15). They cannot be
  known in advance, so including them would be look-ahead. This makes the FOMC row
  conservative.
- **2025 US federal shutdown**: several BLS dates moved (Oct-2025 CPI to 2025-10-24,
  Nov-2025 CPI never published, Nov/Dec-2025 NFP shifted). We keep the realised
  dates — still knowable before the session — but the "published a year ahead"
  claim is weaker for those four prints. The OpEx result does not depend on them.
- **Ad-hoc exchange closures** (2018-12-05 Bush funeral, 2025-01-09 Carter funeral)
  are not used as pre-holiday anchors.
- **Decision timing**: the overlay decision for session *d* is taken at the 09:30 bar
  of *d* and uses only prices at or before that bar. The re-entry time (15:59) is a
  fixed schedule, not a signal. Every fill is at the following bar's open. There is
  no point at which the code touches a price from later in the session.
- **What *is* in-sample**: choosing OpEx out of the five families after looking at
  the data. That is selection, not look-ahead, and it is the main thing to discount
  (Section 9).

## 7. Robustness

### 7.1 Randomisation: is the OpEx set special?

600 random sets of 97 risk-on sessions, same overlay, no-stop daily proxy:

| | p5 | median | p95 | OpEx set | percentile |
|---|---:|---:|---:|---:|---:|
| CAGR | 39.98% | 44.24% | 48.89% | **50.74%** | **99.3** |
| max DD | 52.11% | 54.97% | 57.99% | 53.61% | 14.3 |

The OpEx set beats 99.3% of random same-size sets on CAGR and 86% on drawdown.
The effect is not "de-risking any 97 days".

### 7.2 Sub-period stability of the OpEx gain (no-stop proxy, %/yr of log return)

| Period | n | total | ≈ per year |
|---|---:|---:|---:|
| 2017-2019 | 32 | +10.97% | +3.73% |
| 2020-2022 | 23 | +15.68% | +5.37% |
| 2023-2026 | 42 | +17.38% | +4.69% |

Negative in no era. The 2023-2026 period includes the 0DTE era, which is where the
effect would be expected to weaken if anything.

### 7.3 Neighbouring implementations (harness, 1 bp)

CAGR / DD, 10y and 5y:

| Implementation | 10y | 5y |
|---|---:|---:|
| Full session, BIL (V1) | 67.06 / 40.65 | 53.83 / 35.88 |
| Full session, QQQ (V2) | 64.09 / 41.25 | 52.41 / 35.11 |
| Half TQQQ, half BIL (V3) | 63.00 / 42.01 | 51.97 / 34.68 |
| OpEx + FOMC, BIL (V4) | 69.08 / 43.15 | 54.84 / 34.16 |

The response is monotone in the amount de-risked (V1 > V2 > V3 > baseline on CAGR),
which is what a real drift should look like. It is not a single lucky grid point.

### 7.4 Condition we did **not** promote (descriptive only)

OpEx days split by the opening gap (TQQQ open vs prior close), o2c mean:

| gap bucket | n | o2c |
|---|---:|---:|
| < −2% | 10 | **+105.5 bp** |
| −2 … −0.5% | 16 | −90.9 bp |
| −0.5 … +0.5% | 28 | −88.1 bp |
| +0.5 … +2% | 40 | −76.7 bp |
| > +2% | 7 | −67.0 bp |

The overlay's failure mode is the capitulation open: after a ≤ −2% gap the OpEx
session mean-reverts hard. A rule "skip the overlay if TQQQ opens more than 1-2%
below the prior close" would have kept 81 of 101 events with a mean o2c of −84 bp
and skipped 20 events averaging +21 bp. That is economically sensible (do not fade a
capitulation) and would likely help the 5-year drawdown, but with only 10-26
observations per bucket it is a small-sample fit. **I did not have the compute budget
to run it through the harness, so it is reported as a hypothesis, not a result.**

## 8. Why it might work

- Monthly options expiry concentrates dealer gamma and forces mechanical unwind flow
  into the 4 pm print. The intraday shape (weakness building monotonically into the
  close, largest single bucket at the open) is consistent with an auction/roll-driven
  flow rather than a news shock.
- The overnight leg is untouched, so the overlay gives up none of TQQQ's drift; it
  only avoids the part of the day where the flow is against you.
- The effect is 3× in TQQQ (−64 bp vs −21 bp in QQQ), so the 3× wrapper is the right
  place to express it.
- Prior evidence: OPEX-day weakness in SPY 1993-2024 (average −0.77% on expiry day,
  −23.55% compounded, 51.4% win rate) and the option-expiration-week literature;
  order-imbalance studies document concentrated rollover flow on the third Friday
  and the following Monday. Links in Section 11.

## 9. Limitations

1. **The 5-year drawdown does not improve.** 35.88% vs 33.49% at 1-minute marks
   (+2.39 pp). Even measured from the *winner's* peak (removing the advantage of the
   overlay's higher, earlier peak) it is 34.69% vs 33.49%. The 5-year max DD is the
   2026-06/07 episode, and the overlay's one OpEx day inside it (2026-07-17) gapped
   −6.3% and then rallied +1.7% intraday — exactly the failure mode of Section 7.4.
2. **Selection over five event families.** OpEx was picked after seeing that four
   families have positive intraday returns. Raw t = 2.77 on 97 events
   (two-sided p ≈ 0.007); with a 5-family Bonferroni it is p ≈ 0.03. The
   randomisation test (99.3rd percentile) and the independent SPY prior support it,
   but this is not a pre-registered hypothesis.
3. **The 10-year improvement is not evenly spread.** 2017 is −2.3 pp; the gains are
   concentrated in 2018 (+11.6 pp), 2020 (+32.5 pp), 2021 (+13.0 pp) and 2023
   (+31.0 pp). A handful of large down-OpEx days do most of the work, which is the
   same "cheap tail insurance" profile as the winner's stop.
4. **Costs.** 33 extra round trips a year. At 10 bp the 10-year gain shrinks from
   +8.3 pp to +3.2 pp CAGR. It still dominates the winner at every cost level tested,
   but the edge is not free.
5. **V4 (adding FOMC) is tempting but weakly supported.** It has the best headline
   10-year number (69.08% / 43.15%) and the best 5-year daily-mark DD (30.55% vs
   33.08%), and FOMC's intraday return is −33 bp. But the FOMC swap gain is only
   t = 1.04 and V4 wins on both CAGR and DD in just 13 of 28 rolling windows (vs 27
   for V1). It is reported, not promoted.
6. **Single instrument, single sample, no taxes.** Same caveats as the winner.
7. **BIL carry** is included via BIL's price; the extra time in BIL on 97 sessions
   over 10 years is negligible for carry.

## 10. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents2\event-risk-overlay\strategy.py    # writes result.json
```

Runs in ~12 minutes (36 harness passes over 1.06 M bars). Supporting scripts in the
same folder: `cal.py` (calendars), `explore.py` (event study), `opex_study.py`,
`path_study.py` (intraday shape), `intraday_shape.py`, `robust.py` (t-stats,
randomisation, sub-periods), `random_control.py`, `dd_diag.py`, `variants.py`,
`grid.py`, `summary.py`. No core repository file was modified.

`strategy.py` rebuilds the panel with `bt.panel(("QQQ","TQQQ","BIL"), "2017-01-03",
"2026-10-23", "1min")` and reproduces the winner exactly (58.80/44.56 and
49.88/33.49 at 1 bp) before applying any overlay.

## 11. References

- Lucca, D. O., & Moench, E. (2015). *The Pre-FOMC Announcement Drift.* Journal of
  Finance 70(1). [NY Fed staff report 512](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf)
- *The disappearing pre-FOMC announcement drift* (2020), Finance Research Letters —
  the drift essentially vanished after 2015, which matches our FOMC overnight row
  (+70 bp, i.e. ordinary overnight drift rather than a special pre-FOMC premium).
  [link](https://pmc.ncbi.nlm.nih.gov/articles/PMC7525326)
- Savor, P., & Wilson, M. (2013). *How Much Do Investors Care About Macroeconomic
  Risk?* — higher average equity returns on macro announcement days, consistent with
  our positive CPI/NFP rows.
- *The Options Expiration Week Effect* — OPEX day (close-to-close) averages −0.77%
  on SPY 1993-2024, −23.55% compounded, 51.4% win rate.
  [link](https://quantifiedstrategies.substack.com/p/the-options-expiration-week-effect-aa2)
- *Option-Expiration Week Effect*, Quantpedia (hedge-rebalancing explanation).
  [link](https://quantpedia.com/strategies/option-expiration-week-effect)
- *Option returns: a tale of the expiration rollover day* (FMA 2025) — order
  imbalance concentrated on the third Friday and the following Monday.
  [pdf](https://www.fma.org/assets/docs/Derivatives2025/GarciaAres.pdf)
- *Pre-Holiday Effect*, Quantpedia — pre-holiday returns several times the average
  day; our data agrees (+58 bp close-to-close), which is why de-risking
  pre-holidays loses money. [link](https://quantpedia.com/strategies/pre-holiday-effect)
- *The Pre-Holiday Effect*, StockCharts ChartSchool (50-year S&P 500 table).
  [link](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/the-pre-holiday-effect)
- Kaminski, K. M., & Lo, A. W. (2014). *When do stop-loss rules stop losses?*
  Journal of Financial Markets 18 — the theoretical basis for the winner's stop.
  [doi](https://doi.org/10.1016/j.finmar.2013.07.001)
- Federal Reserve FOMC calendars: [fomccalendars.htm](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
- BLS CPI release schedule: [bls.gov/schedule/news_release/cpi.htm](https://www.bls.gov/schedule/news_release/cpi.htm);
  Employment Situation: [empsit.htm](https://www.bls.gov/schedule/news_release/empsit.htm)
