# Provenance — what each source supports, and what was not used

**Rule:** a source is listed only if it shaped a rule, an assumption, or a
falsifier. "Inspired" is not the same as "tested and kept". No backtest has been
run for this rebuild yet; the evidence column describes what the source says,
not what this strategy has proven.

---

## 1. Sources that shaped the standalone design

| # | Exact idea / claim | Source | URL | Type | Role | Evidence / use | Confidence |
|---|---|---|---|---|---|---|---|
| 1 | Short-horizon reversal is a liquidity-provision premium: after large short-term declines, expected returns rebound, and reversal profits rise with volatility/liquidity stress. | Nagel (2012), *Evaporating Liquidity* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1988706 | paper | inspired rule | The core of Stream B: buy TQQQ after a sharp 3-day or 1-day QQQ decline, when 10-day/60-day vol is elevated. The paper's mechanism (liquidity provision, VIX-linked reversal returns) is the economic reason to expect a rebound premium, not just "buy the dip". | medium |
| 2 | Short-term reversal profits are concentrated in high-volatility, high-turnover stocks and are consistent with liquidity provision; the effect is not a pure bid-ask bounce. | Da, Liu & Schaumburg (2014), *A Closer Look at the Short-Term Return Reversal* | https://academicweb.nd.edu/~zda/Reversal.pdf | paper | supports assumption | Supports conditioning Stream B on a volatility spike (`vol_ratio >= 1.5`) rather than buying every decline. Also warns that the effect can be microstructure-driven, so the 1 bp/5 bp/10 bp cost ladder is mandatory. | medium |
| 3 | RSI(2)-style oversold dip buying inside an uptrend is a practitioner rule with a fast exit on the bounce. | Connors & Alvarez (2008), *Short Term Trading Strategies That Work* | https://www.amazon.com/Short-Term-Trading-Strategies-That-Work/dp/0071609174 | book | inspired rule (partially) | Inspired the fast dip-buy/exit-on-recovery structure of Stream B. **Not used:** the book's 200-day trend filter, which would violate the no-100–250-day-MA rule. The rebuild uses a 10-day recovery mean and a 3-session time exit instead. | low |
| 4 | Volatility timing: taking less market risk when volatility is high improves the Sharpe ratio of the market portfolio because volatility changes are not matched by proportional expected-return changes. | Moreira & Muir (2017), *Volatility-Managed Portfolios* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431 | paper | inspired rule | The calm-regime condition in Stream A (`vol10` below its trailing 60-day 40th percentile). The rebuild uses the idea as a *state filter* for a 1x QQQ carry, not as a leverage scaler. | medium |
| 5 | Volatility scaling does not improve every factor; the result is fragile across portfolios and specifications. | Cederburg, O'Doherty, Wang & Yan (2020), *On the Performance of Volatility-Managed Portfolios* | https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X | paper | supports assumption (caution) | Justifies the pre-registered falsifier that Stream A must beat BIL at 5 bp on its own. A vol-timing rule that only works at 1 bp is not a premium. | medium |
| 6 | Risk parity / inverse-volatility allocation: equalising risk contributions, and the leverage-aversion explanation for why low-risk assets can have higher risk-adjusted returns. | Asness, Frazzini & Pedersen (2012), *Leverage Aversion and Risk Parity* | https://pages.stern.nyu.edu/~lpederse/papers/LeverageAversionRP.pdf | paper | inspired rule | The inverse-vol allocation across Stream A and Stream B, clipped to [0.20, 0.80]. The paper supports risk-based rather than expected-return-based weights. | high |
| 7 | Naive 1/N and simple risk-based weights are hard to beat out of sample; optimised weights often add estimation error. | DeMiguel, Garlappi & Uppal (2009), *Optimal Versus Naive Diversification* | https://doi.org/10.1093/rfs/hhm075 | paper | supports assumption | Why the allocation is inverse-vol with a wide clip instead of a mean-variance or HRP optimiser. The ±1-step clip neighbourhood tests whether the exact clip matters. | high |
| 8 | A rebalanced blend of two strategies can have a higher geometric return than the weighted average of the components, and the optimal mix can beat either component. | Newfound (2020), *Ensembles and Rebalancing* | https://blog.thinknewfound.com/2020/02/ensembles-and-rebalancing | blog | inspired rule | The reason to test a two-stream blend rather than picking one stream. The falsifier "blend Sharpe must beat the better stream, or blend DD must beat the better stream" is the honest version of this claim. | medium |
| 9 | The rebalancing/diversification return is the difference between the portfolio's growth rate and the weighted average of the constituents' growth rates. | *Diversification Returns, Rebalancing Returns and Volatility Pumping* | https://ssrn.com/abstract=2311240 | paper | supports assumption | Background for why the blend's risk is not the weighted average of the streams' risks. | high |
| 10 | Stop-loss rules can change the tails and the return path; the effect depends on the lookback used to decide, serial correlation, regime and costs, so a stop is not automatically free risk reduction. | *Stop-Loss Strategies with Serial Correlation, Regime Switching, and Transactions Costs* | https://ssrn.com/abstract=2695383 | paper | supports assumption | The Stream-B 8% stop is a risk rule, not an alpha claim. The report must show the stop's event count and the worst gap; the source is the caution that a stop can hurt as well as help. | medium |

