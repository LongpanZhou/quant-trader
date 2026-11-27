# Post-Capitulation Session Reversal (PCSR)

**Slug:** `intraday-mean-reversion` · **Rebuild:** `research/revisit/intraday-mean-reversion/`
**Status: PENDING — backtests paused by user instruction (2026-11-26).**
`strategy.py` is written and syntax-checked; `result.json` has **not** been generated.
All numbers in §8 are preliminary, from the pre-freeze development run that
completed before the pause; the frozen code must regenerate them before any of
them is quoted as a result.

---

## 1. The idea in one sentence

After a ≥3 % intraday QQQ capitulation, the forced selling is not finished by
the close, but the **next session's open-to-close** carries a large positive
liquidity-provision premium — so buy TQQQ at the next open, sell before that
session's close, and hold BIL (never overnight) otherwise.

## 2. What is genuinely new here (not "the old base minus the MA")

| | Original | PCSR rebuild |
|---|---|---|
| Return driver | QQQ trend (price > 165-day SMA) | liquidity provision after forced selling |
| Time in TQQQ | ~78 % of sessions, including every night | ~4–5 % of sessions, **never overnight** |
| Holding period | weeks to months | one session (≈6.5 h) |
| Signal | slow moving average | intraday drawdown event |
| Risk profile | full gap/crash risk | no gap risk by construction; event risk only |
| Assets | QQQ gate, TQQQ/BIL | QQQ signal, TQQQ vehicle, BIL cash |

There is no 100–250-day moving average on QQQ, TQQQ, SPY or NDX anywhere in the
strategy, and no old weight matrix or `build_weights` is imported or copied.
The old base is computed **only** to measure the correlation reported in §9.

## 3. Hypothesis (falsifiable)

> A ≥3 % intraday decline in QQQ is a liquidity shock. Market makers and
> short-horizon liquidity providers are compensated for absorbing it, and that
> compensation is realised in the **next session's open-to-close return**, not
> in the remainder of the trigger session and not in the overnight gap.
> Therefore a strategy that is long TQQQ only during the session after a
> capitulation should earn a positive, economically meaningful return with low
> correlation to a trend-following base.

Mechanism references: Nagel (2012) shows short-term reversal returns are the
return to liquidity provision and spike in turmoil; Lou–Polk–Skouras and the
NY Fed overnight-drift work show the reversal is concentrated across the
overnight/intraday boundary; Gao et al. show intraday moves otherwise continue,
which is why the trade is *not* a same-day dip-buy.

## 4. Universe and data

| Role | Instrument | Data |
|---|---|---|
| Signal | QQQ | 1-minute adjusted, 2016-01-04 → 2026-10-23 |
| Vehicle | TQQQ | 1-minute adjusted, same span |
| Cash | BIL | 1-minute adjusted, same span |
| Validation / benchmark | SPY | daily adjusted (`data/round3/yahoo/SPY-1d-yahoo.parquet`), 2015-01-02 → 2026-10-23 |

Data limits that shaped the design:

- No 1-minute SPY before 2026 (Dukascopy cache is only Aug–Nov 2026), and no
  sector, bond, gold or volatility-product history. The **trading** universe is
  therefore QQQ/TQQQ/BIL. SPY daily is used only for the out-of-universe check
  in §7 and as a benchmark.
- TQQQ is used only for a one-session hold, so the daily-reset decay that makes
  long-dated 3× exposure expensive is second-order (FinLab's decomposition puts
  the drag at −15.2 pts/yr for full-time exposure, not for 6.5 hours).
- Half days (13:00 close) and the 18 sessions with missing minutes are handled
  by session-index arrays (`first`/`last` per date), never by clock time.

## 5. Exact specification

**Signal (per session k):**

```
prev_close_k = QQQ last 1-minute close of session k-1        (15:59)
dd_k         = min over t in session k of QQQ_t / prev_close_k - 1
event_k      = dd_k <= -3.0%
```

The minimum is over 1-minute **closes**, so it is known exactly at session k's
15:59 close. Session 0 has no prior close and can never be an event.

**Position:**

- If `event_k`, target 100 % TQQQ for session k+1, set at session k's last bar
  → filled at session k+1's 09:30 open.
- Exit: target 0 at session k+1's second-to-last bar → filled at the final
  bar's open (15:59). The position is flat through the 15:59 bar and overnight.
- Otherwise 100 % BIL.
- Consecutive events are separate one-session trades; the book is flat between
  the close of one held session and the open of the next.

**Sizing and risk:**

- 100 % of equity in TQQQ during the held session (no leverage beyond TQQQ);
  no pyramiding.
- No stop-loss: a −3 % intraday stop on the held session was tested in the
  preliminary run and made the result worse (9.69 % vs 17.12 % CAGR), because
  the stop sells the reversal it is trying to own. Pre-registered as V4.
