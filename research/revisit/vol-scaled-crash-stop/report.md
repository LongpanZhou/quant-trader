> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Vol-scaled crash system (VSCS) - standalone rebuild

**Slug:** `vol-scaled-crash-stop` · **Original:** `research/agents2/vol-scaled-crash-stop`
**Status: `pending_test` (dev only).** The strategy, hypothesis and falsifiers are frozen;
the dev/holdout runs are paused until the lead authorises the test.
This report separates **measured** evidence (the pre-pause exploration of the binary
core) from **projected** behaviour of the primary (sized) design. No holdout bar has
been loaded: the panel is physically truncated at 2023-12-29.

---

## 1. The extracted idea

The original strategy's only genuinely new element was **one-sided, volatility-scaled
stop distance**:

```
d = clip(0.70 x ATR14(TQQQ daily), 2.5%, 4.0%)
```

Tight when volatility is low, but **never wider than the 4% level that protects against
the gap nights the stop exists to avoid**. The 165-day QQQ regime underneath was the
shared base and is discarded here.

The underlying effect, measured in round 2 on 2017-2026 (204 stop events): after TQQQ
breaks `open x (1 - d)`, the mean move from the exit fill to the next session's open is
**-0.46%** (median -0.32%), with 55% of events reversing and the mean carried by a fat
left tail. The break is a *conditional continuation* signal, not an average-day signal.

## 2. Hypothesis (written before the test)

> A complete strategy can be built from this effect alone: hold TQQQ by default, size
> it inversely to ATR, and when the one-sided ATR barrier breaks, move the TQQQ sleeve
> to BIL for the rest of the session and the night. Removing the 165-day trend gate
> should leave a **lower-drawdown** strategy with **daily-return correlation below 0.60**
> against the old base, because the crash exits and the inverse-vol size reduce exposure
> exactly in the high-variance periods that drive the old base's returns.

The base is not a moving-average regime: it is "own TQQQ, but volatility decides both
the size and the exit". There is no QQQ/TQQQ/SPY/NDX 100-250 day MA anywhere.

## 3. Falsifiers (decided before the test)

The rebuild is **retired as overlay-only** if any of these hold on the development window:

1. **Diversity:** daily-return correlation with the 165-day baseline `>= 0.60`.
   (Already true for the binary core: 0.64 - see section 7.)
2. **No risk improvement:** max drawdown is not materially below the 165-day baseline's.
3. **No return left:** CAGR falls below the 165-day baseline (44.8% on dev) *and* the
   drawdown is not at least 10 pp lower - then the strategy is dominated.
4. **Signal is noise:** the matched-frequency placebo (same number of exits on random
   sessions/minutes) matches or beats the strategy's CAGR or Sharpe.
5. **Tail-only artefact:** the event mean is not significantly below zero
   (bootstrap `p(mean >= 0) > 0.10`) or the result depends on fewer than 10 events.
6. **Cost-fragile:** 5 bp net Sharpe < 0.5, or 10 bp net CAGR below BIL.
7. **Sub-period instability:** the result is carried by one of 2016-19 / 2020-21 / 2022-23.

## 4. Universe and data

| Item | Value |
|---|---|
| Tradable | **TQQQ** (long only), **BIL** (cash) |
| Data | `data/intraday-hf/*-1m.parquet` (QQQ/TQQQ/BIL), regular session, adjusted |
| Marks | 1-minute (`research/bt.py` + `simcore`), 2% band, next-open fills |
| Dev window | **2016-01-04 .. 2023-12-29** (2,012 sessions; the 1m archive starts on 2016-01-04, so there is no pre-2016 intraday warm-up) |
| Holdout | 2024-01-02 .. 2026-10-23 - **not loaded by this agent** |

SPY exists only as a daily benchmark (`data/round3/yahoo/SPY-1d-yahoo.parquet`); the
data note forbids using it as a tradable asset because there is no 2016-2023 intraday
history. No sector/bond/gold 1-minute history exists locally, so the rebuild stays in
the QQQ/TQQQ/BIL universe. This is the main limitation on how different the strategy
can be: any long-only strategy on this universe is a TQQQ-beta strategy at heart.

## 5. Exact rules (frozen spec)

