# Relative Nasdaq flow dip (RN Flow) — rebuild of `letf-rebalance-flow`

**Status:** design / pre-registration. **Backtests paused** (2026-11-26).
No `result.json` has been generated. No development or holdout metrics exist
yet. This report is a skeleton plus a complete, testable specification.

**Original:** `research/agents2/letf-rebalance-flow` — a one-hour TQQQ overlay
on the round-1 165-day winner.
**This rebuild:** a standalone relative-value event strategy, no shared base.

---

## 1. Extracted idea

The original overlay's genuinely new claim was not the TQQQ trend base. It was
that the **end-of-day move contains temporary leveraged-ETF / options-hedging
pressure that partly reverses afterwards**. On risk-off days when QQQ rallied
more than 1.5% by 14:59, the old strategy bought TQQQ for the last hour and
exited before the close, because the overnight after those rallies was negative
on average.

That claim is kept. The implementation changes completely.

## 2. Why the old form could not stand alone

- The pure signal owned the position for only one hour on ~96 days in ten
  years. The standalone version returned about 7%/yr at 1 bp — far below TQQQ
  and the 165-day baseline.
- The default-long version that kept TQQQ most of the time returned more, but
  its daily-return correlation with the old base was 0.64–0.72, above the
  0.60 independence rule, and its drawdown was still ~76–82%.
- The old overlay only worked because a separate long-TQQQ book supplied the
  exposure and the overnight drift. That is exactly the shared base the revisit
  is meant to remove.

## 3. Hypothesis

**H1.** When QQQ underperforms SPY by a large standardized amount on day *t*,
part of that relative move is temporary Nasdaq-specific flow pressure
(leveraged-ETF rebalancing, options delta-hedging, index arbitrage), not
information. The relative move should partly reverse over the next few
sessions.

**H2.** Buying TQQQ at the next open after such a relative dip, holding three
sessions, and holding BIL otherwise produces a positive standalone return with
daily-return correlation below 0.60 to the old 165-day TQQQ/BIL baseline.

**H3.** The signal-day return exceeds the unconditional TQQQ return over the
same three-session windows, and a random-entry placebo with the same event
count, holding period and exposure does not reproduce it.

The economic prior is that the Nasdaq-100 complex has the largest leveraged-ETF
and options complex, so its end-of-day flow shock is disproportionately
Nasdaq-specific. SPY is the benchmark that measures "Nasdaq-specific" without
shorting. The signal is relative, so it is not an absolute market-direction
bet, and there is no 100–250-day trend gate.

## 4. Complete strategy specification

| Choice | Base rule |
|---|---|
| Traded universe | **TQQQ, BIL**. TQQQ gives the reversal enough amplitude; BIL is the risk-off asset. Both are markable on the existing 1-minute panel. |
| Signal universe | **QQQ daily adjusted close, SPY daily adjusted close**. SPY is never held; it is only the relative benchmark. |
| Signal | `rel_t = r_QQQ,t − r_SPY,t`; `sigma_t = std(rel, 20)` through *t−1*; `z_t = rel_t / sigma_t`. |
| Entry | If `z_t < −1.25` and flat, set 100% TQQQ at day *t*'s close; fill at day *t+1*'s open. |
| Holding | **3 sessions**: fill at *t+1* open; hold through the third session; sell at *t+4* open. |
| Sizing | 100% TQQQ on a signal, 100% BIL otherwise. No leverage beyond 100% TQQQ; no shorts. |
| Overlap | One position at a time; ignore new signals while holding. |
| Risk | Base: no stop. Pre-registered variant: exit if TQQQ closes 10% below the entry open, fill next open. |
| Costs | 1 bp headline; 5 bp and 10 bp reported. |
| Marks | 1-minute QQQ/TQQQ/BIL panel; daily targets broadcast to minutes with the same fill times. |

**Signal timing / fill timing.** The daily close of *t* is known at 16:00 ET.
The target is set at the last 1-minute bar of *t* and fills at the next
session's 09:30 open. The position is held through the last bar of the third
session and sold at the following open. This matches the daily engine's
next-open convention and has no look-ahead.

