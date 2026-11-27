# Provenance — gap-fill-fade round-3 rebuild

Every rule or claim below is mapped to a source, or marked **Own test / no
external source**. The old overlay's 65.17%/39.02% result is **not** evidence
for this rebuild and is not used to justify any parameter.

Source quality note: the gap-size split is supported by a mix of peer-reviewed
papers (Aiche et al., *Price gap anomaly*, IOSR, Grant et al.) and 2026
industry/data studies (MPM, Steady Turtle, Open Market Journal,
thetrading.tools). The exact band, confirmation, stop, time stop and vol target
are own-test choices; the papers describe the effect, not these parameters.

## 1. Supporting and inspiring sources

| # | Idea / claim it supports | Source | URL | Type | Role | Evidence | Confidence |
|---|---|---|---|---|---|---|---|
| 1 | Small opening gaps fill; large gaps persist and continue. This is the size split behind the +0.10–0.75% band. | MPM Markets (2026), *Testing the "Gaps Always Fill" Myth Across Six Futures Markets* | https://mpmmarkets.com/research/gaps-always-fill-myth-futures-markets | report | inspired rule | Small gaps fill quickly and almost always same-session; large gaps often remain unfilled for several sessions and continue; no reliable edge after costs. Used to restrict the fade to small gaps and exclude >1% gaps. | high |
| 2 | NQ/ES same-session fill probability falls monotonically with gap size; big gaps are continuation. | Steady Turtle (2026), *How often does the gap fill? NQ & ES, six years of data* | https://steady-turtle.com/statistics/gap-fill-probability | blog | inspired rule | NQ same-session fill 60.3%; sub-10-point gaps 96.4%, 80-point+ 38.1%; "big gaps are continuation, not fade." Used for the small-gap band and the decision not to short large gaps. | high |
| 3 | Gap-fill probability scales with ATR: under 0.25× ATR fills ~94%, over 2× ATR fills ~9%. | Open Market Journal (2026), *Does the S&P 500 Fill Its Gaps? It Depends on Size* | https://openmarketjournal.com/research/sp500-gap-fill-probability | blog | supports assumption | Same-session fill rates by ATR bucket. A 0.10–0.75% QQQ gap is roughly 0.07–0.50× the local median 14-day ATR of 1.49%, inside the high-fill region. | medium |
| 4 | QQQ/SPY 2%+ up-gaps fill only ~27% same-day; 1%+ up-gaps have positive open-to-close drift. Large gap-ups are continuation. | thetrading.tools (2026), *Gap Analysis: Do Gaps Always Fill? SPY & QQQ* | https://www.thetrading.tools/gap-analysis | data | supports assumption | 2%+ up-gap same-day fill 27%, 52% within five sessions; 1%+ up-gaps average positive open-to-close with ~60% up-day rate. Used to exclude large gap-ups from the short. | medium |
| 5 | Small up-gaps close same-session; large +2%+ up-gaps mostly do not; up-gaps fill faster than down-gaps. | IOSR Journal of Economics and Finance (2019), *Filling Open Price Gap on Intraday Timeframe: A Case Study for DJIA Index Stocks* | https://www.iosrjournals.org/iosr-jef/papers/Vol10-Issue5/Series-2/C1005021418.pdf | paper | supports assumption | 68.2% of small up-gaps close same-session; only 12.1% of +2%+ up-gaps close; 50% of up-gaps close by 09:52. Used for the small-gap band and the early-session timing. | medium |
| 6 | Positive gaps drift in the gap direction; negative gaps are larger and adjust faster. Supports keeping large gap-ups as continuation and treating the fade as a small-gap, positive-gap phenomenon. | Aiche, Cohen & Griskin (2024), *Stocks Opening Price Gaps and Adjustments to New Information*, Computational Economics 63 | https://link.springer.com/article/10.1007/s10614-023-10363-w | paper | supports assumption | Ten years of S&P 500, Nasdaq-100 and Russell 2000 stocks: negative gap openings are larger, bad-news adjustment is quicker, positive gaps drift. Used as background for the asymmetry. | medium |
| 7 | Gap-day prices tend to move in the gap direction; the momentum effect is temporary; the naive "gaps always fill" rule is false. | *Price gap anomaly in the US stock market: The whole story*, Journal of Behavioral and Experimental Finance (2020) | https://www.sciencedirect.com/science/article/pii/S1062940820300747 | paper | supports assumption | 1928–2018 DJI/S&P 500/Nasdaq: prices change in the gap direction on the gap day; no evidence gaps always fill. Used to motivate testing continuation and the size split rather than a blanket fade. | medium |
| 8 | Intraday reversals after large opening changes exist, are stronger after positive changes, and shrink after bid–ask costs. | Grant, Wolf & Yu (2005), *Intraday price reversals in the US stock index futures market: A 15-year study*, Journal of Banking & Finance 29(5) | https://www.sciencedirect.com/science/article/pii/S0378426604000949 | paper | inspired rule | S&P 500 futures 1987–2002: significant intraday reversals after large opening gaps, stronger after positive gaps; profits reduced by a bid–ask proxy. Supports the fade direction and the cost caution. | high |
| 9 | High overnight returns negatively predict the first half-hour return; the reversal strengthens during market stress. | *Does overnight return predict the first half-hour return for U.S. market indices?* (2026) | https://www.sciencedirect.com/science/article/pii/S1062940826001294 | paper | inspired rule | SPY: overnight return negatively predicts the first 30-minute return; stronger in high-volatility periods including the early COVID phase. This is the closest external support for the 10:00 confirmation and the stress filter. | high |
| 10 | The opening auction aggregates overnight information; the opening price is a meaningful signal. | *Price Discovery in Auction Markets: A Look Inside the Black Box*, Review of Financial Studies 13(3) (2000) | https://academic.oup.com/rfs/article-abstract/13/3/627/1576835 | paper | supports assumption | Opening mechanisms aggregate overnight information; the opening trade can reflect stabilization and non-information factors. Background for why the opening gap carries information. | medium |
| 11 | Opening procedures and call auctions incorporate overnight information; opening volume predicts daytime volume and opening trades show reversals. | Gross (2003), *Price Discovery in Opening Procedures: The Efficiency of NYSE and Nasdaq Openings after Delays* | https://leeds-faculty.colorado.edu/grossd/Research/Price%20Discovery%20in%20Opening%20Procedures%202003-11.pdf | paper | supports assumption | NYSE/Nasdaq openings after delayed openings: overnight information is incorporated in the opening procedure. Background only; no parameter taken from it. | medium |
| 12 | Opening call auctions affect ongoing trade; opening volume relates to daytime volume and opening trade prices show reversals. | *The interaction between opening call auctions and ongoing trade: Evidence from the NYSE*, Journal of Financial Markets (2004) | https://www.sciencedirect.com/science/article/abs/pii/S1058330004000023 | paper | supports assumption | Opening batch volume predicts volume across the day; opening trade price reversals; the opening process handles information efficiently. Background only. | medium |
| 13 | Volatility-managed sizing: scale exposure by trailing realised variance instead of holding a fixed size. | Moreira & Muir (2017), *Volatility-Managed Portfolios* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431 | paper | supports assumption | Scale exposure inversely with trailing realised variance. Used for the 10% annualised vol-target sizing; the exact 10% and the 10% floor are own-test. | medium |
| 14 | Trading costs can erase short-term reversal profits; better portfolio construction can preserve some of them. | *Another look at trading costs and short-term reversal profits*, Journal of Banking & Finance (2012) | https://www.sciencedirect.com/science/article/pii/S0378426611002263 | paper | supports assumption | Reversal profits can survive costs with better portfolio construction; conventional cost estimates can be misleading. Used for the 1/5/10 bp cost sensitivity and the warning that the edge is cost-fragile. | medium |
| 15 | The 10:00 first-30-minute confirmation (`r30 < 0` and price below the open), the OR-high stop with a 0.2% floor / 1.5% cap, the 11:30 time stop, and the exact 10% vol target. | Own test / no external source | null | data | inspired rule | These are design choices, not published rules. The first-30-minute reversal literature (Grant et al.; the 2026 paper) motivates the confirmation in general, and the opening-range literature motivates the OR high as a level, but the exact thresholds, floor/cap and timing are own-test. | high |

