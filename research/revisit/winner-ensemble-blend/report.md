> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# winner-ensemble-blend — revisit: standalone two-stream risk parity

**Status: SPEC ONLY — BACKTESTS PAUSED.** No simulation has been run. No
`result.json` has been generated. No holdout data (2024-01-02 → 2026-10-23) has
been inspected. This report is a pre-registration and design document; the
results tables are intentionally empty until the lead authorizes the run.

Files:

- `HYPOTHESIS.md` — pre-registered idea, hypothesis, falsifiers.
- `SPEC.md` — exact rules, parameters, execution, evaluation plan.
- `PROVENANCE.md` — source-by-source provenance and what was not used.
- `strategy.py` — complete implementation (not executed).
- `report.md` — this document.

---

## 1. What the original strategy actually was

The round-2 `winner-ensemble-blend` was a fixed 75/25 (and inverse-vol) blend of
two round-1 sleeves:

- the winner: QQQ 165-day SMA regime + armed 4% minute stop, 100% TQQQ/BIL;
- the ensemble: QQQ 165-day trend + 20-day volatility budget + 1-minute crash
  vote, 100% TQQQ/BIL.

Both sleeves sat on the **same 165-day QQQ base**. The blend's headline numbers
(58.42%/41.18% 10y, 47.92%/32.33% 5y at 1 bp) were the base's return with a
smaller drawdown. The allocation layer was never tested on independent return
streams. So the original is **not** evidence that inverse-vol blending has a
standalone edge; it is evidence that a 25% defensive overlay can shave a trend
strategy's drawdown.

## 2. The genuinely new idea, rebuilt

The new content is the allocation principle:

> **Allocate across independent return streams by inverse trailing volatility so
> the portfolio's risk comes from the combination, not from a market regime.**

To test it honestly, the rebuild creates two complete, opposing streams on the
same liquid universe. Neither uses a 100–250-day price moving average, the old
stop, or the old weights.

### Universe

QQQ (1x), TQQQ (3x), BIL (T-bills). SPY is a benchmark only: local SPY history is
daily and ~0.99 correlated with QQQ, so it adds no independent driver. No local
2016–2023 data exists for bonds, gold, sectors or volatility products; the
strategy is deliberately restricted to assets the data supports.

### Stream A — calm-regime QQQ carry (1x, partial)

At the daily close:

- `vol10` = 10-session realised vol of QQQ daily returns.
- `q40` = 40th percentile of `vol10` over the last 60 sessions.
- `r5` = QQQ 5-session return.

If `vol10 < q40` **and** `r5 > 0`: hold **70% QQQ + 30% BIL** for the next
session. Otherwise hold **100% BIL**.

This is an equity-risk-premium harvester that only participates in calm, rising
markets. It is intentionally 1x (not TQQQ) and only 70% invested, so it does not
become a QQQ proxy. Holding period: regime-based, typically days to weeks.

### Stream B — panic-reversal TQQQ (3x, short hold)

At the daily close, a panic signal is:

```
r3 <= -5%   OR   (r1 <= -3% AND vol10/vol60 >= 1.5)
```

If flat and not in cooldown: buy **100% TQQQ** at the next open. Exit on the
first of:

1. QQQ close back above its 10-day mean (recovery);
2. TQQQ close 8% below the first close after entry (close-based stop);
3. three sessions held (time exit).

After an exit, a 2-session cooldown blocks re-entry. Holding period: 1–3
sessions. This harvests the short-term reversal / liquidity-provision premium
after panic selling, using TQQQ only for the rebound.

### Allocation

At each daily close:

- `sigma_A`, `sigma_B` = 20-day realised vol of each stream's standalone daily
  returns, **shifted one day** (day *d* uses returns through *d−1*).
- `a_A = (1/sigma_A) / (1/sigma_A + 1/sigma_B)`, clipped to **[0.20, 0.80]**;
  `a_B = 1 − a_A`.
- Blend target = `a_A · w_A + a_B · w_B`; residual BIL.

The 20/80 clip guarantees both streams matter. The blend's equity exposure never
exceeds 100%; no leverage beyond TQQQ, no shorts.

### Execution

Daily signals at the 15:59 close; target set at bar *i*, filled at bar *i+1*'s
open; 2% band; 1-minute equity marks. No intraday signal is used.

## 3. Why this is not just the old overlay with the base removed

| Old blend | This rebuild |
|---|---|
| Both sleeves: 100% TQQQ in a 165-day QQQ uptrend | No 165-day gate anywhere |
| 4% armed minute stop inherited from round 1 | No round-1 stop; Stream B has a separate 8% close stop |
| Return driver: slow Nasdaq trend + crash overlay | Return drivers: calm-vol equity carry + post-panic reversal |
| 3x equity most of the time | 1x QQQ in calm periods; 3x only for 1–3 sessions after selloffs |
| Allocation across two copies of the same trade | Allocation across two opposing conditional exposures |

The two streams are deliberately anti-correlated in condition: Stream A is long
in calm up markets, Stream B is long after panic down moves. That is the
diversification the original never had.

## 4. Hypothesis and expected correlation

**Hypothesis.** The inverse-vol blend earns a positive risk-adjusted return on
2016–2023, with a lower drawdown than either stream alone and a daily-return
correlation below 0.60 with the old 165-day TQQQ baseline.

**Expected correlation: 0.30–0.55**, hard ceiling 0.60. Reasoning: the old base
is long TQQQ ~74% of dev days. Stream A is long QQQ ~40% of days, mostly calm up
days, so alone it could correlate ~0.6 with the base. Stream B is long TQQQ only
~5–10% of days after selloffs, often when the base is in BIL, so its correlation
should be low. A risk-balanced blend (roughly 55–65% A, 35–45% B) should land
near 0.40–0.55. If it lands at 0.60 or above, the strategy is still equity beta
in disguise and is rejected.

