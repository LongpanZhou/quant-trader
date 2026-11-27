# Provenance — `ratio-pairs` rebuild

Every rule and assumption in `HYPOTHESIS.md` / `strategy.py` is listed here with
the source that supports it, or marked as an own test. Confidence is about the
source's support for the specific claim, not about the strategy's profitability.

## Data

| item | source | notes |
|---|---|---|
| QQQ / TQQQ / BIL 1-minute, adjusted | `data/intraday-hf/`, loaded by `research/bt.py` | regular session, 500-day warmup, dividend/split factors from the daily Yahoo archive; the same panel used by the original |
| SPY daily | `data/round3/yahoo/SPY-1d-yahoo.parquet` + `SOURCE.md` | benchmark only; the local Dukascopy SPY 1-minute cache covers only 2026-08-31..2026-11-20 |
| No other assets | directory audit, 2026-11-26 | no sector/bond/gold/vol intraday history locally; no new data fetched |

## Sources

### 1. The ratio identity (the core of the idea)

- **Avellaneda & Zhang (2010), "Path-Dependence of Leveraged ETF Returns",
  SIAM J. Financial Mathematics.**
  <https://epubs.siam.org/doi/10.1137/090760805>
  Also the author PDF:
  <https://math.nyu.edu/inmemoriam/avellaneda/LETFRISKPROF.pdf>
  - *Claim used:* `L_t/L_0 = (S_t/S_0)^b · exp((b−b²)/2 · V_t + financing)`,
    with `V_t` the realised variance. For `b = 3`, `log(TQQQ/QQQ) =
    2·log(QQQ) − 3·V_t`, so the ratio's detrended level is a joint measure of
    how far QQQ has run and how little variance it took.
  - *Role:* inspired the signal and the `dv = 3·dq − dt` variance proxy.
  - *Confidence:* high (the formula is stated and tested on 56 LETFs).

- **Cheng & Madhavan (2009), "The Dynamics of Leveraged and Inverse
  Exchange-Traded Funds".**
  <https://www.researchgate.net/publication/228231757>
  - *Claim used:* daily re-leveraging creates a path-dependent payoff; the
    drag is a real cost for buy-and-hold holders; rebalancing can amplify
    end-of-day volatility.
  - *Role:* supports the assumption that 3x exposure is not a free scaling of
    QQQ and that the drag term is economically meaningful.
  - *Confidence:* medium (abstract/metadata read; the web page's SSRN 1393995
    link was not verified).

- **Adjusted Close, "Leveraged ETF 'Decay' Is Not What You Think It Is".**
  <https://adjustedclose.com/leveraged-etf-decay>
  - *Claims used:* TQQQ/QQQ realised daily beta 2.957; theoretical drag
    `≈ ½·L·(L−1)·σ² = 3σ²` for 3x; the volatility break-even is near 14%
    realised vol for 3x funds; TQQQ's financing + fee gap is ≈7.23%/yr.
  - *Role:* supports the "do not hold 3x in the middle state" rule and the
    scale of the drag used in `dv`.
  - *Confidence:* medium (single blog, but with a transparent methodology and
    a 16–18-year sample).

- **Trainor (2025), "Beyond Volatility Decay: Correcting Relative Expected
  Return Estimates for Leveraged ETFs", JRFM 19(1):20.**
  <https://www.mdpi.com/1911-8074/19/1/20>
  - *Claim used:* LETF expected returns are state-dependent; the provider
    formula misstates them by large amounts depending on the return/volatility
    environment.
  - *Role:* supports conditioning the leverage decision on the variance state
    rather than holding 3x permanently.
  - *Confidence:* medium (abstract read).

### 2. Why froth is dangerous (the crash mechanism)

- **Brunnermeier & Sannikov (2014), "A Macroeconomic Model with a Financial
  Sector", American Economic Review 104(2).**
  <https://www.aeaweb.org/articles?id=10.1257%2Faer.104.2.379>
  - *Claim used:* the "volatility paradox" — low measured risk leads to higher
    endogenous leverage, which makes the system more prone to volatility
    spikes. A calm, strongly trending market is when fragility builds.
  - *Role:* the economic reason a high ratio extension should predict poor
    forward returns and fat left tails, not continued outperformance.
  - *Confidence:* high (theory paper; the mechanism is canonical).

- **NY Fed, Liberty Street Economics (2017), "The Low Volatility Puzzle: Are
  Investors Complacent?".**
  <https://libertystreeteconomics.newyorkfed.org/2017/11/the-low-volatility-puzzle-are-investors-complacent/>
  - *Claim used:* "low volatility in itself can be a catalyst for high future
    volatility" via VaR/margin/leverage feedback.
  - *Role:* plain-language support for the froth → cash state.
  - *Confidence:* high.

### 3. The variance-state risk control

