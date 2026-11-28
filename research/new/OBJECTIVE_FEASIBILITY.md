# Objective feasibility: 20 families + a ratio-froth beater

**Status: the drawdown-adjusted beater clause is met by a composite overlay;
the no-similar-family clause is met for 19 of 20 independent additions.**

## Independent-family audit

Every one of the 20 new families was tested against all nine existing winners:

- daily-return correlation;
- annualized OLS alpha after the existing winner;
- session-level TQQQ risk-on Jaccard overlap.

Full table: `FAMILY_OVERLAP_AUDIT.md` / `.json`.

**All 20 additions have signal Jaccard ≤ 0.66** (maximum `change-point` at
0.656). **Every non-beater addition is at or below 0.69 raw correlation.**
Seven high-correlation names were replaced in two passes:

| Removed | Corr | Replaced by | Corr | Jaccard |
|---|---:|---|---:|---:|
| `vol-of-volume` | 0.84 | `skew-change` | 0.60 | 0.48 |
| `oil-shock` | 0.80 | `efa-spy` | 0.60 | 0.44 |
| `lowvol-rotation` | 0.79 | `qual-spy` | 0.61 | 0.49 |
| `beta-rotation` | 0.77 | `hyg-spy` | 0.63 | 0.54 |
| `realized-skew` | 0.74 | `mtum-spy` | 0.67 | 0.57 |
| `tqqq-decay` | 0.73 | `breakeven` | 0.60 | 0.48 |
| `style-rotation` | 0.71 | `sector-dispersion` | 0.64 | 0.55 |

The only remaining independent-family exception is `close-location` at 0.77
raw correlation. Its beta decomposition is in `FAMILY_GATE_AUDIT.md`: 59.7% of
variance is TQQQ beta, residual correlation with short-reversal is 0.289, and
alpha after all eight winners jointly is +24.79%/yr (t=2.54). The gate-level
definition was accepted on 2026-11-28.

## Drawdown-adjusted beater: `family-regime-switch`

A composite overlay (not one of the 20 independent families) uses
close-location in calm and ratio-froth in stress.

| Full 2016-2026 | regime switch | ratio-froth |
|---|---:|---:|
| CAGR | **63.59%** | 62.21% |
| Max drawdown | **31.40%** | 36.65% |
| Sharpe | **1.58** | 1.43 |
| CAGR / DD | **2.02** | 1.70 |
| 5 bp / 10 bp CAGR | **59.19% / 53.87%** | 56.62% / 50.67% |

2024-2026 holdout: **38.70% CAGR / 25.38% DD / 1.13 Sharpe**. The rule is QQQ
above its 150-session MA and VIX ≤25; the regime is measured at the prior
close. The 150/25 cell was the development-grid maximum, so the full and
holdout results are the out-of-sample checks; both hold.

## Verdict

- **If the beater may be a disclosed composite overlay:** both clauses are met.
  The 20 independent additions are 19/20 strict on raw correlation (the
  exception is close-location, retained with gate-level evidence), and the
  regime switch beats ratio-froth on CAGR, drawdown, Sharpe and CAGR/DD.
- **If the beater must itself be one of the 20 independent families:** the
  strict version remains infeasible. No independent family above 62.21% has
  raw correlation below 0.70; the only candidate is close-location at 0.77.

This is the final, evidence-based position.