**Why this is not the old base.** No QQQ/TQQQ/SPY/NDX 100–250-day moving
average; no round-1 4% stop; no old `build_weights` or old weights; the
position is driven by a relative QQQ–SPY event, not a slow trend; TQQQ is held
only on event days, not as a permanent base.

## 5. Expected correlation and return

**Expected correlation with the old 165-day baseline: 0.25–0.45.** The old base
is long TQQQ on roughly 80% of sessions; this strategy is long TQQQ on roughly
10–15% of sessions and BIL otherwise. Relative-dip days are more likely in
risk-off or rotation periods, when the old base is often in BIL, which lowers
the overlap further. The TQQQ leg makes the correlation higher than a QQQ-only
version would be; a QQQ-risk-asset variant is a pre-registered lower-correlation
check.

**Expected return:** modest. On event days the strategy earns the TQQQ beta of
a three-session window plus any relative-reversal alpha. A plausible range is
**8–15% CAGR with 35–55% max drawdown** and Sharpe 0.4–0.6; a weak version
could be 4–8%. It is not expected to beat TQQQ buy-and-hold on CAGR. The value,
if any, is a distinct event-driven return stream with low correlation, not a
higher-return clone.

**Expected correlation with other rebuilds:** unknown until the lead computes
the matrix. The closest neighbour is `gap-capitulation-reversal` (buying after a
gap-down). This strategy uses a close-to-close *relative* underperformance, not
a gap, and holds three sessions; the lead should check the pair.

## 6. What would falsify it

1. **No predictive power:** the coefficient of the next 1/3-session TQQQ return
   on `z_t` is ≤ 0, or its HAC t-statistic is below 2.
2. **Too correlated:** development daily-return correlation with the 165-day
   baseline is ≥ 0.60.
3. **No excess return:** development CAGR is below BIL, or Sharpe < 0.3.
4. **Fragile event count:** fewer than 100 events and a bootstrap p-value above
   0.10; or the result is driven by a single sub-period (2020) or a single side
   (only up-market dips or only down-market dips).
5. **Costs kill it:** the edge disappears at 5 bp or 10 bp.
6. **Placebo:** random entries with the same event count, holding period and
   exposure produce a similar CAGR/Sharpe.
7. **Just beta:** the signal-day return is no better than unconditional TQQQ
   over the same three-session windows.
8. **Leverage artefact:** the QQQ-risk-asset version has no edge, i.e. the
   result is only the 3x beta of TQQQ, not a relative-value reversal.

## 7. Data

| Use | File | Notes |
|---|---|---|
| Traded/marked prices | `data/intraday-hf/QQQ-1m.parquet`, `TQQQ-1m.parquet`, `BIL-1m.parquet` | Adjusted, regular session, 2016-01-04 onward. |
| Signal closes | `data/intraday-hf/QQQ-1d-yahoo.parquet` | Daily adjusted close. |
| Signal closes | `data/round3/yahoo/SPY-1d-yahoo.parquet` | Daily adjusted close, 2015-01-02..2026-10-23. |
| 1-minute SPY | `data/cache/dukascopy/SPY/` | Only 2026-08-31 onward; **not usable** for the 2016–2023 development period. |

The missing 1-minute SPY history is why the signal uses the daily
close-to-close relative move rather than a last-hour QQQ-vs-SPY move. This is a
data constraint, not a choice to avoid the late-day question. If a 2016–2023
1-minute SPY history is added later, the same design can be refined to the last
30–60 minutes.

## 8. Preliminary evidence (old strategy; not a test of this rebuild)

- The old 96 risk-off late-rally events: TQQQ 15:00–15:59 **+64 bp** mean
  (median +48 bp, hit 67%, t = 2.49); the following overnight **−90 bp** mean
  (median −19 bp, hit 46%, t = −1.85).
- Overnight reversal regression on the absolute last-hour move, controlling
  for the day's move: coefficient **−2,886 bp per unit** (HAC t = −2.27),
  strongest in 2023–26 (t = −2.95). This is the closest own evidence that
  end-of-day flow reverses, but it is *absolute* QQQ/TQQQ, not the QQQ–SPY
  spread used here.
- Old standalone last-hour versions: 2–14% CAGR depending on threshold, with
  0.02–0.29 correlation to the old base — low correlation but too little
  return.
