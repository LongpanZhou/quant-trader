# Provenance — `risk-parity-hrp` rebuild (VSRP)

Every rule is mapped to a source or explicitly marked **own design**. Sources
were reviewed at abstract/summary level during design (search on 2026-11-26);
none of the papers' strategies were re-implemented. No URL is invented: each one
comes from the search results, the repo's existing paper list, or an earlier
report in this repo.

## 1. Rule → source map

| Rule / claim | Source | Role | What exactly it supports | Confidence |
|---|---|---|---|---|
| Weight assets by risk contribution, not capital | Asness, Frazzini & Pedersen (2012), *Leverage Aversion and Risk Parity* | inspired rule | Leverage-averse investors overpay for levered assets; risk-based weighting is the rationale for the ERC QQQ/TQQQ composition. | high |
| ERC weights on two near-perfectly correlated assets reduce to inverse-vol (75/25) | Own derivation from the ERC definition; consistent with Asness et al. | supports assumption | With ρ≈1, ERC weights are wᵢ ∝ 1/σᵢ; this is why the sleeve is 75% QQQ / 25% TQQQ and why it is a leverage choice, not diversification. | high |
| QQQ/TQQQ is one factor at 3x; multi-day returns are path-dependent | Cheng & Madhavan (2009), *The Dynamics of Leveraged and Inverse ETFs* | supports assumption | Daily-reset leverage; the pair is not a second risk premium. Verified locally: 10y daily corr 0.99951, 60d avg 0.99986. | high |
| LETF compounding depends on autocorrelation and regime; mean reversion hurts 3x funds | Hsieh, Chang & Chen (2025), *Compounding Effects in Leveraged ETFs* | supports assumption / caveat | Justifies capping TQQQ at its risk-parity weight and not letting the sleeve become a pure 3x bet; warns that TQQQ's edge is state-dependent. | medium |
| "Volatility decay" is convexity, not a free lunch | Carpenter, Lu & Whitelaw (2026), *In Defense of Leveraged and Inverse Funds* | counter-evidence | Keeps the design from claiming a free drag harvest; motivates the vol cap and the drawdown brake. | medium |
| Scale exposure by trailing realised variance (the rule we invert) | Moreira & Muir (2017), *Volatility-Managed Portfolios* | tested only / benchmark | Defines the pro-cyclical vol-target benchmark. It is *not* the promoted rule: measured dev correlation with the 165-day base is 0.78, so it fails the diversity requirement. | high |
| Vol-managed portfolios often fail out of sample | Cederburg, O'Doherty, Wang & Yan (2020) | counter-evidence | Reason not to trust a pro-cyclical vol rule; motivates testing the opposite sign with a placebo. | high |
| Risk-return trade-off is weak/negative at long horizons; beliefs about vol adjust slowly | *Volatility Expectations and Returns* (NBER w28102, 2020) | supports assumption | The economic basis for damping the contrarian tilt when the long-horizon vol is in a persistent high regime (2022-type). | medium |
| Volatility changes move prices and subsequent expected returns | *The Effect of Volatility Changes on the Level of Stock Prices and Subsequent Expected Returns* (JF, 1991) | supports assumption | Short-horizon overreaction/mean-reversion channel that the transient-spike tilt tries to harvest. | medium |
| Post-spike forward returns are elevated; the effect decays over weeks | La Manna (2025), *Volatility Regime Transitions and Equity Return Decoupling*; JOC 32(4) 2021 VIX-jump study | supports assumption | Supports the 20-day event horizon and the short (20d) vs long (120d) vol split used in the slope. Both are recent/weak evidence, not peer-reviewed consensus. | low |
| Exact windows (20/120/60), slope scale 0.35, 70% damper, base 35%, tilt 0.20, vol cap 18%, DD thresholds, clips, warm-up | **Own design / no external source** | own design | Chosen as round numbers from the hypothesis, not fitted. The ±1-step neighbourhood is the test. | — |

## 2. Rejected sources / rejected rules

| Source or rule | URL | Why rejected |
|---|---|---|
| López de Prado (2016), HRP | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678 | Implemented in full during the original agent (single linkage, quasi-diagonalisation, recursive bisection) on 60-day covariances of QQQ/TQQQ/BIL. It allocated **99.99% to BIL** (QQQ 0.0089%, TQQQ 0.0010%). HRP is a valid general method but degenerate on a set that contains a near-riskless asset. Not used. |
| Naive risk parity / ERC across QQQ, TQQQ and BIL | Own test, no external source | ERC across the three gives 1.03% QQQ / 0.34% TQQQ / 98.63% BIL: a T-bill portfolio with no equity premium. Rejected by construction, before any backtest. |
| Pro-cyclical volatility targeting as the *rebuild* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431 | Not rejected as a published result — rejected for this brief on measurement: all variants correlated **0.71–0.83** with the 165-day base on dev, above the 0.60 limit. Kept only as the inverted benchmark. |
| A price moving-average gate in any form (165d or renamed 100–250d) | — | Forbidden by the brief and, empirically, the source of the shared base: it is what makes 26 strategies correlate at 0.86. Not used anywhere in the rebuild. |

## 3. Data provenance

| Data | Path | Role | Note |
|---|---|---|---|
| QQQ / TQQQ / BIL 1-minute, adjusted, regular session | `data/intraday-hf/` via `bt.load_1m` | tradable universe + marks | BIL reverse-split adjustment is handled in `bt.load_1m`. |
| SPY daily | `data/round3/yahoo/SPY-1d-yahoo.parquet` | benchmark only | `data/round3/yahoo/SOURCE.md` explicitly forbids using it as a tradable asset: no SPY intraday history for the dev window. |
| 165-day baseline | built in `strategy.py::baseline_weights` | comparison / correlation only | Never an input to the strategy. |

No bond, gold or volatility-product history exists locally, so the risk-parity
universe cannot be extended beyond a single equity factor plus cash. That is the
main external-validity limitation of this rebuild and is stated in the report.

## 4. What is genuinely new here

The **contrarian volatility-state risk budget** — raising the risk budget on a
*transient* 20d-vs-120d vol spike while damping the raise when the 120d vol is
itself in a persistent high regime — is an own hypothesis. It is *not* a
published rule. The literature above supplies the mechanism (overreaction,
slow-moving vol beliefs, weak long-horizon risk-return trade-off) but no paper
tests this exact allocation rule. If the placebo and ablation tests kill it, the
correct conclusion is that the hypothesis is wrong, not that the sources are.
