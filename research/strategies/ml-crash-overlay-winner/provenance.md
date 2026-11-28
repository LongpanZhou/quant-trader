# Provenance — ML crash-day classifier → leverage-decay timing

**Rule:** every rule or claim below has a source entry, or is explicitly marked
`Own test / no external source`. The distinction between *inspired the rule*,
*supports an assumption*, and *tested and rejected* is kept explicit.

## A. Idea → source table

| # | Idea / claim it supports | Source | URL | Type | Role | What exactly supports it | Confidence |
|---|---|---|---|---|---|---|---|
| 1 | TQQQ's long-run return is path-dependent: `log LETF ≈ k·log index − k(k−1)/2 · Σr²`, so decay rises with realized variance | Avellaneda & Zhang (2010), *Path-Dependence of Leveraged ETF Returns*, SIAM J. Financial Mathematics 1(1):586–603 | https://epubs.siam.org/doi/10.1137/090760805 | paper | **inspired rule** | Derives the exact leveraged-ETF return formula and validates it on 56 LETFs; the `−3·Σr²` term is the economic basis for the `decay5` label and the TQQQ/QQQ choice | high |
| 2 | Daily re-leveraging makes LETFs path-dependent and unsuitable for passive buy-and-hold; returns can be destroyed by high volatility | Cheng & Madhavan (2009), *The Dynamics of Leveraged and Inverse Exchange-Traded Funds*, Journal of Investment Management 7(4) | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995 | paper | **supports assumption** | Shows the embedded path-dependent option and value destruction in high-vol paths; motivates treating TQQQ as a *conditional* instrument rather than a permanent holding | high |
| 3 | The decay is large in practice: at QQQ 22.3% annualized vol, a 3× fund loses roughly 15 pp/year to the variance term | FinLab, *Leveraged ETF Decay: Volatility Drag and Costs in 14 Funds* | https://finlab.finance/en/blog/leveraged-etf-decay | blog | **supports assumption** | Empirical decomposition of TQQQ vs 3× QQQ; the measured 15.2 pp/year matches the `k(k−1)/2·σ²` approximation and shows the effect is economically large | medium |
| 4 | Leveraged and inverse ETFs are not buy-and-hold products; compounding and daily reset create risks | SEC/FINRA, *Updated Investor Bulletin: Leveraged and Inverse ETFs* | https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-alerts/sec-finra | report | **supports assumption** | Regulator's plain-language warning on compounding and path dependence; supports the decision to hold TQQQ only in the low-decay state | high |
| 5 | Walk-forward validation with a purge at the train/test boundary | Arnott, Harvey & Markowitz (2019), *A Backtesting Protocol in the Era of Machine Learning* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3275654 | paper | **supports assumption** | Protocol for out-of-sample ML backtests; the model retrains annually on data strictly before the test year and purges 6 sessions | high |
| 6 | Overlapping labels are not independent; purge/embargo and do not treat every row as a sample | López de Prado (2016), *The 10 Reasons Most Machine Learning Funds Fail* | https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf | paper | **supports assumption** | Label design and non-IID warnings; the 5-session label is purged by 6 sessions and the model uses a 750-session rolling window | high |
| 7 | Backtest overfitting and multiple testing require a placebo and a full parameter plateau | Bailey, Borwein, López de Prado & Zhu, *The Probability of Backtest Overfitting* | https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf | paper | **supports assumption** | The evaluation plan reports a ±1-step neighbourhood and a 300-draw random-state placebo rather than a single best backtest | high |
| 8 | Rare-event crash classifiers are genuinely hard; honest OOS AUC/PR-AUC is often near the base rate | Detection of extreme market events using Machine Learning (GitHub) | https://github.com/addicteduser04/Detection-of-extreme-market-events-using-Machine-Learning | report | **tested only** | Reports PR-AUC 0.063 for Random Forest over 5,294 OOS predictions with 24 positives; used to calibrate the expectation that the decay classifier may have little skill | high |
| 9 | A simple logistic crash model can fail to beat the naive base rate out of sample | *Forward Logistic Analysis, 1994–2025*, Journal of Accounting and Finance Research | https://rjwave.org/jaafr/papers/JAAFR2609192.pdf | paper | **supports assumption (negative benchmark)** | OOS AUC 0.631 vs 0.648 for the naive expanding base rate; motivates the pre-registered falsifier "AUC ≤ 0.55 → retire" | high |
| 10 | Walk-forward crash prediction with expanding windows and quantile labels is an established protocol | *Predicting S&P 500 Market Crashes: A Comparative Study of Machine Learning and Traditional Statistical Models* (ACM, 2026) | https://dl.acm.org/doi/full/10.1145/3829441.3829559 | paper | **supports assumption** | Uses a 5-day cumulative-return crash label and expanding-window folds; the protocol, not the reported high AUC, informed the walk-forward design | medium |
| 11 | Sequential walk-forward crisis forecasting with a compact feature set | *Stock Market Crisis Forecasting Using Neural Networks with Input Factor Selection* (MDPI, 2021) | https://www.mdpi.com/2076-3417/12/4/1952 | paper | **supports assumption** | Sequential re-estimation for crisis months supports annual retraining and a compact, economically motivated feature set | medium |
| 12 | The exact three-state TQQQ/QQQ/BIL mapping, the 15/75 thresholds, the 5-session minimum hold and the 25th-percentile label | **Own test / no external source** | — | — | **inspired rule** | This is the new hypothesis. No source specifies this rule; it is derived from the decay formula and the pre-registered falsifiers in `report.md` | — |
| 13 | The original 20-session absolute crash classifier and its diagnostics (AUC 0.225–0.757, ex-2020 50.0%, 2026-only 5y edge, placebo p95 65.7%) | **Own test / no external source** — `research/agents2/ml-crash-overlay-winner/result.json` and conversation history | — | report | **inspired rule / negative evidence** | The original classifier is the starting point; its instability is why the rebuild uses a *relative decay* label and a QQQ default instead of a TQQQ base | high |
| 14 | Walk-forward logistic protocol (standardisation, median imputation, 750-session window, annual retrain, purge) | **Own test / no external source** — round-1 `research/agents/ml-classifier` | — | report | **inspired rule** | The protocol is reused conceptually, not the code or the base weights; the original `build_weights` is not called or copied | high |
| 15 | The 165-day QQQ/TQQQ baseline used **only** for the correlation benchmark | **Own test / no external source** — round-1 `research/agents/daily-regime-minute-entry` | — | report | **benchmark only** | The baseline is computed separately and is never used as a gate, a feature, or a weight source; it exists solely to measure the < 0.60 correlation requirement | high |

