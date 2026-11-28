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
`change-point` at 0.656. The four highest raw-correlation names were replaced
on 2026-11-28:

| Removed | Corr | Replaced by | Corr | Jaccard |
|---|---:|---|---:|---:|
| `vol-of-volume` | 0.84 | `skew-change` | 0.60 | 0.48 |
| `oil-shock` | 0.80 | `efa-spy` | 0.60 | 0.44 |
| `lowvol-rotation` | 0.79 | `qual-spy` | 0.61 | 0.49 |
| `beta-rotation` | 0.77 | `hyg-spy` | 0.63 | 0.54 |

The replacement gates are CBOE SKEW tail-risk pricing, EFA/SPY developed-market
relative, QUAL/SPY quality-factor leadership, and HYG/SPY credit-equity risk
appetite. Pairwise correlations among them are 0.38–0.61; pairwise Jaccard is
0.27–0.40.

The remaining raw correlations above 0.70 are all above-bar winners with
significant residual alpha:

| Family | Max corr | Against | Alpha / yr | Alpha t | Jaccard |
|---|---:|---|---:|---:|---:|
| `close-location` | 0.77 | short-reversal | +37.82% | 2.80 | 0.47 |
| `realized-skew` | 0.74 | relative-value | +22.15% | 1.77 | 0.56 |
| `tqqq-decay` | 0.73 | rebalance-flow | +24.95% | 2.39 | 0.53 |
| `style-rotation` | 0.71 | relative-value | +24.39% | 1.80 | 0.61 |

## The ratio-froth conflict

The only full-window candidate above ratio-froth's **62.21%** CAGR is
`close-location` at **66.23%**. Its Jaccard is **0.47**, its residual alpha is
**+37.8%/yr at t=2.80**, and its raw correlation is 0.77.

Every genuinely low-correlation external family tops out lower: crypto 46.50%,
rates 38.80%, style 37.98%, EFA/SPY 35.59%, QUAL/SPY 35.03%. The removed oil
family reached 46.95% but had 0.80 raw correlation. Returns above 62% require
high TQQQ beta; that mechanically raises raw correlation with the existing
high-beta winners even when the entry gate differs.

## Verdict

- **Gate-level view:** all 20 have Jaccard ≤0.66; the four highest raw
  correlations were replaced. All remaining >0.70 names have positive residual
  alpha (t≥1.77) and Jaccard ≤0.61. The objective is met under this definition.
- **Strict raw-return view:** close-location's 0.77 correlation fails a
  zero-correlation test. No strategy above 62.21% has lower raw correlation.

This is an evidence-based trade-off, not a claim that a strictly uncorrelated
>62.21% strategy exists.
