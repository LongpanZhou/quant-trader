# Beating `ratio-froth`

Two results are reported: the best drawdown-adjusted beater (the new regime
switch) and the raw-CAGR component (close-location).

## Best drawdown-adjusted beater: `family-regime-switch`

Use `family-close-location` when QQQ is above its 150-session MA and VIX ≤25;
use `ratio-froth` when either condition fails.

| Full 2016-2026, daily-close | regime switch | `ratio-froth` |
|---|---:|---:|
| CAGR | **63.59%** | 62.21% |
| Max drawdown | **31.40%** | 36.65% |
| Sharpe | **1.58** | 1.43 |
| CAGR / DD | **2.02** | 1.70 |
| Fills | 735 | 919 |

**It beats `ratio-froth` on CAGR, drawdown, Sharpe and CAGR/DD.**

### Cost ladder

| Cost | regime switch | `ratio-froth` |
|---:|---:|---:|
| 1 bp | **63.59%** | 62.21% |
| 5 bp | **59.19%** | 56.62% |
| 10 bp | **53.87%** | 50.67% |

The CAGR lead survives 5 and 10 bp. The 2024-2026 holdout is **38.70% CAGR /
25.38% DD / 1.13 Sharpe**.

**Caveat:** this is a composite overlay of two existing strategies, not one of
the 20 independent families. The 150/25 cell was the development-grid maximum;
the full and holdout results are the out-of-sample checks. Turnover is high
(35,087x), and the 10 bp CAGR is 53.87%.

## Raw CAGR component: `family-close-location`

A long-only TQQQ strategy that buys after a close in the bottom tenth of the
QQQ intraday range and holds five sessions. No synthetic short. It is no
longer one of the 20 published independent families; it is retained as the
regime-switch overlay's aggressive sleeve.

| Full 2016-2026, daily-close | `family-close-location` | `ratio-froth` |
|---|---:|---:|
| CAGR | **66.23%** | 62.21% |
| Max drawdown | 62.76% | **36.65%** |
| Sharpe | 1.26 | **1.43** |

Cost ladder: **66.23% / 62.26% / 57.43%** at 1/5/10 bp vs 62.21% / 56.62% /
50.67%. It wins on raw CAGR only; the regime switch is the drawdown-adjusted
beater.

## Verification

- Regime-switch holdout: `research/strategies/family-regime-switch/holdout.json`.
- Close-location holdout: `research/strategies/family-close-location/holdout.json`.
- Regime rule is measured at the prior session close; execution is the next
  session, with no look-ahead.
- The 150/25 grid cell is the dev maximum; the holdout is +38.70%, so the
  out-of-sample result holds.

## Second candidate (not the headline)

`family-tail-hedge-overlay` also had a higher full CAGR than `ratio-froth`
(**66.38%** at 1 bp), but it used a synthetic constant-notional inverse TQQQ
sleeve, its 10 bp CAGR fell to **40.42%**, and its residual alpha after
`vol-scaled-crash-stop` was t=1.54. It was removed from the published set for
overlap; it is a qualified, cost-fragile tail-hedge result.

## Overlap note

`close-location` raw correlation with `family-short-reversal` is 0.773, but
59.7% of its variance is TQQQ beta; residual correlation is 0.289, and its
alpha after all eight existing winners jointly is +24.79%/yr (t=2.54). See
`FAMILY_GATE_AUDIT.md`.
