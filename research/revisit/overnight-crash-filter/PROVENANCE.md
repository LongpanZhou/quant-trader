# Provenance — `overnight-crash-filter` rebuild

Every rule in the rebuilt strategy is mapped to a source or to an explicit
"own test / no external source". Roles: **inspired rule** (the source supplies
the mechanism), **supports assumption** (corroborates a premise but no parameter
is taken), **benchmark**, **tested only**, **rejected**.

## 1. The overnight premium exists and is a risk premium

| Claim used | Source | URL | Role | Confidence |
|---|---|---|---|---|
| The US equity premium is earned close-to-open, not open-to-close | Cliff, Cooper & Gulen (2008), *Return Differences between Trading and Non-Trading Hours: Like Night and Day* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081 | inspired rule | high |
| Overnight and intraday returns are driven by different clienteles; riskier/high-beta names earn their premium overnight | Lou, Polk & Skouras (2019), *A Tug of War: Overnight versus Intraday Expected Returns*, JFE 134(1) | http://www.econ.yale.edu/~shiller/behfin/2015-04-11/lou_polk_skouras.pdf | inspired rule | high |
| The overnight drift is large and persistent across assets | Haghani, Ragulin & Dewey (2022), *Night Moves* (JOIM 2024) | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4139328 | supports assumption | high |
| Expected overnight returns rise with the variance of the risky asset / end-of-day VIX, because market makers demand compensation for holding risk while closed | Bondarenko & Muravyev (2021), *Market Return Around the Clock: A Puzzle*, NY Fed Staff Report 917 | https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf | inspired rule (vol scaling) | high |
| The conditional equity premium mainly compensates for risk and illiquidity **during market closures** | *Give me a break: What does the equity premium compensate for?* (2025), International Review of Financial Analysis 99 | https://ideas.repec.org/a/eee/intfin/v99y2025ics1042443124001690.html | supports assumption (size on overnight risk, not total risk) | medium |

Note on the last two: they cut against a naive "skip high volatility" rule. If
the overnight premium is compensation for overnight risk, then higher overnight
vol should mean a *higher* expected overnight return, not a lower one. The
rebuild therefore **scales** the overnight position with a gap budget instead of
blanket-skipping volatile nights, and only switches off at an extreme ceiling
where the fat-tail/jump component dominates (see §3).

## 2. The block-conditional signal: night continuation, day reversal

| Claim used | Source | URL | Role | Confidence |
|---|---|---|---|---|
| Intraday returns reverse the prior overnight return ("the day destroys the night"); overnight returns continue the prior intraday return ("night extends the day"). Regression of intraday on past overnight: coefficient negative, t = -5.67, R² ≈ 13% | *The Day Destroys the Night, Night Extends the Day* (2023), Carlo Alberto working paper | https://www.carloalberto.org/wp-content/uploads/2023/01/Day-Destroys-The-Night-Night-Extends-The-Day.pdf | inspired rule (the core signal) | medium |
| Return persistence/reversal across the close-open boundary is a robust decomposition result, not a single-market artefact | Lou, Polk & Skouras (2019) (short-term reversal earns overnight); Aboody, Even-Tov, Lehavy & Trueman (2018), *Overnight Returns and Firm-Specific Investor Sentiment*, JFQA | https://anderson-review.ucla.edu/wp-content/uploads/2021/03/Aboody-et-al_overnight_returns_and_firmspecific_investor_sentiment_JFQA2018.pdf | supports assumption | medium |
| Large overnight gaps revert within the first 30 minutes of the session | Concretum Group, *Beat the Market: An Effective Intraday Momentum Strategy for the SPY* | https://concretumgroup.com/backtesting-7-years-of-free-data-beat-the-market-an-effective-intraday-momentum-strategy-for-the-sp500-etf-spy | supports assumption (day leg) | medium |

