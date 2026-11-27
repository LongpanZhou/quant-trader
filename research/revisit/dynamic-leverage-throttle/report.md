> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Volatility-Shock Recovery (VSR) — standalone rebuild of `dynamic-leverage-throttle`

**Slug:** `dynamic-leverage-throttle`
**Status:** **DESIGN ONLY — backtests paused (2026-11-26).** No `result.json`
has been produced, no `bt.run`/`bt.run_many` has been run for this version, and
no performance number below is a result. The pre-pause exploratory numbers in
§2 are labelled as such: they motivated the redesign and are not the candidate.

---

## 1. The idea extracted from the original

The original strategy's genuinely new element is **volatility-targeted leverage
sizing**: TQQQ is sized inversely to its own realised volatility
(`0.30 + 0.70 × min(1, 0.65/vol20)`) instead of being held at a constant 100%.
Everything else — the 165-day QQQ SMA regime, the 30% permanent core, the armed
4% minute stop — belongs to the shared round-1 base.

The rebuild keeps the inverse-vol risk budget but makes volatility **own the
whole position**. It does not strip the old base and call the residue a
strategy: it replaces the trend gate with a volatility-state entry, changes the
holding period from daily to weeks, removes the core and the minute stop, and
uses volatility both to enter/exit and to set the weight.

## 2. Why the direct strip does not work (pre-pause evidence)

A development-only exploration was run before the pause
(2016-01-04..2023-12-29, 1 bp, 2% band, 1-minute marks). It is not audited and
is not the candidate. It showed why a continuous vol-target rebuild cannot pass
the independence rule:

| Variant | Dev CAGR / max DD | Corr vs 165d base |
|---|---:|---:|
| 165d base (benchmark) | 44.76% / 58.76% | 1.00 |
| Continuous inverse-vol TQQQ, 20–60% target | 22.5–45.7% / 31.6–69.8% | 0.79–0.82 |
| Continuous TQQQ→QQQ vol rotation | 31.1–41.1% / 41.1–48.2% | 0.76–0.81 |
| Vol gate to BIL, 45–50% threshold | 17.3–26.6% / 39.3–42.9% | 0.47–0.54 |
| Vol gate to QQQ, 40–60% threshold | 25.8–39.4% / 40.6–44.2% | 0.71–0.79 |
| Vol target with a hard ceiling (≤60% vol) | 24.3–28.6% / 30.2–34.4% | 0.64–0.65 |
| Drawdown gate (`dd252 > −10%`) | 18.5% / 38.1% | 0.55 |

The lesson: any **always-on** TQQQ/QQQ exposure correlates about 0.8 with the
old base, because the base is long TQQQ in exactly the calm periods when a
continuous vol target is also long. A binary vol gate gets under 0.60 only by
sitting in BIL most of the time, and its return is weak. The rebuild therefore
changes the *state* in which the strategy is long: it is long after a
volatility shock, when the old base is usually out, and in BIL during calm
uptrends when the old base is in.

## 3. Standalone hypothesis

**H1.** After a volatility shock, the *decay* of short-horizon realised
volatility marks the end of forced deleveraging. When the market is also in a
drawdown, the following 2–8 weeks have positive convexity that TQQQ can
capture. Sizing the position inversely to the still-elevated volatility keeps
the risk budget roughly constant. The resulting strategy should have a
respectable return with a daily correlation well below 0.60 to the 165-day
trend base.

**H2 (why the state is different).** The signal is the joint state

```
v20 ≥ 1.25 · v60          (a genuine volatility shock)
v5  ≤ 0.85 · v20          (the shock is decaying)
−35% ≤ dd252(QQQ) ≤ −8%   (fear to recover from, but not a >35% catastrophe)
```

The old base is usually **out** in this state; VSR is **in**. In calm uptrends
VSR is in BIL and the base is in TQQQ. The return drivers are close to
orthogonal.

**H3 (sizing).** `w_TQQQ = min(0.75, 0.30 / v20)`; BIL for the rest. This is
the original inverse-vol idea, but it is the entire position, not a tilt on a
100% TQQQ book.

## 4. Universe, data and holding period

| Item | Choice | Why |
|---|---|---|
| Signal asset | QQQ daily close | Drawdown from the 252-session high |
| Risk asset | TQQQ | The original instrument; 3× QQQ |
| Cash | BIL | Local T-bill proxy; earns its own return |
| Data | Local adjusted 1-minute QQQ/TQQQ/BIL, 2016-01-04..2023-12-29 | Only tradable intraday data present; no new downloads while paused |
| SPY | Daily only, `data/round3/yahoo/SPY-1d-yahoo.parquet` | `SOURCE.md` restricts it to the buy-and-hold benchmark; no SPY 1m for 2016–2023 |
| Signal timing | Daily close `t` | All indicators use data through `t` only |
| Fill timing | Next bar open (09:31 for the first bar of `t+1`) | `bt.py` convention; no same-bar fill |
| Holding period | Episodic, 2–8 weeks | Vol-normalisation / recovery / time stop, not a daily rebalance |
| Rebalance | Every 5 sessions while held | Keeps the holding period distinct; lower turnover |
| Leverage | Max 75% TQQQ; no shorting | Long-only, gross ≤ 1 |

