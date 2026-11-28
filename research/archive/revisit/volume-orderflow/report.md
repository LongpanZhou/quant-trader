> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Rebuild: participation exhaustion long (`volume-orderflow`)

**Status: hypothesised, awaiting authorisation. Backtests paused. No results.**
**Dev period:** 2016-01-04 → 2023-12-29 · **Holdout:** never inspected by this agent.
**Spec:** `spec.md` · **Pre-registration:** `hypothesis.md` · **Sources:** `provenance.md`

---

## 0. Independence from the old base

| Old base element | Present in this rebuild? |
|---|---|
| QQQ close vs 165-day SMA regime | **No.** No moving average of any length on QQQ/TQQQ/SPY/NDX is used as a gate. |
| Round-1 4% armed minute stop | **No.** There is no price stop at all; the exit is a five-session clock. |
| Reused `build_weights` / old weight matrix | **No.** `strategy.py` builds weights from this event only. The old code was read for the idea, not imported. |
| 100% TQQQ held ~78% of the time | **No.** Expected exposure 25–40%, in discrete five-session bursts. |

The only place the 165-day rule appears is `main()`, as a **benchmark and
correlation reference** — never as a gate.

## 1. The idea in one paragraph

The original strategy discovered one thing: participation decides whether a price
move is information. It could only express that as a stop filter, which is why it
was an overlay. Generalising the same claim into a return forecast gives a
complete strategy: when QQQ sells off **inside the session** on well-above-normal
volume and still **closes in the upper half of its range**, the selling has been
absorbed, and TQQQ should rise over the next five sessions. When it does not, hold
BIL.

## 2. Rules (exact; see `spec.md` for the implementation-level version)

1. Session aggregates from QQQ's own bars: `rvol` = volume ÷ mean of the prior 20
   sessions; `intraday` = close ÷ open − 1; `clv` = close location in the range.
2. **Event** = `rvol ≥ 1.5` **and** `intraday ≤ −0.8%` **and** `clv ≥ 0`.
3. On an event, buy **100% TQQQ at the next session's open**, hold **5 sessions**,
   exit at an open. A new event extends the window.
4. Otherwise **100% BIL**. Long-only, no leverage beyond the 3× ETF, no stop.
5. Costs: 1 bp headline, 5/10 bp reported. Next-open fills, 2% band, minute marks.

## 3. Results

*Not run. Backtests are paused; `strategy.py --authorized` has not been executed
and no `result.json` exists.*

To be filled, once authorised:

| Window | 1 bp CAGR / DD / Sharpe | 5 bp | 10 bp | Fills | Exposure |
|---|---:|---:|---:|---:|---:|
| dev 2016-01-04 → 2023-12-29 | TBD | TBD | TBD | TBD | TBD |
| holdout (lead only) | — | — | — | — | — |
| 10y / 5y (lead only) | — | — | — | — | — |

| Benchmark (dev) | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| TQQQ buy-and-hold | TBD | TBD | TBD |
| QQQ buy-and-hold | TBD | TBD | TBD |
| BIL | TBD | TBD | TBD |
| 165-day baseline *(reference only)* | TBD | TBD | TBD |

## 4. What must be reported before any claim is made

1. **Event statistics**: number of events, number of non-overlapping holds,
   mean/median five-session TQQQ return after events vs unconditional, bootstrap
   p-value (one-sided).
2. **Falsifier table** F1–F8 from `hypothesis.md` §4, each with its number and a
   pass/fail cell.
3. **Parameter surface** 3 × 3 × 2 × 3 (rvol × intraday × clv × hold) with the
   plateau marked, plus the 60-session rvol baseline and the 50% size variant.
4. **Sub-periods** 2016–19 / 2020–21 / 2022–23.
5. **Placebo** with 500 draws.
6. **Correlations**: vs the 165-day baseline (target < 0.60) and vs every other
   rebuilt strategy the lead reports (target < 0.70).
7. **Cost decomposition**: fills × notional × bps, so the 10 bp row can be checked.

## 5. Known risks to the design

| Risk | Why it matters | Mitigation in the spec |
|---|---|---|
| **Thin sample.** `rvol≥1.5 & intraday≤−0.8% & clv≥0` may fire only 15–30 times in 8 years. | Bootstrap power is low; a single 2020 event can dominate. | F4 sub-periods, F5 placebo, and an explicit "retire without running if < ~40 events" note in `hypothesis.md` §7. |
| **2020 concentration.** The round-2 gain was a 2020 artifact; this design could repeat that mistake. | A crash-only edge is a hedge, not a strategy. | Report the event mean with and without 2020-02-20→2020-04-30; F4 requires the sign in two of three sub-periods. |
| **Collision with `gap-capitulation-reversal`.** Both buy after declines. | The brief requires < 0.70 pairwise. | This event requires an **intraday** decline and a close off the low, and excludes gap-driven moves by construction; that agent keys on the gap. If the lead still measures ≥ 0.70, this design should be dropped, not tuned. |
| **Low exposure → low CAGR.** 25–40% time in market cannot compete with 78%-invested TQQQ on headline CAGR. | The leaderboard rewards CAGR. | The claim is a distinct, near-uncorrelated return stream; it must be judged on Sharpe and correlation, and the report must say so rather than chase CAGR by adding leverage. |
| **`clv ≥ 0` may be doing the work.** | Then the edge is a candle-pattern filter, not participation. | F8: if the event without the clv filter has no edge, retire rather than keep the filter. |

## 6. Why not the alternatives

- **Cross-sectional sector abnormal volume** (the literature's canonical HVRP
  form): better powered, but needs 1-minute sector history that does not exist
  locally, and `research/bt.py` marks equity on the panel's closes, so the brief's
  minute-mark requirement cannot be met. Documented in `provenance.md` §3.
- **Volume-expansion timing ladder**: tested pre-pause, no edge, placebo p = 0.30–0.35.
- **Volume-armed stop as the strategy**: overlay-only; without the regime the
  drawdown stays near 80%.

## 7. Reproduction (only after authorisation)

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\revisit\volume-orderflow\strategy.py --authorized
```

Without `--authorized` the script prints the paused notice, simulates nothing and
writes nothing.