## 2. Rejected sources and rules

| Source / rule | URL | Why rejected |
|---|---|---|
| Failed-opening-range-breakout family ("break out, fail, go the other way") — TradingEdge Journal (2026) | https://tradingedgejournal.com/blog/opening-range-breakout-futures-backtest/ | The article tests a 96-cell "failed breakout → other side" family on ES and finds nothing survived; every candidate was negative on the confirm months. A revert rate is not a trade. This rebuild does **not** fade the opening-range break; it uses the first 30 minutes only as a time confirmation of the gap. |
| Fetna (2026), *Opening-Range Breakout Does Not Survive Trading Costs* (SSRN 7428398) | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7428398 | 225 pre-registered ORB cells; zero survive realistic costs. Rejected as a basis for an ORB or failed-ORB trade. |
| Loomi (2026), *Gap Fill Strategy: NQ Opening Gap Statistics* | https://www.loomiai.io/learn/opening-gap-fill-strategy-nasdaq | 3,236 NQ gap-fade trades, 2010–2026: three of four gap-size buckets lose after 1 point of costs; small gaps are the worst. Rejected as a standalone gap-fade rule; the rebuild only uses the size split, plus confirmation, stop, target and vol sizing, and must prove the net edge itself. |
| FXAbsolute (2026), *XAUUSD Opening Range False Breakout Data* | https://fxabsolute.com/research/xauusd-opening-range-false-breakout-data | Descriptive path statistics, not net P&L; it explicitly says a near-100% boundary-break rate is not a win rate. Rejected as an edge source. |
| Zarattini & Aziz (2023), *Can Day Trading Really Be Profitable? Opening Range Breakout* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622 | The ORB continuation variant was tested in round 1 and failed to beat TQQQ standalone; the paper's TQQQ result uses 2–4× intraday notional, which this long-only 1× harness does not allow. Rejected as a basis for this rebuild. |
| Naive "gaps always fill" rule | https://mpmmarkets.com/research/gaps-always-fill-myth-futures-markets | Rejected by the local event study and MPM/Steady Turtle/Open Market Journal: large gap-ups continue, and small-gap fades are too small after costs. The rebuild only fades the small band with confirmation. |
| The old 165-day QQQ/TQQQ/BIL base and the round-1 4% armed stop | null (original `research/agents2/gap-fill-fade`) | Explicitly excluded by the 2026-11-26 clarification. The old 65.17%/39.02% result is not evidence for the rebuild. The strategy never holds TQQQ, never holds overnight, and has no 100–250-day MA gate. |