- Structural risk control: **no overnight exposure**, one session per event,
  cash otherwise.

**Execution:** weights at bar *i* fill at bar *i+1* open; 2 % band; 1 bp
headline, 5 bp and 10 bp reported. No shorting, so no borrow cost.

## 6. Timing and no-look-ahead proof

1. `dd_k` uses only bars of session k, all ≤ 15:59 of session k.
2. The entry weight is written at session k's last bar and executed at the first
   bar of session k+1. There is no same-bar fill anywhere.
3. The exit weight is written at the second-to-last bar and executed at the last
   bar's open. The last bar's close is used only for marking equity.
4. `prev_close_k` is the previous session's last close, strictly earlier.
5. No moving average of any length is used.

The audit cuts at 2020-03-12 11:07 and 2022-09-13 10:41 should leave every
weight before the cut identical; the strategy only reads data up to each bar.

## 7. Pre-registered tests (to run only when authorised)

| # | Test | Expectation / decision rule |
|---|---|---|
| P0 | Primary: threshold 3.0 %, 1 session, TQQQ, dev 2016-01-04→2023-12-29 | Positive CAGR at 1/5/10 bp; corr < 0.60; event mean > 0 with cluster-bootstrap p < 0.10 |
| V1 | Threshold neighbours 2.5 %, 3.5 %, 4.0 % | Same sign; report the plateau, including where it breaks |
| V2 | 5-minute closes instead of 1-minute for the event | Same effect (granularity check) |
| V3 | 2-session and 3-session holds | Expected worse drawdown; confirms the one-session identity |
| V4 | −3 % intraday stop on the held session | Expected worse (preliminary: 9.69 % vs 17.12 %) |
| V5 | QQQ as the vehicle instead of TQQQ | Lower return and lower drawdown; report both |
| V6 | Vol-scaled size: min(1, 1 % / σ20) | Risk variant, not the primary |
| V7 | Cluster cap: half size on a repeat event within 3 sessions | Risk variant |
| V8 | Placebo: 89 randomly chosen sessions, same one-session hold | Mean near the unconditional +0.10 %, far below the event mean |
| V9 | Sub-periods 2016–19, 2020–21, 2022–23 | All three positive; 2022–23 is the weak one (preliminary ≈ 0) |
| V10 | SPY daily out-of-universe check (low/prev close ≤ −2 %, ≤ −3 %) | Same sign on a second index if the effect is market-wide, not QQQ-specific |
| V11 | Correlation vs the old 165-day base, daily returns, dev overlap | Must be < 0.60 (preliminary 0.181) |
| V12 | Bootstrap over event clusters (gap > 5 sessions), 5,000 draws | Report n events, n clusters, one-sided p |

`variants_tried` counts the pre-registered set above; any additional variant
found during the run must be added to the report with its result, not silently
dropped.

## 8. Preliminary development evidence (pre-freeze, paused run)

These numbers come from the development-only harness that completed before the
pause (`scratch/explore_dev.py`, `scratch/dev_eval.py`). **They are not the frozen
result and must be reproduced by `strategy.py`.**

Old 165-day base on the same dev window, 1 bp, for scale: **44.76 % CAGR /
58.76 % DD / 1.02 Sharpe**.

| Variant | Events | CAGR 1 bp | Max DD | CAGR 5 bp | CAGR 10 bp | Corr vs base |
|---|---:|---:|---:|---:|---:|---:|
| **P0: 3.0 %, 1 session, TQQQ** | **89** | **17.12 %** | **22.24 %** | **15.34 %** | **13.16 %** | **0.181** |
| V1: 2.5 % | 150 | 17.62 % | 31.77 % | 14.84 % | 11.46 % | 0.216 |
| V1: 3.5 % | 58 | 7.35 % | 22.24 % | 6.26 % | 4.90 % | 0.192 |
| V1: 4.0 % | 35 | 6.61 % | 22.24 % | 5.95 % | 5.12 % | 0.152 |
| V3: 2-session hold | 89 | 5.30 % | 64.46 % | 4.08 % | 2.57 % | 0.230 |
| V3: 3-session hold | 89 | 10.52 % | 67.43 % | 9.37 % | 7.94 % | 0.268 |
| V4: −3 % stop on held session | 89 | 9.69 % | 24.65 % | 7.75 % | 5.37 % | 0.100 |
| V5: QQQ vehicle | 89 | 6.86 % | 7.82 % | 5.24 % | 3.25 % | 0.178 |

Event study (5-minute event definition, dev): 84 events, next-session TQQQ
open→close **+1.346 %** mean, +0.99 % median, 60 % win, vs an unconditional
next-session mean of **+0.099 %**. By sub-period: 2016–19 +1.34 % (n=29),
2020–21 +2.51 % (n=29), 2022–23 **+0.05 %** (n=26).

