# Gold-miner stress — report

**Slug:** `family-gold-miner-stress`  
**Dev:** 23.43% CAGR / 65.72% DD / 0.67 Sharpe.  
**Full:** 24.04% CAGR / 65.72% DD / 0.68 Sharpe; 429 full fills.  
**2024-2026 holdout:** 25.90% CAGR / 37.69% DD / 0.71 Sharpe.

## Rules

When the 20-session GDX/GLD change is in its bottom half, buy TQQQ contrarian;
otherwise BIL. The signal is the miner/metal ratio, not the gold price.

## Why it is distinct

Maximum signal Jaccard against the nine existing winners is 0.537; maximum raw
correlation is 0.693. It is a precious-metals stress gate, not a sector
rotation. The reverse direction (miners leading) returned 12.25% with an
88.69% drawdown.

## Caveats

- Full CAGR is below the TQQQ bar; this is an active research family, not a
  winner.
- The 65.72% drawdown is high; the strategy is a diversifier, not a core
  holding.
- The 2024-2026 holdout is reported exactly as run; it is not used to tune the
  parameters.
- External daily series are committed under `data/external/`.