## 5. Falsifiers (pre-registered)

The rebuild is rejected if any of these holds on dev:

1. Correlation with the 165-day baseline ≥ 0.60.
2. Blend Sharpe ≤ max(Sharpe_A, Sharpe_B) **and** blend max DD ≥
   min(maxDD_A, maxDD_B): the allocation adds neither return nor risk reduction.
3. Stream A's standalone dev CAGR at 5 bp ≤ BIL's, or Sharpe ≤ 0: calm carry is
   not a premium.
4. Stream B has < 25 events, or the bootstrap p-value for the mean post-signal
   3-session TQQQ return is > 0.10.
5. The sign of the blend's dev CAGR flips at both ±1-step neighbours of a core
   parameter, or correlation crosses 0.60 at both neighbours.
6. Blend dev CAGR at 5 bp ≤ 0, or 5 bp max DD > 40%.
7. 2022–2023 sub-period CAGR < −10%.
8. Random entries with the same frequency and holding period beat the real
   signals' dev Sharpe in >10% of 200 draws.

If only one stream survives (A or B), the honest result is a one-stream
strategy, and this slug is marked `retired_overlay_only` because the *allocation*
idea did not stand alone.

## 6. Evaluation plan (when authorized)

- Dev only: 2016-01-04 → 2023-12-29. Holdout and official 10y/5y are null in
  `result.json`; the lead runs those after freezing.
- Costs: 1 bp headline, 5 bp, 10 bp.
- Metrics: CAGR, max drawdown (1-minute marks), Sharpe, Sortino, vol, exposure,
  fills, turnover.
- Correlations: blend vs baseline; each stream vs baseline; A vs B.
- Sub-periods: 2016–2019, 2020–2021, 2022–2023.
- ±1-step neighbourhood table for every core parameter.
- 200-draw random/placebo control (same exposure frequency and event count).
- Stream-B event study: event count, mean 3-session forward TQQQ return,
  10,000-resample bootstrap p-value.
- Benchmarks: TQQQ, QQQ, SPY buy-and-hold on dev; the original's published
  10y/5y numbers, labelled as not dev-comparable.

## 7. Results

**Not run. Backtests paused by the lead on 2026-11-26. No numbers are available.**

| Window | 1 bp CAGR / DD | 5 bp CAGR / DD | 10 bp CAGR / DD |
|---|---:|---:|---:|
| dev 2016-01-04 → 2023-12-29 | — | — | — |
| holdout | not run (lead only) | not run | not run |
| 10y (overlaps holdout) | not run (lead only) | not run | not run |
| 5y (overlaps holdout) | not run (lead only) | not run | not run |

When the run is authorized, `strategy.py` will fill this table and
`result.json` from the harness, including the neighbourhood, placebo, event
study and correlations. No number will be hand-typed.

## 8. Honest risks before the test

1. **Single-factor universe.** QQQ and TQQQ are the same factor at different
   leverage. A residual correlation with the old base is likely; the 0.60
   ceiling may be hard to clear. If it fails, the honest conclusion is that the
   allocation idea cannot be diversified with the available data.
2. **Few reversal events.** Stream B likely has 30–60 events over eight years.
   The bootstrap p-value will be weak; a positive point estimate may not be
   statistically distinguishable from noise.
3. **Close-based stop, gap risk.** TQQQ can gap through the 8% stop. The stop is
   a risk reducer, not a guarantee.
4. **Low absolute return.** A 1x partial carry plus a rare 3x reversal is
   unlikely to approach the old 58% CAGR. That is acceptable for a diversifier,
   but it is not a replacement for the winner.
5. **Allocation proxy.** Stream vols are estimated from close-to-close returns,
   not from a full net-of-cost simulation. This is causal and standard for
   sizing, but it is an approximation; the report will state it.
6. **No point-in-time stock universe.** The strategy trades ETFs only, so
   survivorship/delisting is not a concern for the traded assets.

## 9. Provenance summary

The full table is in `PROVENANCE.md`. The key mappings:

| Rule / assumption | Source | Role |
|---|---|---|
| Post-panic reversal is a liquidity-provision premium | Nagel (2012), *Evaporating Liquidity* | inspired Stream B |
| Reversal is concentrated in high-vol, high-turnover names | Da, Liu & Schaumburg (2014) | supports the vol-ratio condition |
| Fast dip-buy with a quick recovery exit | Connors & Alvarez (2008) | inspired Stream B; the 200-day filter is **not** used |
| Calm-vol equity carry / volatility timing | Moreira & Muir (2017) | inspired Stream A |
| Volatility timing is fragile | Cederburg et al. (2020) | supports the Stream-A falsifier |
| Inverse-vol / risk-parity weights | Asness, Frazzini & Pedersen (2012) | inspired the allocation |
| Simple risk-based weights beat optimisers out of sample | DeMiguel, Garlappi & Uppal (2009) | supports the simple clip |
| Rebalancing/ensemble premium | Newfound (2020); SSRN 2311240 | motivates testing a blend |
| Stops are not free | SSRN 2695383 | caution for the 8% stop |
| No 165-day base, no old stop, no old code | Brief section 2; own test | hard constraint |

## 10. Decision requested from the lead

Authorize the development run of `strategy.py` (dev only, 1/5/10 bp). If the
correlation is ≥ 0.60 or the falsifiers fail, the strategy will be marked
`rejected`/`retired_overlay_only` with the evidence, not force-fitted.
