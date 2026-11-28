# Provenance — Trend/VIX regime switch

**No external paper is linked.** This overlay was constructed manually inside
this project from two existing strategies.

| Rule / component | Source | Role | Evidence |
|---|---|---|---|
| Calm sleeve: buy TQQQ after a close in the bottom tenth of the QQQ range, hold five sessions | `family-close-location` | internal component | verified strategy record in `research/strategies/family-close-location` |
| Stress sleeve: 165-day trend + volatility throttle | `ratio-froth` | internal component | verified strategy record in `research/strategies/ratio-froth` |
| Calm/stress switch: QQQ > 150-session MA and VIX ≤25 | own 3×3 grid | own test | 150/25 was the development-grid maximum; see report |
| Costs and execution: next-open fills, 2% band, 1 bp headline | shared research harness | internal infrastructure | benchmarked at 5/10 bp in the report |

The full-window edge is concentrated in 2016-2024. In 2025 the overlay returned
20.49% versus ratio-froth 83.35%; 2026 YTD 0.79% versus 29.83%; trailing one
year 13.67% versus 37.35%. It is a research overlay, not a current live edge.