SPY daily exists at `data/round3/yahoo/SPY-1d-yahoo.parquet` (2015–2026), but
its `SOURCE.md` restricts it to the buy-and-hold benchmark: there is no SPY
1-minute history for 2016–2023, so it cannot be a tradable asset in a
1-minute-marked strategy. Sector, bond, gold and volatility-product data are
not present locally. The design does not pretend to use them. If the data
subagent adds a point-in-time intraday SPY or sector panel later, a robustness
variant can use it, but it is not part of the pre-registered primary.

## 5. Exact pre-registered rules

Let `v5`, `v20`, `v60` be the annualised standard deviations of TQQQ daily
close-to-close log returns over 5/20/60 sessions, using data through the close
of session `t`. Let

```
dd252_t = QQQ_t / max(QQQ over the last 252 sessions) − 1
```

**Entry** (flat and past the cooldown), evaluated at the close of `t`:

1. `v20_t ≥ 1.25 × v60_t` (vol shock);
2. `v5_t ≤ 0.85 × v20_t` (shock decaying);
3. `−0.35 ≤ dd252_t ≤ −0.08` (fear, not a >35% catastrophe);
4. all inputs finite.

At the next session's open, buy `w = min(0.75, 0.30 / v20_t)` TQQQ; the rest is
BIL.

**While held:**

- Re-size every 5 sessions to `min(0.75, 0.30 / v20_t)`.
- Exit at the close of `t` (fill next open) if any of:
  - `v20_t ≤ 1.05 × v60_t` (vol normalised);
  - `dd252_t ≥ −0.03` (recovered to within 3% of the high);
  - `v5_t ≥ 1.10 × v20_t` (vol re-accelerating);
  - `dd252_t ≤ −0.40` (catastrophe stop);
  - 60 sessions held (time stop).
- After an exit, wait 5 sessions before a new entry (cooldown).

No 165-day moving-average gate, no 30% core, no 4% minute stop, no shorting.

### Parameters and neighbourhood

| Parameter | Primary | ±1-step grid |
|---|---:|---|
| `shock_mult` | 1.25 | 1.15 / 1.25 / 1.35 |
| `decay_ratio` | 0.85 | 0.80 / 0.85 / 0.90 |
| `dd_entry` | −8% | −6% / −8% / −10% |
| `target_vol` | 30% | 25% / 30% / 35% |
| `time_stop` | 60 | 40 / 60 / 80 |

The primary is the round middle. It is promoted only if it sits inside a
plateau: at least 2/3 of the 3×3×3×3×3 neighbourhood has the same CAGR sign and
correlation below 0.60, and the primary is not the single best cell.

## 6. Risk and sizing

- The weight is `min(0.75, 0.30 / v20)`. At `v20 = 0.60` that is 50%; at
  `v20 = 1.00` it is 30%; at `v20 = 1.50` it is 20%. The cap binds only in
  unusually calm vol, which the entry condition mostly excludes.
- BIL is the residual. There is no cash drag beyond BIL's own return.
- No stop on price. The catastrophe exit is a drawdown-state exit
  (`dd252 ≤ −40%`), not a minute stop.
- No shorting, no borrow cost, no leverage above 100% TQQQ.
- The main tail risk is a renewed crash after entry. The vol-decay condition and
  the 60-session time stop are the protections; the design explicitly does not
  use a price stop, because the round-1 evidence showed the minute stop is part
  of the shared base and because a price stop would re-introduce the old
  timing.

## 7. Expected correlation with the old base

**Pre-registered expectation: 0.15–0.45 daily-return correlation on the
development period.** Rationale:

- VSR is long TQQQ mainly when QQQ is below its 165-day SMA; the base is in BIL
  then.
- VSR is in BIL during calm uptrends; the base is long TQQQ then.
- Overlap is limited to the later part of recoveries, after the base re-enters
  and before VSR's vol-normalisation exit.

A correlation of **0.60 or higher** falsifies the independence claim. If the
first implementation lands at 0.50–0.60, the next step is to shorten the
holding period (exit on `vol_normalised` earlier) or tighten the entry
drawdown, not to add a new filter.

## 8. Falsifiers and pass/fail

