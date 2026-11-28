# Objective feasibility: 20 non-overlapping families + ratio-froth beater

**Status: gate-level objective met; strict raw-correlation definition not met.**

## Audit method

Every one of the 20 new families was tested against all nine existing winners:

- daily-return correlation;
- annualized OLS alpha after the existing winner;
- session-level TQQQ risk-on Jaccard overlap.

Full table: `FAMILY_OVERLAP_AUDIT.md` / `.json`.

## Final audit

**All 20 additions have signal Jaccard ≤ 0.66.** The maximum is
`change-point` at 0.66; 19 are ≤ 0.61. The three former high-overlap names
(policy-liquidity, VIX term structure, credit spread) were replaced by
homebuilder, financials and retail rotation.

| Statistic | Worst remaining |
|---|---:|
| Signal Jaccard | **0.66** (`change-point`) |
| Raw correlation | **0.84** (`vol-of-volume` vs relative-value) |
| Raw correlation of the ratio beater | **0.77** (`close-location` vs short-reversal) |
| Close-location Jaccard | **0.47** |
| Close-location residual alpha | **+37.8%/yr, t=2.80** |

## The ratio-froth conflict

The only full-window candidates above ratio-froth's **62.21%** CAGR are:

- `close-location`: **66.23%**, Jaccard **0.47**, alpha +37.8%/yr, t=2.80,
  raw correlation 0.77;
- the removed `tail-hedge-overlay`: 66.38%, raw correlation 0.85 with
  `vol-scaled-crash-stop`.

Every independent external family tops out lower: oil 46.95%, crypto 46.50%,
rates 38.80%, style 37.98%. Returns above 62% require high TQQQ beta; that
mechanically raises raw correlation with the existing high-beta winners even
when the entry gate differs.

## Verdict

- **Gate-level view:** all 20 have Jaccard ≤0.66, and close-location's 0.47
  signal overlap plus +37.8%/yr residual alpha supports a distinct CLV gate.
  The objective is met under this definition.
- **Strict raw-return view:** close-location's 0.77 correlation fails a
  zero-correlation test. No strategy above 62.21% has lower raw correlation.

This is an evidence-based trade-off, not a claim that a strictly
uncorrelated >62.21% strategy exists.