- Old default-long exit versions: 40–49% CAGR, but 0.64–0.72 correlation and
  76–82% drawdown — a high-beta variant, not an independent edge.
- Old multi-day reversal checks (absolute down-day signal, TQQQ, 3–5 session
  hold): 16.8–17.2% CAGR, 51–65% drawdown, 0.27–0.49 correlation. These are
  the reason a multi-session hold is the prior for this rebuild, not a one-hour
  trade.

**These are motivations, not results.** The relative QQQ–SPY signal has not
been tested.

## 9. Pre-registered evaluation plan (not run)

- Development only: **2016-01-04 → 2023-12-29**. Holdout 2024–2026 is not
  inspected.
- 1 bp headline; 5 bp and 10 bp.
- Neighbourhood: z threshold {−1.00, −1.25, −1.50}; hold {1, 2, 3, 5} sessions;
  choose from a plateau, not the peak.
- Sub-periods: 2016–19, 2020–21, 2022–23.
- Placebo: random entry days matched on count and holding period; 1,000 draws.
- Event count and bootstrap p-value if <100 events.
- Benchmarks: TQQQ, QQQ, SPY buy-and-hold; original strategy's `result.json`.
- Correlations: 165-day baseline, plus the lead's cross-rebuild matrix.
- QQQ-risk-asset variant (no leverage) as the "is it just beta?" test.
- A ±1-session execution delay (fill at *t+2* open) as a look-ahead/robustness
  check.

## 10. Results

**TBD — backtests paused. Do not fill these with expectations.**

| Window | 1 bp CAGR / DD | 5 bp CAGR / DD | 10 bp CAGR / DD |
|---|---:|---:|---:|
| Dev 2016-01-04..2023-12-29 | TBD | TBD | TBD |
| 10y (overlaps holdout) | TBD | TBD | TBD |
| 5y (overlaps holdout) | TBD | TBD | TBD |

Correlation vs 165-day baseline: **TBD** (expected 0.25–0.45).
Event count: **TBD**.

## 11. Limitations

1. **No 1-minute SPY for dev.** The signal is daily, not last-hour. The
   "late-day" part is the close-to-close relative move, which includes the
   close; it is not the same as a 15:00–15:58 signal.
2. **The signal is a proxy for flow, not a direct measurement of LETF
   rebalancing.** We do not observe LETF creations/redemptions or underlying
   volume. The relative QQQ–SPY move is an inference.
3. **TQQQ adds beta.** Even on event days, the strategy carries 3x Nasdaq beta;
   the QQQ variant is the clean test of whether the relative reversal survives
   without leverage.
4. **The old evidence is absolute, not relative.** The overnight reversal
   regression used QQQ/TQQQ absolute returns. The relative QQQ–SPY version may
   be weaker if the flow is market-wide rather than Nasdaq-specific.
5. **Parameter priors are in-sample.** z = −1.25 and hold = 3 come from the old
   event study and standard practice, not from a pre-2026 independent sample.
   The plateau and placebo tests are mandatory.
6. **No short leg.** The design is long-only because the engine is long-only;
   the "relative value" is implemented by choosing TQQQ vs BIL, not by shorting
   SPY. This leaves market beta in the signal days.

## 12. References

See `provenance.md` for the full table. Key sources:

- Barbon et al. (2022), *Liquidity Provision to Leveraged ETFs and Equity
  Options Rebalancing Flows* — LETF/option rebalancing price pressure at the
  end of the day.
- Shum, Hejazi, Haryanto & Rodier (2016), *Intraday Share Price Volatility and
  Leveraged ETF Rebalancing*, Review of Finance 20(6):2379–2409.
- Baltussen, Da & Soebhag (2025); Vidovich & Zerjal (2026), *The End-of-Day
  Reversal After 2019* — the reversal side.
- Gao, Han, Li & Zhou (2018), *Market intraday momentum*, JFE 129(2):394–414 —
  the opposite (continuation) hypothesis.
- Lenkey (2024), *The market impact of leveraged ETFs: A survey of the
  literature*, QFE 8(4):815–840 — the economic-significance caution.
- Ivanov & Lenkey (2018), *Do leveraged ETFs really amplify late-day returns
  and volatility?*, JFM 41:36–56 — the skeptical test.