| # | Test | Fail if |
|---|---|---|
| 1 | Correlation vs 165d base | ≥ 0.60 |
| 2 | Dev return/risk | CAGR < 8%, or Calmar < 0.50, or max DD > 35% (1m marks) |
| 3 | Event evidence | < 12 entries, or episode bootstrap p > 0.10 |
| 4 | Concentration | 2020 > 80% of total P&L, or both 2016–19 and 2022–23 negative |
| 5 | Ablation | Removing the vol-decay condition performs as well |
| 6 | Neighbourhood | CAGR sign flips or median Calmar < 0.35 in the 3×3×3×3×3 grid |
| 7 | Cost | Edge disappears at 5 bp (10 bp is a caveat) |

Failure of 1, 2, 3 or 6 means `rejected`, not `retired_overlay_only`: the idea
can stand alone, but this implementation did not.

## 9. Provenance

| # | Claim | Source | URL | Role | Evidence / use | Confidence |
|---|---|---|---|---|---|---|
| 1 | Scale exposure inversely to recent variance; vol-managed equity portfolios raise Sharpe | Moreira & Muir (2017), *Volatility-Managed Portfolios* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431 | inspired rule | The `0.30 / v20` risk budget is a capped inverse-vol implementation | high |
| 2 | Volatility targeting improves Sharpe and cuts left-tail/drawdown severity; a slow estimator is preferred | Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert (2018), *The Impact of Volatility Targeting* | https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf | supports assumption | Supports the risk-budget framing and the 20-day core window | high |
| 3 | Volatility-managed portfolios often fail out of sample; temper the rule | Cederburg, O'Doherty, Wang & Yan (2020), *On the Performance of Volatility-Managed Portfolios* | https://doi.org/10.1016/j.jfineco.2020.04.015 | supports assumption | Motivates an episodic, state-dependent use of vol sizing rather than an always-on target | high |
| 4 | Volatility clusters and is persistent; GARCH-type models | Bollerslev (1986), *Generalized Autoregressive Conditional Heteroskedasticity* | https://doi.org/10.1016/0304-4076(86)90063-1 | supports assumption | Justifies using 5/20/60-day realised vol and a decay condition | high |
| 5 | Realised volatility forecasts future volatility well | Andersen & Bollerslev (1998), *Answering the Skeptics: Yes, Standard Volatility Models Do Provide Accurate Forecasts* | https://doi.org/10.2307/2527343 | supports assumption | The v5/v20/v60 signal is a realised-vol forecast, not a price trend | high |
| 6 | Realised volatility has long memory and pronounced persistence | Andersen, Bollerslev, Diebold & Labys (2003), *Modeling and Forecasting Realized Volatility* | https://econ.duke.edu/~boller/Published_Papers/ecta_03.pdf | supports assumption | Supports the multi-horizon vol comparison (v5 vs v20 vs v60) | high |
| 7 | VIX spikes are a fear gauge; sharp rebounds often follow | Whaley (2000), *The Investor Fear Gauge* | https://doi.org/10.3905/jpm.2000.319728 | inspired rule | The post-shock entry state (fear + decaying vol) is the equity analogue of the fear-gauge rebound | medium |
| 8 | Extreme fear sentiment predicts high subsequent returns | Da, Engelberg & Gao (2015), *The Sum of All FEARS: Investor Sentiment and Asset Prices* | https://doi.org/10.1093/rfs/hhu072 | supports assumption | Supports buying after a fear spike rather than avoiding it | medium |
| 9 | Asymmetric volatility feedback: negative shocks raise future volatility | Campbell & Hentschel (1992), *No News Is Good News: An Asymmetric Model of Changing Volatility in Stock Returns* | https://doi.org/10.1016/0304-405X(92)90037-X | supports assumption | Explains why post-shock vol stays elevated and why the sizing must be inverse-vol | medium |
| 10 | Daily-reset 3× ETFs have path dependence and volatility drag | Cheng & Madhavan (2009), *The Dynamics of Leveraged and Inverse Exchange-Traded Funds* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995 | supports assumption | Justifies capping TQQQ at 75% and holding it only in the recovery state | high |
| 11 | TQQQ seeks 3× daily, not 3× over longer periods; volatile markets are hazardous | ProShares, *TQQQ UltraPro QQQ Summary Prospectus* | https://www.proshares.com/globalassets/proshares/prospectuses/tqqq_summary_prospectus.pdf | supports assumption | Primary-document confirmation of the holding-period risk | high |
| 12 | The 165-day QQQ SMA baseline is the benchmark/correlation reference | Round-1 winner report (internal) | null | benchmark | Used only by `baseline_165d_weights`; never in `build_weights` | high |
| 13 | Continuous stripped vol targeting correlates 0.79–0.82 with the old base | Own pre-pause dev test (this agent, 2026-11-25/26) | null | tested only | The reason the rebuild changes the state rather than the gate | high |