- **Moreira & Muir (2017), "Volatility-Managed Portfolios", Journal of
  Finance 72(4).**
  <https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.12513>
  - *Claim used:* scaling exposure by lagged realised variance improves
    Sharpe ratios for the market and several factors because variance is
    forecastable and not offset by proportional expected-return changes.
  - *Role:* supports standing aside when the ratio-implied variance is
    expanding (`stress > 1.75`).
  - *Confidence:* high for the published result.

- **Cederburg, O'Doherty, Wang & Yan (2020), "On the performance of
  volatility-managed portfolios", Journal of Financial Economics 138(1).**
  <https://doi.org/10.1016/j.jfineco.2020.04.015>
  - *Claim used:* in a broader sample of 103 strategies, volatility-managed
    portfolios do **not** systematically beat their unmanaged counterparts in
    direct Sharpe comparisons, although spanning alphas are positive.
  - *Role:* counter-evidence; the stress rule must earn its place in the
    ablation, not be assumed to work.
  - *Confidence:* high.

- **Downside-risk paper (2021), "Downside risk and the performance of
  volatility-managed portfolios", Journal of Banking & Finance.**
  <https://www.sciencedirect.com/science/article/abs/pii/S0378426621001576>
  - *Claim used:* downside-volatility scaling outperforms total-volatility
    scaling; the effect is return timing.
  - *Role:* supports using a variance-expansion (downside) trigger rather than
    a symmetric vol target.
  - *Confidence:* medium (abstract read).

### 4. Benchmarks and context (not the rule)

- **FinLab (2026), "TQQQ 200-Day Moving Average Strategy".**
  <https://finlab.finance/en/blog/leveraged-etf-timing-backtest>
  - *Claims used:* the QQQ 200-day rule on TQQQ made 45.1% CAGR with a −60.9%
    drawdown, 2017–2026; 6 of 8 exits saw TQQQ rise while out.
  - *Role:* benchmark context for the banned base; the whipsaw evidence is a
    reason not to rebuild around a slow price gate.
  - *Confidence:* high for the numbers quoted (same data era).

- **Exent (2026), "TQQQ and the 200-Day Moving Average: An Exit Rule,
  Tested".**
  <https://www.exent.ai/resources/leveraged-etf-200-day-rule>
  - *Claims used:* 46.4% vs 42.5% CAGR, −54.8% vs −81.6% drawdown, 34 switches;
    the 2025 tariff selloff was −56.7% held vs −26.9% with the rule.
  - *Role:* benchmark context; the slow-rule failure in fast crashes motivates
    the ratio/variance state instead of a price MA.
  - *Confidence:* medium.

### 5. Tested and not used

- **Hessel, Nam, Wang, Cunyu & Zhang (2017), "Shorting Leveraged ETF Pairs"
  (CXO Advisory summary).**
  <https://www.cxoadvisory.com/volatility-effects/monthly-rebalanced-shorting-of-leveraged-etf-pairs/>
  - *Claim:* long/short LETF pair spreads mean-revert, and the profit is a bet
    on index mean reversion that dies in trends.
  - *Why not used:* I tested the mean-reversion implication at daily and
    intraday frequency in the original work. The daily deciles had no signal
    (next-day TQQQ − 3×QQQ excess was −2 to −6 bp in every decile); the
    intraday 5-minute fade had a 72.7% event-study hit rate but vanished under
    next-bar fills. Also, `bt.simulate` rejects negative weights, so a
    long/short pair cannot be modelled in this harness.
- **Slow 200-day price rules** (FinLab/Exent): banned by the revisit brief and
  shown to whipsaw; benchmark only.
- **A 165-day QQQ regime of any kind:** banned; not present in the code.

### 6. Own tests (no external source)

- **The 200-session detrend of the ratio and the `0.20 / −0.30` thresholds.**
  Chosen from the exploratory dev buckets and the original report's surface,
  not from a published result. This is a model choice; the report must show
  the ±1-step neighbourhood and the plateau.
- **The `dv` construction** `3·log(QQQ_t/QQQ_{t−1}) − log(TQQQ_t/TQQQ_{t−1})`
  is the discrete form of the Avellaneda–Zhang identity, but the specific
  use of its 20/60-day ratio as a switch is my own.
- **The dev evidence in section 2 of the report** came from
  `explore.py`/`explore2.py` runs made before the 2026-11-26 test pause. They
  are single-run, unaudited and not reproducible from the final `strategy.py`
  until the lead authorises a run.
- **Expected correlation 0.45–0.58** is an extrapolation from those
  exploratory runs, not a measured property of the final code.

## What would change this provenance

If the audited run shows the ratio states add nothing over always-QQQ, the
honest conclusion is that the extracted idea was **overlay-only** and the
strategy should be retired, regardless of the literature above. The sources
support the *mechanism*; they do not prove the *timing rule*.