What the preliminary table already says, honestly:

- The one-session hold is the only robust expression. Two- and three-session
  holds keep the same event count but blow the drawdown to 64–67 %; the reversal
  is a session effect, not a multi-day recovery.
- The threshold is **not** a flat plateau: 2.5 % and 3.0 % are similar (17.6 vs
  17.1 %), but 3.5 % drops to 7.4 %. The 3.0–3.5 % band carries much of the
  edge, so the exact CAGR is threshold-sensitive. V1 and V6 must be reported in
  full, and the threshold must be described as chosen at the upper edge of a
  two-point plateau, not a smooth optimum.
- 2022–23 is the weak sub-period (≈0 % mean per event). The strategy is not
  immune to a grinding bear market; it simply has no overnight or trend
  exposure to lose.
- The −3 % stop and the multi-day holds were rejected on the evidence, not
  assumed.

## 9. Correlation

Preliminary dev daily-return correlation with the old 165-day base: **+0.181**
(n ≈ 1,800 overlapping sessions). The mechanism for the low correlation is
structural: the strategy is in cash on ~95 % of days, never overnight, and its
few active days are selected by a panic event rather than by trend state. The
brief's limit is 0.60.

Correlation with other rebuilt strategies: **not yet computed** — the lead's
`correlations.json` is the authority. Because this strategy holds no position
on ~95 % of days, pairwise correlation with any continuously-invested rebuild
should be low, but it must be measured, not assumed.

The closest neighbour in the rebuild set is likely `gap-capitulation-reversal`
(buying after a *gap-down* capitulation). The two are distinct: PCSR triggers on
the **intraday drawdown** (not the opening gap), holds exactly one session with
**no stop and no regime exit**, and is flat overnight by construction. If the
lead measures a correlation above 0.70, the differentiator to test is the
trigger (intraday drawdown days that do *not* gap down at the open), not a
parameter tweak.

## 10. Falsifiers (what would kill the idea)

1. **Dev CAGR ≤ 0 at 1 bp**, or the 5 bp result collapsing to ≤ 0.
2. **Event mean not above the unconditional next-session mean**: cluster
   bootstrap p > 0.10 on the 89 events.
3. **No positive sub-period**: 2022–23 already ≈ 0; if 2016–19 or 2020–21 also
   turns negative, the effect is not stable.
4. **Granularity artifact**: the 5-minute event definition fails while the
   1-minute works (or vice versa).
5. **Single-cluster dependence**: removing the largest event cluster (2020-03)
   kills the result.
6. **The bounce is really the overnight gap**: if buying at the open and
   selling at the close has no edge but holding from the prior close does, the
   mechanism in §3 is wrong and the strategy should be re-specified or retired.
7. **Correlation ≥ 0.60** with the old base: the idea is not distinct enough to
   justify a separate strategy.

## 11. Results (to be filled by the authorised run)

| Window | Cost | CAGR | Max DD (1 m marks) | Max DD (daily marks) | Sharpe | Fills |
|---|---|---:|---:|---:|---:|---:|
| dev 2016-01-04→2023-12-29 | 1 bp | TBD | TBD | TBD | TBD | TBD |
| dev | 5 bp | TBD | TBD | — | — | — |
| dev | 10 bp | TBD | TBD | — | — | — |
| 10y 2017-01-03→2026-10-23 (overlaps holdout) | 1 bp | TBD | TBD | TBD | TBD | TBD |
| 10y | 5 bp | TBD | TBD | — | — | — |
| 5y 2021-10-25→2026-10-23 (overlaps holdout) | 1 bp | TBD | TBD | TBD | TBD | TBD |
| 5y | 5 bp | TBD | TBD | — | — | — |

Benchmarks on dev: TQQQ, QQQ, SPY (daily), and the original strategy's own
numbers (10y 50.96 %/44.83 %, 5y 35.50 %/36.29 %, 1 bp).

The 10y and 5y windows overlap the holdout. They will be produced once by the
frozen code and labelled as overlapping; they are **not** used for any design
decision. The lead runs the holdout-only window.

## 12. Limitations and risks

- **Small event count.** 89 events, 41 clusters in 8 years. The bootstrap is the
  right inference; the point estimate of CAGR is not precise.
- **Threshold sensitivity.** See §8: 3.0 % sits at the edge of the 2.5–3.0
  plateau. The report must show the full neighbourhood.
- **2022–23 flat.** A sustained bear market can remove the edge for years.
- **TQQQ-specific.** The bounce is leveraged; a 3× vehicle magnifies both the
  +1.35 % mean and the left tail. V5 (QQQ) is the lower-risk alternative.
