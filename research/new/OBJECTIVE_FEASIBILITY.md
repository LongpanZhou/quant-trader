# Objective feasibility: 20 non-overlapping families + ratio-froth beater

**Status: strict no-similar-family clause met for 19 of 20; the only exception
is the ratio-froth beater itself.**

## Audit method

Every one of the 20 new families was tested against all nine existing winners:

- daily-return correlation;
- annualized OLS alpha after the existing winner;
- session-level TQQQ risk-on Jaccard overlap.

Full table: `FAMILY_OVERLAP_AUDIT.md` / `.json`.

## Final audit

**All 20 additions have signal Jaccard ≤ 0.66** (maximum `change-point` at
0.656). **Every non-beater addition has raw correlation ≤ 0.69.** Seven
high-correlation names were replaced in two passes:

| Removed | Corr | Replaced by | Corr | Jaccard |
|---|---:|---|---:|---:|
| `vol-of-volume` | 0.84 | `skew-change` | 0.60 | 0.48 |
| `oil-shock` | 0.80 | `efa-spy` | 0.60 | 0.44 |
| `lowvol-rotation` | 0.79 | `qual-spy` | 0.61 | 0.49 |
| `beta-rotation` | 0.77 | `hyg-spy` | 0.63 | 0.54 |
| `realized-skew` | 0.74 | `mtum-spy` | 0.674 | 0.573 |
| `tqqq-decay` | 0.73 | `breakeven` | 0.602 | 0.481 |
| `style-rotation` | 0.71 | `sector-dispersion` | 0.643 | 0.551 |

The replacement gates are CBOE SKEW tail-risk pricing, EFA/SPY developed-market
relative, QUAL/SPY quality, HYG/SPY credit-equity, MTUM/SPY momentum, TIP/IEF
inflation compensation, and cross-sectional sector dispersion.

## The single exception: the beater

`close-location` is the only remaining name above 0.70 raw correlation:

| Statistic | Value |
|---|---:|
| Full CAGR | **66.23%** |
| Full DD / Sharpe | 62.76% / 1.26 |
| Raw correlation | **0.77** vs `family-short-reversal` |
| Signal Jaccard | **0.47** |
| Residual alpha after short-reversal | **+37.82%/yr, t=2.80** |
| 5 bp / 10 bp CAGR | **62.26% / 57.43%** vs ratio-froth 56.62% / 50.67% |

No other addition above 0.70 remains. No genuinely low-correlation family
clears ratio-froth's 62.21%: crypto 46.50%, rates 38.80%, EFA/SPY 35.59%,
QUAL/SPY 35.03%. Returns above 62% require high TQQQ beta, which mechanically
raises raw correlation with the existing high-beta winners even when the entry
gate differs.

## Verdict

- **Strict raw-correlation view:** 19 of 20 additions are ≤0.69. The only
  exception is the required beater, which cannot be replaced without removing
  the only strategy that beats ratio-froth.
- **Gate-level view:** close-location's 0.47 Jaccard and +37.8%/yr alpha
  (t=2.80) support a distinct close-location-value gate; the raw correlation
  is a TQQQ-beta artifact.

This is an evidence-based trade-off, not a claim that a strictly uncorrelated
>62.21% strategy exists.
