# Objective feasibility: 20 non-overlapping families + ratio-froth beater

**Status: not fully achievable with the available data under a strict
definition of “non-overlapping.”**

## Audit method

For every one of the 20 new families against all nine existing winners:

- daily-return correlation;
- OLS alpha after the existing winner (annualized, Newey-free OLS t);
- session-level TQQQ risk-on Jaccard overlap, where the weight builder runs.

Full table: `FAMILY_OVERLAP_AUDIT.md` / `.json`.

## Key results

| New | Max corr | Overlap | Annual alpha | Alpha t | Jaccard |
|---|---:|---|---:|---:|---:|
| `close-location` | 0.77 | short-reversal | **+37.82%** | **2.80** | **0.47** |
| `policy-liquidity` | 0.86 | relative-value | +25.92% | 1.84 | **0.87** |
| `vix-term-structure` | 0.75 | rebalance-flow | +20.15% | 1.57 | **0.81** |
| `credit-spread` | 0.76 | rebalance-flow | +17.78% | 1.35 | **0.73** |
| `vol-of-volume` | 0.84 | relative-value | +21.74% | 1.94 | 0.59 |
| `oil-shock` | 0.80 | relative-value | +21.01% | 1.47 | 0.66 |
| `beta-rotation` | 0.77 | rebalance-flow | +16.08% | 1.62 | 0.27 |
| `lowvol-rotation` | 0.79 | short-reversal | −14.69% | −1.43 | 0.52 |

Seventeen of 20 have signal Jaccard below 0.70. Three (`policy-liquidity`,
`vix-term-structure`, `credit-spread`) exceed it and are flagged as overlapping
despite being external-data strategies.

## The ratio-froth conflict

The only full-window candidates above ratio-froth's **62.21%** CAGR are:

- `close-location`: **66.23%**, Jaccard **0.47**, alpha +37.8%/yr, t=2.80,
  raw correlation 0.77;
- the removed `tail-hedge-overlay`: 66.38%, raw correlation 0.85 with
  `vol-scaled-crash-stop`.

Every independent external family tops out lower: oil 46.95%, crypto 46.50%,
rates 38.80%, style 37.98%, VIX 38.68%. Returns above 62% require high TQQQ
beta; that mechanically raises raw correlation with the existing high-beta
winners even when the entry gate differs.

## Verdict

- **Gate-level view:** `close-location` has 47% signal overlap, a distinct CLV
  entry rule, and significant residual alpha. Under a gate-overlap definition
  (Jaccard < 0.50 plus positive alpha), it is a valid independent beater.
- **Raw-return view:** its 0.77 correlation fails a strict “no similar family”
  test. No alternative above 62.21% has lower raw correlation.
- Therefore, **20 strictly non-overlapping families plus a ratio-froth beater
  cannot both be satisfied with the current data.** Replacing close-location
  removes the only beater; keeping it leaves one raw-correlation overlap.

This is an evidence-based infeasibility result, not a claim that the objective
is complete.
