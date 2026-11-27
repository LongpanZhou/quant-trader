# Provenance: participation exhaustion long

**Rule:** every claim below is either sourced, or explicitly marked
`Own test / no external source`. Distinguish **inspired the rule** from
**tested and rejected**. URLs come from my round-2 audit or from the search
results recorded there; where I only know the title, the URL is `null` rather
than guessed.

---

## 1. Sources that inspired the rule

| # | Idea / claim it supports | Source | Role | Evidence in the source | Confidence |
|---|---|---|---|---|---|
| S1 | After a **high-volume decline**, returns tend to **reverse** rather than continue, because the price pressure is non-informational (liquidity provision). This is the sign H1 needs. | Campbell, J. Y., Grossman, S. J., & Wang, J. (1993). *Trading volume and serial correlation in stock returns.* Quarterly Journal of Economics 108(4), 905–939. URL `null` (title only; not verified in this session). | inspired rule | Shows daily returns exhibit more negative serial correlation following high-volume days, and links it to non-informational (liquidity/risk-bearing) trading rather than information. That is the economic mechanism for buying a heavy-volume decline. | high (for the paper's existence and direction); medium (for transfer to a 3× index ETF at a 5-session horizon) |
| S2 | Extreme **abnormal volume** carries information about subsequent returns (the high-volume return premium). | Gervais, S., Kaniel, R., & Mingelgrin, D. H. (2001). *The high-volume return premium.* Journal of Finance 56(3), 877–919. Cross-country replication: *The high-volume return premium: cross-country evidence*, JFE (2012). [link](https://www.sciencedirect.com/science/article/abs/pii/S0304405X11001954) | inspired rule | Documents that stocks with unusually high volume outperform over the following days/weeks, replicated across 41 countries. Supports "abnormal participation is informative", though their test is cross-sectional and monthly. | medium |
| S3 | The **interaction** of volume with direction matters: high-volume moves are late-stage and reverse faster, while low-volume moves persist. | Lee, C. M. C., & Swaminathan, B. (2000). *Price momentum and trading volume.* Journal of Finance 55(5), 2017–2069. [doi](https://doi.org/10.1111/0022-1082.00280) | inspires the direction check | Momentum life cycle: high-volume winners reverse faster. Used here as the reason the event must be a *decline* (a high-volume advance is the late-stage case that reverses), and as the reason the close-location filter is pre-registered in H1a. | medium |
| S4 | Short-horizon return autocovariance turns negative after high-volume days (a second, independent statement of S1). | Conrad, J., Hameed, A., & Niden, C. (1994). *Volume and autocovariances in short-horizon individual security returns.* Journal of Finance 49(4). URL `null` (title only). | supports assumption | High-volume days are followed by negative short-horizon autocorrelation, consistent with reversal after liquidity-driven moves. | medium |
| S5 | Participation conditions whether a price move is informative — the original `volume-orderflow` claim, and the reason the event requires `rvol ≥ 1.5` rather than any decline. | Gao, L., Han, Y., Li, S. Z., & Zhou, G. (2018). *Market intraday momentum.* Journal of Financial Economics 129(2), 394–414. [doi](https://doi.org/10.1016/j.jfineco.2018.05.009) | inspired rule (condition only) | Finds intraday predictability is stronger on higher-volume days. I use only the conditioning insight; their actual first-half-hour → last-half-hour rule was tested and rejected (see §3). | medium |
| S6 | A 5-session horizon is long enough for liquidity-driven pressure to unwind but short enough that the signal is not a slow trend bet. | Own test / no external source | design choice | Chosen from the event-study literature range (1–20 days) with the constraint that a longer hold collapses exposure toward the old base and raises correlation. Declared neighbours 3 and 10 sessions in `spec.md` §4. | — |
| S7 | Exact thresholds `rvol ≥ 1.5`, `intraday ≤ −0.8%`, `clv ≥ 0`, `hold = 5`, `size = 100%`. | Own test / no external source | design choice | Fixed a priori, before any test of this event definition. The only prior information is the aggregate sign in `hypothesis.md` §6, measured on a *different* event (close-to-close, no clv filter, overlapping). All thresholds sit on declared grids so the report can show a plateau rather than a point. | — |
| S8 | Time-based exit only; no price stop. | Own test / no external source | design choice | A price stop would recreate the original overlay (F8-style attribution failure). The round-2 evidence that a stop alone cannot control this instrument's drawdown is in §3. | — |

## 2. Sources used for context, not for the rule

| Source | Use |
|---|---|
| Kaminski, K. M., & Lo, A. W. (2014). *When do stop-loss rules stop losses?* J. Financial Markets 18, 234–254. [doi](https://doi.org/10.1016/j.finmar.2013.07.001) | Explains why the *original* stop worked in momentum states. Not used in the rebuild, which has no stop. |
| Lou, D., Polk, C., & Skouras, S. (2019). *A tug of war: overnight versus intraday expected returns.* JFE 134(1). [pdf](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf) | Explains why the original held overnight. The rebuild deliberately does **not** optimise for the overnight/intraday split; it holds whole sessions, so this is context only. |
| Konishi, H. (2002). *Optimal slice of a VWAP trade.* J. Financial Markets 5(2). [link](https://www.sciencedirect.com/science/article/abs/pii/S1386418101000234) | VWAP as an execution benchmark, not a forecast — the reason the VWAP branch was dropped. |

## 3. Tested and rejected (evidence against, not for)

| Item | Evidence | Consequence |
|---|---|---|
| **Volume-expansion timing ladder** — hold TQQQ while 5-day/60-day mean volume is below a threshold, else BIL. | Pre-pause dev (2016-01→2023-12, 1 bp): q70 32.42/65.97, q80 37.72/71.30, vs TQQQ 36.15/82.29 and the 165d baseline 44.76/58.76. Placebo with matched off-frequency: p(placebo ≥ real) = 0.35 at 29% off, 0.30 at 19% off. | Killed the *timing* form. Volume level alone has no usable forward information; the design moved to an event study. |
| **Volume-confirmed 1m/5m order flow** (CLV-signed volume, tick-rule flow, up/down-volume pressure, VWAP deviation, cumulative RVOL). | Correlations with the next 30-minute TQQQ return: −0.010, −0.009, +0.001 (5m flow), +0.007 (5m VWAP), −0.047 (cum RVOL, non-monotone and contrarian). | No intraday flow signal survives; the rebuild does not use 1-minute flow. |
| **Overnight RVOL gate** — go to BIL overnight after a high-volume session. | Pooled it looked strong (rvol>1.5 & down: −74.9 bp), but era spreads were −0.05% / −0.23% / **+0.06%**; in the 5y window high-volume nights were *better* (+0.236% vs +0.155%), and applied to the winner it cut 5y CAGR by 8.8 pp. | The round-2 result was a 2020 artifact; the rebuild does not use it, and its sign is the opposite of this rebuild's hypothesis. |
| **The original volume-armed stop as a standalone strategy** — always-long TQQQ, 4% stop armed by participation, no regime. | Pre-pause dev: 39.14/79.96 (volume-armed) and 43.38/77.28 (always armed) versus 53.56/41.11 for regime + stop. Without the regime the stop leaves an ~80% drawdown because the losses are overnight gaps. | The stop is overlay-only, and this is the evidence that the rebuild must be an event strategy, not a stop. |
| **Cross-sectional sector HVRP** — long the 3 highest-abnormal-volume of 11 sector SPDRs, short the 3 lowest, monthly, beta-hedged. | Not tested: it needs 1-minute sector history for minute marks, and none exists locally (`data/cache/dukascopy/SPY` covers 2026-08-31→2026-11-20 only; `data/round3/` is empty; free 1-minute history back to 2016 is not available). | Designed and dropped for a documented data reason, not a performance reason. If a minute-level sector panel is ever added, this is the better-powered version of the same idea and should be tried. |
| **Distribution-day counting**, **VWAP/OBV/A-D as a regime**, **continuous volume-scaled stop**. | Round-2 measured results: 9.14/38.23; 47.08/58.03 and 28.24/61.09; 61.77/47.68. | Not reused. |

## 4. Pre-pause exploratory scripts in this folder

`explore.py`, `explore2.py`, `explore3.py` were written and run on 2026-11-26
**before** the pause was announced. They are kept as the origin of the evidence
in §3 and `hypothesis.md` §6. They are **not** part of the frozen strategy, they
use a different event definition, and they must not be re-run without
authorisation. `strategy.py` does not import them.