The day-leg signal is the *sign of the overnight gap*, not its size. Restricting
it to large gaps (|gap| > 2%) would turn it into a ~20-trade-per-decade event
strategy with fat-tail dependence and it would collide with the separate
`gap-capitulation-reversal` rebuild; the broad version is the pre-registered
base and the size-conditioned version is an explicit falsifier, not a variant.

## 3. Why a gap budget rather than a stop or a moving average

| Claim used | Source | URL | Role | Confidence |
|---|---|---|---|---|
| Overnight returns have a larger jump/fat-tail component than intraday returns; intraday volatility is higher per hour but overnight surprises dominate | CFM, *The Fine Structure of Volatility Feedback II: Overnight and Intra-Day Effects* (2013) | https://www.cfm.com/wp-content/uploads/2022/12/273-2013-The-fine-structure-of-volatility-feedback-II-overnight-and-intra-day-effects.pdf | supports assumption | high |
| Per-hour intraday volatility is roughly 2-3x overnight volatility, and the day/night ratio is stable over time (1.5-3.5 for the S&P) | Muravyev & Ni (2019), *Why Do Option Returns Change Sign from Day to Night?*, JFE | https://www.sciencedirect.com/science/article/abs/pii/S0304405X19302193 | tested only (I considered and rejected a day/night variance-ratio timing signal because the ratio is stable) | high |
| Leveraged ETFs reset daily and inherit the overnight gap at roughly 3x; a price stop cannot act during the gap | Cheng & Madhavan (2009), *The Dynamics of Leveraged and Inverse ETFs* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995 | supports assumption (3x leg, gap sizing) | high |
| Volatility decay of TQQQ is concentrated in high-vol days | FinLab, *Leveraged ETF Decay: Volatility Drag and Costs in 14 Funds* | https://finlab.finance/en/blog/leveraged-etf-decay | supports assumption (vol ceiling) | medium |

A stop is the wrong tool for a gap: the stop is only observable after the gap
has already printed. The rebuild replaces the old 4% stop with an **ex-ante gap
budget**: position size = budget / (z x forecast overnight vol). That is the
literal meaning of "overnight crash filter" — cap what a 3-sigma gap can cost.

## 4. Ideas considered and rejected

| Idea | Why rejected |
|---|---|
| Day/night variance-ratio rotation (hold the block with the higher variance share) | Muravyev & Ni show the day/night variance ratio is stable (1.5-3.5); a stable ratio cannot time blocks. The *level* of vol is the usable state variable. |
| Large-gap-only day leg (gap < -2%) | ~20 events per decade, fat-tail driven, and overlaps the separate `gap-capitulation-reversal` rebuild. Kept as a diagnostic, not the base. |
| 165-day QQQ regime | Explicitly excluded by the brief; it is the old shared base. |
| Round-1 4% armed stop | Overlay of the old base; a stop cannot see an overnight gap. Replaced by ex-ante sizing. |
| Overnight-only with a binary vol skip (my round-2 v1) | This is the "strip the base" failure mode the clarification warns about: same block, same asset, binary filter. The rebuild adds a second block (day reversal), a second asset (QQQ), a continuous risk budget and a conditional signal. |

## 5. Own tests / no external source

| Rule | Status |
|---|---|
| Vol window = 20 days | Own choice, standard RiskMetrics horizon; neighbourhood 10/20/40 reported. |
| Vol ceiling = 40% annualised QQQ | Own choice; plateau 35/40/45 reported. |
| Gap budget = 4% of equity per 3-sigma move | Own choice; plateau 3/4/5/6% reported. |
| Day-leg scale = 0.5 | Own choice reflecting lower conviction; 0.25/0.5/0.75 reported. |
| Dev sample 2016-01-04..2023-12-29 | Brief. |
| QQQ/TQQQ/BIL universe | Data constraint: only these three have local 1-minute history from 2016. SPY intraday under `data/cache/dukascopy/SPY` starts 2026-08-31 (7 weeks) and cannot support a 2016-2023 development test; no sector, bond, gold or volatility-product intraday data is present locally. |
