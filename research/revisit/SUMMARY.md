# Revisit summary — published freeze

Uniform window **2016-01-04 → 2026-10-23**, next-open fills, 2% band,
1 bp costs, daily-close marks. `Dev` is the frozen 2016-2023 development
result (1-minute marks; pre-tune where the post-freeze tune changed the
strategy). `Post` is the post-tune variant when it differs; the website
keeps the pre-tune curve, not the variant. See
`WHY_UNDERPERFORM.md` §3 and `audit/validity_A.md` … `validity_D.md`.

| Strategy | Idea | Dev CAGR / DD | Post-tune dev | Full CAGR / DD / Sharpe | Freeze |
|---|---|---:|---:|---:|---|
| `ratio-froth` | The original 165-day base + 4% stop + TQQQ/QQQ ratio overlay. | — | — | **62.21%** / 36.65% / 1.43 | original |
| `vol-scaled-crash-stop` | A stop distance should scale with volatility (0.7 daily ATR) but never widen past the 4% level that protects a | 57.84% / 39.29% | — | **51.32%** / 37.88% / 1.26 | current |
| `intraday-seasonality` | QQQ down more than 1% by the close forces leveraged-ETF selling into the close; buy the closing print and own  | 21.84% / 43.75% | — | **26.41%** / 39.24% / 0.96 | current |
| `event-risk-overlay` | The monthly option-expiry session is the one systematically weak session of the expiry cycle; own the cycle an | 26.94% / 39.04% | — | **22.20%** / 36.97% / 0.96 | current |
| `ratio-pairs` | The TQQQ/QQQ ratio is a leverage-cycle meter: froth precedes amplified shocks, a deep discount with a turn pre | 18.96% / 34.59% | — | **20.42%** / 33.94% / 1.13 | current |
| `time-of-day` | The overnight+first-30m block pays because it settles the previous session's closing pressure, so it should be | 19.70% / 31.81% | — | **17.21%** / 31.78% / 0.89 | current |
| `ml-classifier` | Unsupervised regime clustering allocates TQQQ/QQQ/BIL by each cluster's past forward returns. | 20.69% / 36.04% | — | **16.15%** / 36.60% / 0.67 | current |
| `ml-crash-overlay-winner` | TQQQ's 3x daily reset makes leverage favorable only when the path is smooth; a walk-forward ML classifier of 5 | 15.80% / 22.42% | — | **15.07%** / 23.33% / 0.76 | current |
| `intraday-momentum` | A weekly three-state leverage ladder on the Nasdaq-100: 3x TQQQ when the overnight-minus-intraday spread and t | 13.51% / 63.98% | — | **14.65%** / 63.55% / 0.61 | current |
| `intraday-mean-reversion` | After a >=3% intraday QQQ capitulation, buy TQQQ at the next open and sell before that session's close; flat ( | 11.31% / 31.47% | — | **12.41%** / 21.48% / 0.71 | current |
| `overnight-crash-filter` | Night continues an up day; the day reverses a down night; size by a 3-sigma gap budget. | 10.37% / 27.62% | — | **11.34%** / 26.98% / 0.81 | current |
| `letf-rebalance-flow` | Nasdaq underperformance vs SPY at the close is temporary LETF/flow pressure; buy TQQQ for a three-session reve | 13.20% / 41.80% | — | **7.80%** / 42.98% / 0.40 | current |
| `risk-parity-hrp` | Equal-risk QQQ/TQQQ composition with a risk budget that rises after transient volatility spikes and is damped  | 5.70% / 18.46% | — | **6.49%** / 17.89% / 0.69 | current |
| `dual-speed-regime` | QQQ's 60-minute EMA cross measures intraday trend persistence; hold TQQQ only while that trend is up and flat  | 5.38% / 38.02% | 28.76% | **5.15%** / 36.93% / 0.35 | pre_tune |
| `gap-capitulation-reversal` | Buy a quiet, short-term-oversold capitulation in QQQ, not a generic gap-down in a 165-day bull regime. | 4.18% / 12.49% | 8.30% | **4.64%** / 10.63% / 0.82 | pre_tune |
| `winner-ensemble-blend` | Inverse-volatility allocation across two independent return streams: calm QQQ carry (1x) and panic-reversal TQ | 0.30% / 32.67% | — | **3.04%** / 30.53% / 0.33 | current |
| `volume-orderflow` | A heavy-volume intraday decline that closes in the upper half of its range marks absorbed supply, so TQQQ rise | 0.87% / 16.66% | — | **2.49%** / 13.11% / 0.36 | current |
| `dynamic-leverage-throttle` | Volatility-shock recovery: buy TQQQ when a realised-vol shock is decaying inside a market drawdown, sized inve | 2.65% / 9.16% | 5.24% | **2.38%** / 15.30% / 0.54 | pre_tune |
| `gap-fill-fade` | Short QQQ on confirmed failed small gap-ups in a weak, stressed tape. | 1.43% / 0.48% | — | **2.21%** / 0.38% / 6.53 | current |
| `stop-reentry-recovery` | Buy TQQQ after a leveraged-ETF downside overshoot (TQQQ falls >=3% intraday and underperforms 3x QQQ by >=1pp) | 1.25% / 1.81% | — | **2.05%** / 1.25% / 5.09 | current |
| `daily-regime-minute-entry` | A 4% break below the TQQQ session open predicts continuation into the close; trade it as an intraday short ins | -0.04% / 64.18% | 0.91% | **2.04%** / 62.82% / 0.20 | pre_tune |
| `ensemble-signals` | Volatility spikes mean-revert; the high-vol contraction phase is a distinct TQQQ recovery window, while rising | -5.21% / 76.04% | -6.34% | **1.34%** / 75.91% / 0.20 | pre_tune |
| `vol-kelly-overlay` | Buy a volatility-scaled TQQQ position after a 1-minute-RV spike, an oversold QQQ drawdown and the first up-clo | 1.81% / 19.22% | — | **1.03%** / 16.50% / 0.17 | current |
| `drawdown-regime` | After a >=20% QQQ drawdown, own TQQQ only inside a confirmed 60-session recovery window, then stand aside unti | -1.64% / 48.81% | 17.20% | **-0.11%** / 47.55% / 0.07 | pre_tune |
| `donchian-breakout` | A Donchian breakout is only worth leveraging when short, medium and long breakout horizons agree; the alignmen | -3.38% / 37.05% | 13.40% | **-0.94%** / 35.77% / 0.01 | pre_tune |
| `opening-range-breakout` | A failed breakdown of the 30-minute opening range that reclaims the range low is a liquidity-sweep reversal; b | -2.10% / 17.22% | — | **-1.32%** / 19.99% / -0.33 | current |
| `drawdown-stop-overlay` | A failed breakdown / stop-run reclaim: buy TQQQ after QQQ undercuts its prior 20-day low intraday but closes b | -1.74% / 45.45% | -9.25% | **-2.37%** / 55.33% / 0.06 | pre_tune |

Notes:
- `pre_tune` means the published curve is the pre-registered version and
  the current `result.json` is a post-tune variant (see §3 of the audit).
- The `holdout` results remain in the individual `result.json` files;
  they are not used here and are not a clean holdout for tuned strategies.
- The old pre-audit summary is preserved as `SUMMARY_pre_audit.md`.
