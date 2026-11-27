# Revisit summary: 26 standalone rebuilds

Development 2016-01-04 → 2023-12-29. Holdout 2024-01-02 → 2026-10-23, run once for the four strategies that passed their dev gates. All marks are 1-minute, fills are next-open, costs are 1 bp unless stated. TQQQ dev benchmark: 36.39% CAGR / 82.29% max DD; holdout: 43.59% / 62.21%.

| Strategy | Idea | Status | Original 10y CAGR/DD | Rebuild dev 1 bp | Holdout 1 bp | Corr vs 165d |
|---|---|---|---|---|---|---|
| `daily-regime-minute-entry` | A 4% break below the TQQQ session open predicts continuation into the close; trade it as an intraday s... | **rejected** | 58.80% / 44.56% | -0.04% / 64.18% | not run | -0.20 |
| `donchian-breakout` | A Donchian breakout is only worth leveraging when short, medium and long breakout horizons agree; the ... | **rejected** | 46.36% / 59.79% | -3.38% / 37.05% | not run | 0.41 |
| `drawdown-regime` | After a >=20% QQQ drawdown, own TQQQ only inside a confirmed 60-session recovery window, then stand as... | **rejected** | 61.57% / 40.34% | -1.19% / 39.88% | not run | 0.06 |
| `drawdown-stop-overlay` | A failed breakdown / stop-run reclaim: buy TQQQ after QQQ undercuts its prior 20-day low intraday but ... | **rejected** | 43.27% / 45.23% | -1.74% / 45.45% | not run | 0.30 |
| `dual-speed-regime` | QQQ's 60-minute EMA cross measures intraday trend persistence; hold TQQQ only while that trend is up a... | **rejected** | 70.11% / 42.91% | 5.38% / 38.02% | not run | 0.35 |
| `dynamic-leverage-throttle` | Volatility-shock recovery: buy TQQQ when a realised-vol shock is decaying inside a market drawdown, si... | **rejected** | 57.05% / 41.32% | 2.65% / 9.16% | not run | 0.11 |
| `ensemble-signals` | Volatility spikes mean-revert; the high-vol contraction phase is a distinct TQQQ recovery window, whil... | **rejected** | 54.73% / 39.91% | -5.21% / 76.04% | not run | 0.47 |
| `event-risk-overlay` | The monthly option-expiry session is the one systematically weak session of the expiry cycle; own the ... | **rejected** | 67.06% / 40.65% | 26.94% / 39.04% | not run | 0.34 |
| `gap-capitulation-reversal` | Buy a quiet, short-term-oversold capitulation in QQQ, not a generic gap-down in a 165-day bull regime. | **passed** | — | 4.18% / 12.49% | 5.99% / 2.29% | 0.03 |
| `gap-fill-fade` | Short QQQ on confirmed failed small gap-ups in a weak, stressed tape. | **rejected** | 65.17% / 39.02% | 1.42% / 0.48% | not run | — |
| `intraday-mean-reversion` | After a >=3% intraday QQQ capitulation, buy TQQQ at the next open and sell before that session's close... | **passed** | 51.06% / 44.83% | 11.31% / 31.47% | 15.62% / 27.66% | 0.13 |
| `intraday-momentum` | A weekly three-state leverage ladder on the Nasdaq-100: 3x TQQQ when the overnight-minus-intraday spre... | **rejected** | 55.63% / 44.89% | 11.97% / 64.46% | not run | 0.62 |
| `intraday-seasonality` | QQQ down more than 1% by the close forces leveraged-ETF selling into the close; buy the closing print ... | **passed** | 61.35% / 44.18% | 21.84% / 43.75% | 40.48% / 31.75% | 0.26 |
| `letf-rebalance-flow` | Nasdaq underperformance vs SPY at the close is temporary LETF/flow pressure; buy TQQQ for a three-sess... | **rejected** | 67.92% / 41.50% | 13.20% / 41.80% | not run | 0.40 |
| `ml-classifier` | Unsupervised regime clustering allocates TQQQ/QQQ/BIL by each cluster's past forward returns. | **rejected** | 74.95% / 40.48% | 20.69% / 36.04% | not run | 0.58 |
| `ml-crash-overlay-winner` | TQQQ's 3x daily reset makes leverage favorable only when the path is smooth; a walk-forward ML classif... | **rejected** | 72.24% / 41.50% | 15.80% / 22.42% | not run | 0.50 |
| `opening-range-breakout` | A failed breakdown of the 30-minute opening range that reclaims the range low is a liquidity-sweep rev... | **rejected** | 48.98% / 48.55% | -2.10% / 17.22% | not run | — |
| `overnight-crash-filter` | Night continues an up day; the day reverses a down night; size by a 3-sigma gap budget. | **rejected** | 67.47% / 36.52% | 10.37% / 27.62% | not run | 0.26 |
| `ratio-pairs` | The TQQQ/QQQ ratio is a leverage-cycle meter: froth precedes amplified shocks, a deep discount with a ... | **passed** | 69.50% / 39.11% | 18.96% / 34.59% | 24.82% / 22.94% | 0.53 |
| `risk-parity-hrp` | Equal-risk QQQ/TQQQ composition with a risk budget that rises after transient volatility spikes and is... | **rejected** | 56.97% / 43.19% | 5.70% / 18.46% | not run | 0.78 |
| `stop-reentry-recovery` | Buy TQQQ after a leveraged-ETF downside overshoot (TQQQ falls >=3% intraday and underperforms 3x QQQ b... | **retired_overlay_only** | 61.03% / 39.92% | 1.25% / 1.81% | not run | -0.00 |
| `time-of-day` | The overnight+first-30m block pays because it settles the previous session's closing pressure, so it s... | **retired_overlay_only** | 49.23% / 42.66% | 19.68% / 31.81% | not run | 0.34 |
| `vol-kelly-overlay` | Buy a volatility-scaled TQQQ position after a 1-minute-RV spike, an oversold QQQ drawdown and the firs... | **rejected** | 47.53% / 45.32% | 1.81% / 19.22% | not run | 0.27 |
| `vol-scaled-crash-stop` | A stop distance should scale with volatility (0.7 daily ATR) but never widen past the 4% level that pr... | **rejected** | 62.60% / 40.94% | 57.84% / 39.29% | not run | 0.71 |
| `volume-orderflow` | A heavy-volume intraday decline that closes in the upper half of its range marks absorbed supply, so T... | **retired_overlay_only** | 65.90% / 42.49% | 0.87% / 16.66% | not run | 0.14 |
| `winner-ensemble-blend` | Inverse-volatility allocation across two independent return streams: calm QQQ carry (1x) and panic-rev... | **rejected** | 58.42% / 41.18% | 0.30% / 32.67% | not run | 0.24 |

## Why each strategy got its status

- **daily-regime-minute-entry — rejected.** Negative dev CAGR; the 4% break short does not survive costs.
- **donchian-breakout — rejected.** Negative dev CAGR; 5/10 bp destroy it.
- **drawdown-regime — rejected.** Negative dev CAGR; the deep-drawdown re-risk is too rare and mistimed.
- **drawdown-stop-overlay — rejected.** Negative dev CAGR; the stop is only useful on the old base.
- **dual-speed-regime — rejected.** 5.4% CAGR and Sharpe 0.36; below cash/QQQ on risk-adjusted terms.
- **dynamic-leverage-throttle — rejected.** 2.65% CAGR with only 5 entries; no usable standalone edge.
- **ensemble-signals — rejected.** Negative dev CAGR; the vol state machine loses money without the old base.
- **event-risk-overlay — rejected.** Strong 26.94%/39.04% and corr 0.34, but fails its own DD>30% gate.
- **gap-capitulation-reversal — passed.** Passed dev gates: 4.18%/12.49%, corr 0.03; holdout 5.99%/2.29%.
- **gap-fill-fade — rejected.** 1.42% CAGR, below BIL; the short is too small to matter.
- **intraday-mean-reversion — passed.** Passed dev gates: 11.31%/31.47%, corr 0.13; holdout 15.62%/27.66%.
- **intraday-momentum — rejected.** Corr 0.62 with the old base; fails the <0.60 diversity rule.
- **intraday-seasonality — passed.** Passed dev gates: 21.84%/43.75%, corr 0.26; holdout 40.48%/31.75%.
- **letf-rebalance-flow — rejected.** 13.2%/41.8%; dominated by QQQ on both return and drawdown.
- **ml-classifier — rejected.** 20.69%/36.04%, corr 0.58; QQQ has higher Sharpe and lower DD.
- **ml-crash-overlay-winner — rejected.** 15.80%/22.42%, corr 0.50; the 10 bp result loses to QQQ on Sharpe.
- **opening-range-breakout — rejected.** Negative dev CAGR; the reclaim has no net edge.
- **overnight-crash-filter — rejected.** 10.37%/27.62%, but fails its conditioning/robustness gates.
- **ratio-pairs — passed.** Passed dev gates: 18.96%/34.59%, corr 0.53; holdout 24.82%/22.94%.
- **risk-parity-hrp — rejected.** Corr 0.78 with the old base; the risk model is still TQQQ beta.
- **stop-reentry-recovery — retired_overlay_only.** Only 1 event in 2,012 sessions; the signal is effectively empty.
- **time-of-day — retired_overlay_only.** Retired: conditioning does not beat the unconditional overnight hold (F1/F2).
- **vol-kelly-overlay — rejected.** 1.8% CAGR and Sharpe 0.25; no standalone edge.
- **vol-scaled-crash-stop — rejected.** Highest rebuild return (57.84%/39.29%) but corr 0.71; fails the <0.60 independence rule.
- **volume-orderflow — retired_overlay_only.** Only 3 events in 2,012 sessions; effectively empty.
- **winner-ensemble-blend — rejected.** 0.3% CAGR; the two streams do not combine into a standalone edge.

## Correlations and diversity

- Passed rebuilds: ratio-pairs, intraday-seasonality, intraday-mean-reversion, gap-capitulation-reversal.
- Average pairwise correlation among the passed set: **0.212**; maximum **0.383** (limit 0.70).
- Correlation vs the old 165-day base: ratio-pairs 0.53, intraday-seasonality 0.26, intraday-mean-reversion 0.13, gap-capitulation-reversal 0.03 (limit 0.60).
- The original 26 shared-base strategies averaged about 0.86 pairwise.

## Honest overall assessment

Removing the shared 165-day TQQQ base destroyed most of the reported returns. Only four rebuilds passed their pre-registered development gates: ratio-pairs, intraday-seasonality, intraday-mean-reversion and gap-capitulation-reversal. They are genuinely independent — average pairwise correlation 0.21, and all four are below 0.60 versus the old base — but their dev CAGRs are 4–22%, far below TQQQ's 36.4%. Two of them beat TQQQ over the last five years: intraday-seasonality (26.07% / 43.75% vs 14.29% / 82.29%) and ratio-pairs (17.11% / 34.59%). Over the full ten years TQQQ still wins on CAGR, though with an 82% drawdown.

The highest-return standalone rebuild is vol-scaled-crash-stop at 57.84% / 39.29% dev, which beats TQQQ on both return and drawdown at 1–5 bp. It is not independent: its daily correlation with the old base is 0.71, so it is best described as a better-managed TQQQ exposure rather than a new edge. event-risk-overlay is the strongest genuinely low-correlation strategy at 26.94% / 39.04% (corr 0.34), but it fails its own 30% drawdown gate.

Most of the other 22 ideas were overlays: stops, filters and risk rules that added value only on top of the old trend base. Several signals were effectively empty after the base was removed (stop-reentry: 1 event; volume-orderflow: 3 events). The evidence supports the original suspicion: the shared base was doing most of the work.