### Rejected / not used

| Source or approach | Why rejected |
|---|---|
| Continuous inverse-vol TQQQ, 20–60% target (own test) | Dev corr 0.79–0.82 with the 165d base; fails the independence rule even though the risk profile is good |
| Continuous TQQQ→QQQ vol rotation (own test) | Dev corr 0.76–0.81; same problem |
| Vol gate to BIL, 45–50% (own test) | Corr 0.47–0.54 passes, but CAGR 17.3–26.6% and Calmar 0.44–0.67; weak return, and a binary gate is not sizing |
| Vol gate to QQQ, 40–60% (own test) | Corr 0.71–0.79; fails |
| Drawdown gate `dd252 > −10%` (own test) | Corr 0.55 but 18.5% CAGR / 38.1% DD; weak and still trend-like |
| 30% core + 165d gate + 4% stop (original) | Shared base; explicitly excluded by the brief |
| Price/minutes stops as the primary risk rule | Re-introduce the old base's timing and violate the standalone requirement; risk is handled by vol state and time stop |
| Short TQQQ tail sleeve | Not used: the idea is long leverage sizing; a short leg would be a different strategy and needs a separate borrow/risk model |

## 10. Backtest plan (when authorised)

1. Freeze this spec and the code; run only 2016-01-04..2023-12-29.
2. Generate dev metrics at 1/5/10 bp on 1-minute marks; 2% band; next-open fills.
3. Benchmark TQQQ, QQQ, BIL and the original `result.json` (10y/5y overlap the
   holdout, label them).
4. Correlation of daily returns vs the 165-day baseline; optional correlation
   vs sibling rebuilds if they expose `daily_returns.parquet`.
5. Sub-periods 2016–19, 2020–21, 2022–23; yearly returns.
6. Entries/exits, median holding period, episode-return bootstrap p-value.
7. The 3×3×3×3×3 neighbourhood and four ablations: no shock, no decay, no
   drawdown, always-on vol target.
8. Only then hand the frozen candidate to the lead for the single holdout run.

## 11. Results

**PENDING — not run.** No CAGR, drawdown, Sharpe, fill count or correlation for
VSR exists yet. The only numbers in this report are the pre-pause exploratory
diagnostics in §2, which are not the candidate.

Expected shape, to be checked rather than claimed: CAGR in the low-to-high
teens, max DD 15–30%, Calmar 0.5–0.9, 10–25 entries, median hold 15–35 sessions,
correlation 0.15–0.45. If the realised numbers are outside these bands, the
falsifiers in §8 decide the status; the bands are not a target to fit.

## 12. Risks and caveats

1. **Few events.** A 1.25× vol shock plus a drawdown plus decay may occur only
   10–25 times in eight years. The bootstrap p-value and event count are
   mandatory; a high Sharpe on 12 events is not evidence.
2. **2020 concentration.** The design is built for post-crash recoveries; 2020
   may dominate. The concentration falsifier exists because of this.
3. **Slow bear markets.** 2022 produced repeated vol spikes without durable
   recoveries; the cooldown and time stop may whipsaw. The 2022–23 sub-period
   is a key test.
4. **Vol signal lag.** `v5 < v20` can be late; the entry may miss the first
   days of a rebound. The alternative (enter on the shock alone) is an ablation,
   not the primary.
5. **TQQQ path dependence.** Even sized down, TQQQ in a high-vol recovery can
   lose 20–30% in days. The 75% cap and inverse-vol weight limit but do not
   eliminate this.
6. **BIL drag.** The strategy is in BIL most of the time. In a long calm bull
   market it will lag QQQ/TQQQ badly; that is the cost of independence.
7. **Universe limits.** Only QQQ/TQQQ/BIL have intraday history. SPY is
   daily-only and the data owner restricts it to the buy-and-hold benchmark;
   sector, bond and gold data are absent. A broader universe could improve
   diversification but is not claimed.
8. **Sample.** 1-minute data starts in 2016; there is no 2000/2008 test. The
   drawdown behaviour in a structural bear is inferred, not observed.

## 13. Files

- `hypothesis.md` — pre-registration, mechanism, falsifiers, expected correlation.
- `strategy.py` — complete implementation (`build_weights`), benchmark and
  evaluation code; **not run**, guarded by `--authorised`.
- `report.md` — this document. No `result.json` exists for this version.
- `explore.py`, `explore2.py` — pre-pause development exploration. They are
  evidence for §2, not the candidate, and must not be run while the pause is on.