For each session `k` (09:30-15:59 ET), with `ATR14[k]` = mean true range of TQQQ daily
bars over the prior 14 sessions divided by the prior close (daily bars are aggregated
from the 1-minute panel; no bar after `k-1`'s close is used):

```
size[k] = clip(0.040 / ATR14[k], 0.40, 1.00)
dist[k] = clip(0.70 * ATR14[k], 0.025, 0.040)

default:   TQQQ = size[k], BIL = 1 - size[k]
trigger:   first 1-minute close with  close < session_open * (1 - dist[k])
on trigger: TQQQ sleeve -> BIL on that bar (fills at the next bar's open);
            stay 100% BIL for the rest of the session and the night
re-entry:  next session's open at size[k+1]
```

- No moving average of any length is used for the gate; the only price reference is the
  session open and ATR.
- Long only, no leverage beyond 100% TQQQ, gross <= 1.
- The first 13 sessions of 2016 have no ATR (the 1m archive starts 2016-01-04): the stop
  is disabled and the size is 1.0 there, which is causal.
- `size` uses ATR through the prior close, so it is known before the session opens.

**Parameters and why:** `0.70` is the centre of the round-2 plateau (0.55-0.85); `2.5%`
is the tight bound (16x TQQQ's 1-minute ATR); `4.0%` is the round-1 validated crisis
stop, inherited as a bound, not re-fitted; `0.040` is TQQQ's long-run median ATR (so the
median size is ~0.95 and the strategy is fully invested in calm markets); `0.40` is the
crisis floor (2022 ATR ~8.2% -> size 0.49 before the floor).

## 6. Why this is not the old base

| | Original | This rebuild |
|---|---|---|
| Slow gate | QQQ > 165-day SMA | **none** (no 100-250 day MA) |
| Default position | TQQQ when regime on, BIL otherwise | TQQQ always, at an inverse-vol size |
| Exit | armed 4% stop from the open | one-sided ATR barrier, always armed |
| Re-entry | next session if regime on | next session unconditionally |
| Time in TQQQ | 78% (10y) | ~85% by size, 100% of days at some size |
| Correlation with 165d base | 1.00 | 0.64 measured (binary core); target < 0.60 |

## 7. Measured evidence (pre-pause, binary 100% core)

These are the only dev numbers that exist. They come from `explore.py` / `explore.json`,
run **before** the backtest pause, on 2016-01-04..2023-12-29, 1 bp, 1-minute marks,
all-BIL exit, **100% TQQQ sizing** (`use_sizing=False` in `strategy.py`). They are not a
new run and not the final frozen result.

| Variant (binary 100%) | Events | CAGR | Max DD | Corr vs 165d | Fills |
|---|---:|---:|---:|---:|---:|
| Pure stop, re-enter next open | 452 | **65.10%** | **59.43%** | **0.64** | 1,807 |
| Fixed 4% (no ATR) | 340 | 57.20% | 60.22% | 0.67 | 1,361 |
| ATR x1.00 | 378 | 59.67% | 60.22% | 0.66 | 1,513 |
| ATR x0.55 | 498 | 71.97% | 56.62% | 0.63 | 1,991 |
| Cooldown 5 sessions | 219 | 26.87% | 42.65% | 0.44 | 875 |
| Cooldown 10 sessions | 141 | 12.69% | 36.07% | 0.39 | 563 |
| Arm on QQQ gap-down open | 219 | 47.48% | 75.31% | 0.67 | 877 |
| Arm on QQQ first-minute down | 226 | 42.96% | 75.68% | 0.68 | 905 |
| **165-day baseline** | - | **44.76%** | **58.76%** | 1.00 | - |
| **TQQQ buy & hold** | - | **35.98%** | **81.68%** | - | - |

The pre-pause baseline used the panel's daily closes, so its 165-day SMA is cold for
the first 165 sessions (the strategy sits in BIL through Aug-2016). The frozen
`strategy.py` seeds the SMA from the QQQ daily parquet instead, so the baseline and the
correlations may move by a few tenths of a point when the test is authorised.

Reading:

- The pure stop is a **real standalone return edge** (+20 pp CAGR over the baseline) but
  it is **not a risk strategy**: 59.4% DD vs the baseline's 58.8%. It cuts TQQQ's 81.7%
  by skipping crash tails, but that is roughly the same protection the slow trend gate
  already provides - and it keeps every multi-month bear.
- Its correlation is **0.64**, above the 0.60 diversity rule. The variants that do pass
  the rule (cooldown 5: 0.44) give up most of the return (26.9% CAGR), because the
  measured continuation lasts only to the next open - staying out longer misses the
  reversal day.
- The ATR scale matters: at the same trigger, ATR x0.55 beats fixed 4% on both CAGR and
  DD (72.0/56.6 vs 57.2/60.2), consistent with round 2.

**So the binary core already fails the rebuild on two of the seven falsifiers
(correlation 0.64 and no drawdown improvement).** The remaining question is whether the
inverse-vol sizing layer (the primary spec) fixes either one.

## 8. Projected primary (not measured)

The primary adds `size = clip(0.040/ATR, 0.40, 1.0)`, so it holds ~95% TQQQ in calm
markets, ~65% in 2020 and ~49% in 2022. Expected direction (to be verified, not claimed):

- drawdown **lower** than the binary core (crisis exposure roughly halved);
- CAGR **lower** than the binary core (less beta in the recoveries);
- correlation vs the 165-day base **uncertain**: the sizing cuts exposure on the
  high-variance days that dominate covariance, but those days are also when the baseline
  is sometimes out of the market, which can push correlation either way.

Working estimate: **0.50-0.65**, with the 0.64 binary measurement as the upper anchor.
The primary passes only if it lands **< 0.60** and keeps CAGR above the baseline (44.8%)
or cuts drawdown by at least 10 pp. If it does not, the strategy is **retired
overlay-only**: the ATR barrier is a crash hedge that needs a trend gate to control the
multi-month bear, which is exactly the shared base it was supposed to replace.

## 9. Overfitting controls (in `strategy.py`, to be run with the test)

- **Variants tried:** 12 (primary, binary ablation, cooldowns 1/2/5, ATR 0.55/1.00,
  fixed 4%, size floors 0.30/0.50, targets 0.030/0.050).
- **Neighbourhood table:** each parameter moved one step, reported as a plateau, not a
  peak. The frozen values are the centre of the round-2 surface plus round-number bounds.
- **Sub-periods:** 2016-19, 2020-21, 2022-23, per variant.
- **Placebo:** 40 matched-frequency draws (same number of exits on random sessions and
  random minutes), reported as a CAGR/DD/Sharpe distribution.
- **Event study:** trigger fill -> next open, with a 10,000-draw bootstrap
  `p(mean >= 0)`; the effect is only credible if this is small and the event count is
  large (452 in the binary core).
- **Costs:** 1 bp headline, 5 bp and 10 bp for the primary and the binary ablation.
- **Holdout:** untouched; the lead runs it once on the frozen strategy.

## 10. Provenance

| Claim / rule | Source | Role |
|---|---|---|
| ATR-multiple exits (Chandelier/ATR construction) | Quant Arenas, Chandelier Exit backtest, https://quantarenas.com/strategy/trend-17-chandelier-exit | inspired rule |
| ATR stops are not automatically better than % stops; trailing ATR underperforms | Cesar Alvarez / Better System Trader #037, https://bettersystemtrader.com/037-cesar-alvarez-studies-stop-losses | tested only (null) |
| ATR multiplier O(1), sub-1.0x ATR collapses under noise | FXNX 20,000-trade study, https://fxnx.com/en/blog/stop-loss-distance-vs-hit-rate-20-000-trade-study | calibration |
| Stops add value under momentum / negative conditional skew | Kaminski & Lo (2014), https://papers.ssrn.com/sol3/papers.cfm?abstract_id=968338 | supports assumption |
| Volatility-scaled risk exposure | Moreira & Muir (2017), https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431 | supports assumption |
| Volatility clustering makes fixed distances regime-dependent | Arrow Algo, https://arrowalgo.com/volatility-clustering | supports assumption |
| Leveraged ETFs rebalance at the close; flows can amplify declines | Cheng & Madhavan (2009), https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995; Avellaneda & Zhang (2010), https://epubs.siam.org/doi/10.1137/090760805 | mechanism |
| LETF/option rebalancing price effects are transitory and reverse the next day | Mathis & Moerke (2022), https://wp.lancs.ac.uk/fofi2022/files/2022/08/FoFI-2022-027-Mathis-Moerke.pdf | boundary condition (why the exit is overnight only) |
| Post-decline end-of-day flow and late-day volatility | Lenkey (2024), https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4710812; ETF.com, https://www.etf.com/sections/equity/one-bad-day-levered-qqq-etf-case-study | mechanism |
| Trigger -> next-open mean -0.46%, median -0.32%, 204 events | Own test, round-2 `report.md` and `events_final.py` | primary evidence |
| 4% cap, 2.5% floor, 0.70 multiplier, 0.040 sizing target | Own test / no external source (round-2 plateau; 4% inherited from the round-1 stop) | design |

The transitory-flow finding is the reason the strategy re-enters at the next open instead
of holding a multi-day short/avoidance: the flow impact reverses during the next session,
so the exploitable window is the gap, not the following day.

## 11. Reproduction (paused)

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
# after the lead authorises the test:
python research\revisit\vol-scaled-crash-stop\strategy.py
```

`strategy.py` builds the dev panel (cached to `dev_panel.npz`), computes the ATR from the
same adjusted prices, runs 12 variants plus 40 placebos through `bt.run_many`, writes
`result.json` with dev 1/5/10 bp, yearly, sub-periods, correlation vs the 165-day
baseline and the event study. `holdout`, `10y` and `5y` are written as `null` for the
lead to run once on the frozen strategy. No core file is modified.
