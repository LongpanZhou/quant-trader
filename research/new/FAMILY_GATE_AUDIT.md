# Family-gate audit

The test is residual alpha after the overlapping winner, not raw correlation.
A strategy keeps its family status only if its gate adds return beyond the
existing winner. Daily full-window returns; OLS with a constant and the
overlapping winner return.

| Candidate | Overlapping winner | Alpha / yr | Alpha t | Beta | Correlation | Decision |
|---|---|---:|---:|---:|---:|---|
| `family-close-location` | `family-short-reversal` | **+25.44%** | **2.59** | 0.66 | 0.77 | **keep** — distinct CLV gate |
| `family-tail-hedge-overlay` | `vol-scaled-crash-stop` | +12.15% | 1.54 | 1.01 | 0.84 | replace |
| `family-dollar-regime` | `relative-value-tqqq` | +4.58% | 0.51 | 1.02 | 0.86 | replace |
| `family-gold-safe-haven` | `relative-value-tqqq` | +4.31% | 0.46 | 1.10 | 0.87 | replace |

## What was replaced

Ten calendar/session/intraday/risk-sizing overlaps were replaced by external
families. Tail-hedge, dollar and gold were then replaced by:

- `family-style-rotation` — IWF/IWD growth-vs-value; full 37.98% CAGR.
- `family-yen-carry` — USDJPY carry/safe-haven; full 18.21%.
- `family-lowvol-rotation` — USMV/SPY defensive style; full 13.31%.

## Final 20 gates

Kept: close-location, policy-liquidity, volume-skew, vol-of-volume,
change-point, Hurst, TQQQ-decay, realized-skew, beta-rotation.

External: VIX term structure, credit spread, sector rotation, breadth,
crypto risk appetite, rates volatility, energy rotation, oil shock, style
rotation, yen carry, low-vol rotation.

`close-location` is the only addition that still overlaps an existing winner
on raw correlation, but its residual alpha is significant. It is also the
ratio-froth CAGR beater.
