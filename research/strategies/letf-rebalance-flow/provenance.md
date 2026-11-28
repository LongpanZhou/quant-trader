# Provenance — Relative Nasdaq flow dip (RN Flow)

Every rule or claim in `HYPOTHESIS.md` / `report.md` maps to a source below, or
is marked **Own test / no external source**. This is a design-stage provenance
record; the rebuilt strategy has not been backtested.

## External sources

| # | Idea / claim it supports | Source | URL | Type | Role | What exactly it supports | Confidence |
|---|---|---|---|---|---|---|---|
| 1 | Leveraged-ETF rebalancing and option delta-hedging create measurable price pressure in the last part of the session, concentrated in the underlying index. | Barbon et al. (2022), *Liquidity Provision to Leveraged ETFs and Equity Options Rebalancing Flows: Evidence from End-of-Day Stock Prices* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3925725 | paper | inspired rule | Documents economically large end-of-day price pressure from LETF rebalancing and option hedging, and links LETF flows to last-half-hour returns. Motivates the end-of-day flow proxy and the relative QQQ–SPY signal. It does not establish the exact daily z-score or 3-session hold. | medium |
| 2 | LETF rebalancing concentrates near the close and is associated with higher end-of-day volatility. | Shum, Hejazi, Haryanto & Rodier (2016), *Intraday Share Price Volatility and Leveraged ETF Rebalancing*, Review of Finance 20(6):2379–2409 | https://doi.org/10.1093/rof/rfv061 | paper | supports assumption | Documents end-of-day rebalancing activity and end-of-day volatility. Supports the timing/flow interpretation; it is about volatility, not directional reversal. | high |
| 3 | End-of-day moves can reverse: intraday losers can outperform into the close / afterwards. | Baltussen, Da & Soebhag (2025); Vidovich & Zerjal (2026), *The End-of-Day Reversal After 2019: A Pre-Registered Test on S&P 500 Stocks Excluding Heavily Traded Names* | https://arxiv.org/abs/2611.09286 | paper | inspired rule | Documents an end-of-day reversal through 2019, weaker after 2019. Motivates fading a temporary relative move rather than extrapolating it. The paper is cross-sectional S&P 500, not QQQ–SPY, and its mechanism tests do not all pass. | high |
| 4 | The opposite hypothesis: intraday momentum, where the early move predicts the late move. | Gao, Han, Li & Zhou (2018), *Market intraday momentum*, Journal of Financial Economics 129(2):394–414 | https://doi.org/10.1016/j.jfineco.2018.05.009 | paper | tested only / competing hypothesis | Shows the first half-hour return predicts the last half-hour return. This is the continuation alternative to the reversal hypothesis. The old overlay found continuation in the last hour on risk-off rally days, so this source is a genuine competing explanation, not a rejected one. | high |
| 5 | Caution: the LETF late-day effect may be statistically detectable but economically small. | Lenkey (2024), *The market impact of leveraged ETFs: A survey of the literature*, Quantitative Finance and Economics 8(4):815–840 | https://doi.org/10.3934/QFE.2024031 | paper | supports assumption / caution | Concludes that reported associations are statistically significant but the economic associations appear insignificant and many papers have methodological issues. This is why the rebuild must be cheap, robust, and tested at 5/10 bp, not assumed to work. | high |
| 6 | Caution: LETF rebalancing may not amplify late-day returns or volatility. | Ivanov & Lenkey (2018), *Do leveraged ETFs really amplify late-day returns and volatility?*, Journal of Financial Markets 41:36–56 | https://doi.org/10.1016/j.finmar.2018.09.001 | paper | supports assumption / caution | Finds little evidence of amplification, cited in the Lenkey survey. Motivates treating the flow mechanism as an interpretation and relying on the local event study. | medium |
| 7 | Background mechanics: constant-leverage ETFs must rebalance daily. | Cheng & Madhavan (2009), *The Dynamics of Leveraged and Inverse Exchange-Traded Funds*, Journal of Investment Management 7(4) | null | paper | supports assumption | Explains daily constant-leverage rebalancing mechanics; does not establish a directional last-hour reversal. URL deliberately null: the old web page's SSRN 1393995 link was not independently verified. | medium |

## Own tests / no external source

| # | Rule / claim | Source | Role | Evidence | Confidence |
|---|---|---|---|---|---|
| 8 | The old overlay's 96-event event study: TQQQ last hour +64 bp, next overnight −90 bp. | Own test / no external source | inspired rule | Measured on the local 1m QQQ/TQQQ/BIL panel, 2017–2026 test window. This is the empirical seed for the reversal hypothesis, but it is *absolute* QQQ/TQQQ, not the relative QQQ–SPY signal. | high (that the old measurement exists) |
| 9 | The old absolute last-hour move predicts an overnight reversal: coefficient −2,886 bp per unit, HAC t = −2.27, controlling for the day's move. | Own test / no external source | inspired rule | OLS/HAC on the old daily event frame; strongest in 2023–26. Motivates fading end-of-day pressure, but does not prove the relative version. | high (old estimate), low (transfer to new signal) |
| 10 | The pure last-hour standalone was too small (2–14% CAGR), and the default-long exit version was too correlated (0.64–0.72) with the old base. | Own test / no external source | rejected design | Prior development screens on the 2016–2023 period (before the backtest pause). These are the reasons the rebuild changes to a relative signal and a multi-session hold instead of a one-hour overlay. | high |
| 11 | The multi-session absolute down-day reversal was the only prior form with a plausible standalone return and correlation <0.60 (16.8–17.2% CAGR, 51–65% DD, 0.27–0.49 corr). | Own test / no external source | inspired rule | Prior development screens (before the pause). Motivates the 3-session hold; the new signal replaces the absolute down day with a relative QQQ–SPY dip. | medium |
| 12 | z = −1.25, 20-day scale, 3-session hold. | Own test / no external source | parameter prior | Chosen before the new test from the old event study and standard z-score practice; pre-registered neighbours are −1.00/−1.50 and 1/2/5 sessions. Not optimized on the new strategy. | medium |

## Data

| Data | Path | Use | Limitation |
|---|---|---|---|
| QQQ 1-minute | `data/intraday-hf/QQQ-1m.parquet` | marking the strategy; QQQ signal cross-check | adjusted, regular session |
| TQQQ 1-minute | `data/intraday-hf/TQQQ-1m.parquet` | traded risk asset | intraday TQQQ is a within-day 3x transform of QQQ in this archive, anchored to real daily closes; no independent TQQQ microstructure |
| BIL 1-minute | `data/intraday-hf/BIL-1m.parquet` | risk-off asset | raw source had a 2017 reverse split; `bt.load_1m` adjusts it |
| QQQ daily | `data/intraday-hf/QQQ-1d-yahoo.parquet` | signal return | adjusted close |
| SPY daily | `data/round3/yahoo/SPY-1d-yahoo.parquet` | signal return | adjusted close, 2015-01-02..2026-10-23 |
| SPY 1-minute | `data/cache/dukascopy/SPY/` | would enable a last-hour signal | only 2026-08-31 onward; **not usable for 2016–2023** |

## Not used

| Source | Why not used |
|---|---|
| ETF.com, *One Bad Day in a Leveraged QQQ ETF* | Anecdotal single-day case study; no testable rule. It was cited on the old web page but is not evidence for this design. |
| The old 165-day QQQ/TQQQ baseline and the round-1 4% stop | Banned shared base. The 165-day baseline is computed **only** as a correlation benchmark, never as a gate. |
| The old overlay's `build_weights` / weights | Not called, copied, or reused. The new code builds a daily relative-signal state machine from scratch. |