## B. Rejected sources and rejected design choices

| Source / choice | URL / location | Why rejected |
|---|---|---|
| 165-day QQQ SMA as a gate | Round-1 `daily-regime-minute-entry` | The brief forbids any 100–250-day MA gate; the rebuild must stand on the ML state alone |
| Old 20-session absolute crash label (`TQQQ < −15%`) | Original `research/agents2/ml-crash-overlay-winner` | OOS AUC was unstable and the P&L was concentrated in 2020/2026; the relative `decay5` label targets the actual TQQQ/QQQ choice instead |
| Next-day crash classifier at the close | Original development history | Weak 5y CAGR/drawdown; the 5y failed both the return and drawdown floors |
| Multi-horizon TQQQ-vs-BIL underperformance model (5/10/20) | Original development history | Bottom-quintile exits cut CAGR too much; no pass |
| Overnight-only 15:50 gap hedge | Original development history | 10y drawdown 47.60% vs the winner's 44.56%; only the 5y improved |
| Long/short TQQQ/QQQ pair | Design-stage idea | `bt.py` is long-only; a private short simulator is not allowed by the brief. The long-only three-state version is the implementable form |
| SPY, sector, bond, gold, vol products | Local data | Historical 1-minute data is not local (only a 2026 dukascopy SPY cache); adding new data requires a `SOURCE.md` and is deferred. QQQ/TQQQ/BIL support the decay thesis directly |
| *CRISIS ALERT: Forecasting Stock Market Crisis Using Machine Learning* (arXiv 2401.06172) | https://arxiv.org/pdf/2401.06172v1.pdf | Monthly crisis classification with very high AUC claims; incompatible with a 5-session daily ETF rotation; not used |

## C. What would count as new evidence

The following are **not** sources and must not be presented as such; they are the
pre-registered tests that will decide whether the hypothesis survives:

1. OOS AUC of the decay classifier on the development window.
2. Dev 1/5/10 bp CAGR, max drawdown, Sharpe, fills and exposure.
3. Daily-return correlation with the 165-day baseline and with TQQQ/QQQ.
4. State-conditional realized `decay5` (TQQQ state vs QQQ state) and a block
   bootstrap p-value.
5. The ±1-step parameter plateau, sub-period results and 300-draw placebo.
6. The lead's one-time holdout run after the strategy is frozen and audited.