## 2. Own-test sources (no external paper)

| Idea / rule | Source | Role | Evidence |
|---|---|---|---|
| The original blend's edge came from the shared 165-day QQQ base, not from the allocation layer. | Own test / no external source (round-2 `winner-ensemble-blend` report and result.json) | motivates the rebuild | Both original sleeves were TQQQ/BIL on the same 165-day gate; the 75/25 blend reproduced the base's return with a smaller drawdown. The blend layer was never tested on independent streams. |
| No 165-day gate, no round-1 4% stop, no old `build_weights`. | Own test / brief section 2 hard rules | constraint | The new streams are built from scratch in `strategy.py`; the old code is read only to understand what not to repeat. |
| 70% QQQ / 30% BIL carry sizing, 20/80 inverse-vol clip, 3-session reversal hold. | Own design choice, not fitted | design | Chosen for risk balance and auditability; the ±1-step table is the test, not the justification. |

## 3. Sources/ideas tested in the original and deliberately not carried over

| Source / idea | URL | Why not used here |
|---|---|---|
| 165-day QQQ regime + armed 4% minute stop (the old winner) | local `research/agents/daily-regime-minute-entry/` | Prohibited shared base. The rebuild uses no 100–250-day price MA and no round-1 stop. |
| 20-day volatility budget + 1-minute crash vote (the old ensemble) | local `research/agents/ensemble-signals/` | It is the same 165-day base with an overlay. The rebuild replaces the daily gate with a 60-day volatility quantile and a 10-day recovery mean. |
| Portfolio drawdown throttling (10/20/30% steps) | original round-2 report, §6.3 | Tested in the original; catastrophic because a 45%-vol strategy is almost always in a >10% drawdown. Not carried over. |
| 38–45% volatility-target overlay | original round-2 report, §6.3 | Tested in the original; failed target #2. Not carried over. |
| SPY as a diversifying asset | local `data/round3/yahoo/SPY-1d-yahoo.parquet` | SPY daily is ~0.99 correlated with QQQ; it adds no independent driver and no local 1-minute SPY history for 2016–2023. Benchmark only. |
| RSI(2) with a 200-day trend filter | Connors & Alvarez (2008) | The 200-day filter is prohibited by the brief. Only the fast dip-buy/recovery-exit concept is used, without the long MA. |

## 4. Data provenance

- QQQ/TQQQ/BIL 1-minute and daily: local `data/intraday-hf/`, adjusted with the
  daily `adjclose/close` factor by `research/bt.py`. No new download.
- SPY daily: local `data/round3/yahoo/SPY-1d-yahoo.parquet` (benchmark only).
- No point-in-time stock universe is used; the strategy is ETF-only, so
  survivorship/delisting is not a concern for the traded assets.
- Development period only: 2016-01-04 → 2023-12-29. The holdout is not read by
  this agent.

## 5. Citation honesty notes

- The Connors book is a practitioner source and its exact RSI(2) rule is **not**
  reproduced; it is cited only for the dip-buy/recovery-exit pattern. Confidence
  is low on purpose.
- Nagel (2012) and Da et al. (2014) are cross-sectional stock-reversal papers.
  This strategy applies the mechanism to an index ETF; that is an extrapolation,
  not a direct replication. The falsifier (bootstrap p-value, event count) is
  there because of this gap.
- Moreira & Muir (2017) is about volatility-managed factor portfolios, not about
  a 60-day volatility quantile on QQQ. The paper motivates the state filter; it
  does not validate the exact threshold. The falsifier "Stream A must beat BIL
  at 5 bp" is the honest test.
- Asness et al. (2012) is about risk parity across asset classes with leverage.
  This rebuild is an unlevered, single-factor, two-stream version. The paper
  supports the weighting principle, not the specific implementation.