- **Execution.** The exit is at 15:59, not the closing auction. Real closing
  auctions may price slightly better or worse; 5/10 bp sensitivity covers it.
- **No cross-asset confirmation.** SPY 1-minute is not available before 2026,
  so the "is this market-wide?" check uses SPY daily only.

## 13. Provenance

| Design choice / claim | Source | Role | Evidence used | Confidence |
|---|---|---|---|---|
| Short-term reversal is compensation for liquidity provision and spikes in turmoil | Nagel, S. (2012), "Evaporating Liquidity", *Review of Financial Studies* 25(7), 2005–2039. <https://www.nber.org/papers/w17653> · <https://academic.oup.com/rfs/article-abstract/25/7/2005/1602153> | supports the core hypothesis | VIX predicts reversal-strategy returns; reversal profits and conditional Sharpe ratios spike in financial turmoil; interpretation is liquidity supply withdrawal | high |
| Overnight and intraday returns reverse each other; the reversal sits across the overnight boundary | Lou, Polk & Skouras, "A Tug of War: Overnight versus Intraday Expected Returns". <http://www.econ.yale.edu/~shiller/behfin/2015-04-11/lou_polk_skouras.pdf> | supports the timing (next session, not same session) | documents negative cross-prediction between overnight and intraday returns | medium |
| End-of-day price pressure reverses overnight | "The Overnight Drift", NY Fed Staff Report 917. <https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf> | context only | documents the overnight drift and reversal of end-of-day pressure; not used to set the threshold | low |
| Intraday moves continue within the session (so do not buy the dip intraday) | Gao, Han, Li & Zhou (2018) intraday momentum; "Does overnight return predict the first half-hour return…". <https://www.sciencedirect.com/science/article/abs/pii/S1062940826001294> | supports the "exit at the close, enter next open" structure | intraday-momentum / time-series continuation evidence, consistent with the measured −0.04 to −0.05 % continuation after −0.5…−1 % 30-minute moves | medium |
| Daily-reset decay is a function of holding period, so a 3× ETF is acceptable for a 6.5-hour hold | FinLab, "Leveraged ETF Decay". <https://finlab.finance/en/blog/leveraged-etf-decay>; Cheng & Madhavan (2009) via <https://quantpedia.com/shorting-leveraged-etfs-the-role-of-borrowing-costs-and-rebalancing-in-volatility-decay-strategies/> | supports the TQQQ vehicle choice | TQQQ −15.2 pts/yr volatility drag and −6.9 pts/yr costs for full-time exposure; decay is a daily-reset, path-dependent effect | medium |
| ≥3 % intraday QQQ drawdown → next-session long, one session, no stop | Own test / no external source | **inspired rule** | 84–89 dev events, next-session +1.35 % vs +0.10 % unconditional; preliminary 17.12 % CAGR / 22.24 % DD / 0.181 correlation | high (measurement) / medium (stability) |
| Next-bar-open fills, 2 % band, 1 bp headline | Project `research/bt.py` harness | supports the execution assumptions | `bt.simulate` compiled core; weights at bar i fill at open i+1 | high |

### Rejected / tested-only sources

| Source | What was tested | Why it was not used |
|---|---|---|
| Connors & Alvarez, RSI(2) mean reversion (via <https://finabase.io/learn/strategies/rsi-mean-reversion>) | RSI(2) < 10 intraday dip-buy with a 165-day gate | +5.87 %/yr gross, −2.43 %/yr at 1 bp, −29.61 %/yr at 5 bp on 10y; the 1–2 bp edge is below the 2 bp round-trip cost |
| "RSI(2) on QQQ has no edge" (<https://tradeinsight.info/posts/rsi2-has-no-edge>) | independent confirmation | gross Sharpe 0.72 vs 0.94 buy-and-hold, 2010–2025 |
| Bollinger(20,2) and VWAP-deviation dip-buying (own test) | 5-minute band/deviation entries | −2.65 % and +2.25 % gross; negative at 1 bp; deviation buckets only span ±0.2 % |
| Opening-gap fade (own test) | fade QQQ gap-downs at 09:35 | gaps continue: −1.0…−0.7 % gap → −0.22 % to close; +1…+5 % gap → +0.68 % to close |
| Multi-session hold and intraday stop (own test) | 2/3-session holds; −3 % stop | 64–67 % drawdown and 9.69 % CAGR respectively; rejected on the evidence |

## 14. Status rule

`strategy.py` sets `status = "passed"` only if all three hold on dev:
1 bp CAGR > 0, correlation < 0.60, cluster-bootstrap `p_mean_le_0` < 0.10.
Otherwise it writes `"rejected"`. `"retired_overlay_only"` is not applicable:
the strategy is a complete long/flat event strategy, not a stop or filter on
another base. The final status is the auditor's and the lead's, not this file's.