## 3. What is own-test, and what would change the design

Own-test components:

- the exact +0.10–0.75% band (the literature supports "small", not these
  numbers);
- the 10-day SMA plus 5-day return weak-tape definition (the 5/20-day versions
  are in the neighbourhood);
- the 20-day realised-vol versus 1-year-median stress filter;
- the 10:00 `r30 < 0` confirmation, the "price below the open" condition, and
  the "gap still open" condition (price above the prior close);
- the OR-high stop with a 0.2% floor and 1.5% cap, the prior-close target, the
  11:30 time stop;
- the 10% annualised vol target and the 10% floor;
- the synthetic linear inverse-QQQ implementation.

If the dev run shows the edge is concentrated in 2020, or the placebos match,
or the neighbourhood has no plateau, the design is retired rather than
re-tuned. If the edge is real but only in the old overlay format, the status is
`retired_overlay_only`.

## 4. Source-to-rule map (quick)

| Rule | Primary source(s) |
|---|---|
| Short only small gap-ups | 1, 2, 3, 4, 5 |
| Exclude large gap-ups (continuation) | 2, 4, 6, 7 |
| Fade the gap direction | 8, 9 |
| 10:00 first-30-minute confirmation | 8, 9, plus own test |
| Stress filter | 9 |
| Opening price is informative | 10, 11, 12 |
| Vol-target sizing | 13, plus own test |
| Costs / borrow | 14, plus brief |
| No 165-day base, no TQQQ, no overnight | 2026-11-26 clarification (rejected source table) |
