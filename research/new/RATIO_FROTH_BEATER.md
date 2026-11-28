# New-family result vs `ratio-froth`

**Winner: `family-close-location`** — a long-only TQQQ strategy that buys after
a close in the bottom tenth of the QQQ intraday range and holds five sessions.
No synthetic short, no leverage beyond TQQQ, 653 full-window fills.

| Full 2016-2026, daily-close | `family-close-location` | `ratio-froth` |
|---|---:|---:|
| CAGR | **66.23%** | 62.21% |
| Max drawdown | 65.98% | **36.65%** |
| Sharpe | 1.26 | **1.43** |
| Fills | 653 | 619 |

**It beats `ratio-froth` on CAGR, not on drawdown or Sharpe.** That is the
honest claim.

## Cost ladder (same full window, 1-minute marks)

| Cost | `family-close-location` | `ratio-froth` |
|---:|---:|---:|
| 1 bp | **66.23%** | 62.21% |
| 5 bp | **62.26%** | 56.62% |
| 10 bp | **57.43%** | 50.67% |

The CAGR lead survives 5 and 10 bp. The strategy's full-window holdout is
2024-01-02..2026-10-23: **34.24% CAGR / 51.00% DD / 0.90 Sharpe**, so it is
not a holdout blow-up.

## Verification

- 8/8 pre-registered grid cells above the TQQQ development bar.
- Pre-cut weight difference at 2020-03-12 11:07: **0.0**.
- Correlation with the existing winners: 0.425 (ratio-froth) to 0.789
  (family-short-reversal); TQQQ 0.789.
- Full holdout and curve:
  `research/new/family-close-location/holdout.json`,
  `research/new/curves/family-close-location.json`.
- Development report: `research/new/family-close-location/report.md`.

## Second candidate (not the headline)

`family-tail-hedge-overlay` also has a higher full CAGR than `ratio-froth`
(**66.38%** at 1 bp), but it uses a synthetic constant-notional inverse TQQQ
sleeve, its 10 bp CAGR falls to **40.42%**, and its correlation with
`vol-scaled-crash-stop` is 0.85. It is a qualified, cost-fragile tail-hedge
result, not the clean long-only winner.
