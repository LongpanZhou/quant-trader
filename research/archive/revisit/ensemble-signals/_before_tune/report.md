# Revisit: `ensemble-signals` -> Volatility Contraction Recovery (VCR)

**Status: design only, 2026-11-26. Backtests are paused. No `result.json` has
been generated and no performance numbers are claimed in this report.**

The original strategy was a 165-day QQQ trend gate plus a volatility budget and
a 1-minute crash vote. The trend gate was the shared base; the volatility budget
and the crash risk were the genuinely new parts. This rebuild keeps the research
area -- volatility as the risk budget and stress as a state -- but does **not**
strip the trend gate off the old overlay. It changes the default asset, the
signal, the holding period, the sizing and the risk rule.

---

## 1. Extracted idea, and why the old overlay is not enough

The old ensemble's new content was:

1. a **volatility budget**: when 20-day realised QQQ volatility was above 1/3,
   the portfolio de-risked from TQQQ to BIL;
2. a **same-session crash vote**: when QQQ fell at least 3% from the prior close
   and the 1-minute trend/momentum/RSI vote was risk-off, TQQQ was sold to BIL
   for the rest of the session.

Everything else -- when to be in TQQQ in the first place -- came from the
165-day QQQ SMA. A "rebuilt" strategy that simply holds TQQQ when vol is low and
BIL when vol is high is still a long-TQQQ beta, and our pre-pause development
diagnostics (not a frozen result) found daily-return correlations of roughly
**0.61-0.84** with the old 165-day base for binary and continuous vol-level
rules. That is not independent enough.

The new direction comes from the same evidence but asks a different question:
**when in the volatility cycle is the 3x payoff actually worth holding?** The old
rule treated high vol only as a reason to leave. The rebuild treats the *phase*
of high vol as the signal: still-rising vol is a panic, but high vol that has
started to contract is a recovery window. Conversely, a rise in vol from a
complacent low is an early warning, even though the old trend gate would still
be long TQQQ.

This changes the base from "TQQQ when trend up, else BIL" to:

> **QQQ by default; TQQQ only in a high-vol contraction; BIL in panic and in
> rising-vol complacency.**

That is a different return driver, a different default asset, and a different
holding period.

---

## 2. Hypothesis

**H1 (recovery premium).** Volatility spikes cluster and then mean-revert. In
the phase where 20-day realised volatility is in the top quintile of its
trailing year but short-horizon volatility has stopped rising, forced selling
and risk premia are elevated, and a multi-day TQQQ position earns a positive
excess return over QQQ and BIL.

**H2 (complacency warning).** When volatility is in the bottom part of its
trailing range but short-horizon volatility is rising quickly, the calm regime
is breaking. A 3x position is poorly compensated; BIL is better than QQQ/TQQQ
until the volatility impulse resolves.

**H3 (distinctness).** Because the strategy is QQQ in normal times, TQQQ only
after stress peaks, and BIL in panic/complacency, its daily returns should be
much less correlated with the old 165-day TQQQ/BIL base than the old overlay
was. Target correlation is below 0.40, with a hard rejection above 0.60.

The hypothesis is falsified if the recovery state does not earn a positive,
repeatable excess return, if the state machine is just QQQ beta, or if the
correlation with the old base stays above 0.60.

---

## 3. Universe and data

| Item | Choice | Reason |
|---|---|---|
| Risk asset | **QQQ** | 1x Nasdaq-100; the default holding in normal volatility |
| Recovery accelerator | **TQQQ** | 3x Nasdaq-100; only in the high-vol contraction state |
| Crash shelter | **BIL** | T-bill return; panic and complacency states |
| Benchmark only | **SPY** | Daily Yahoo file exists (`data/round3/yahoo/SPY-1d-yahoo.parquet`) but there is no SPY 1-minute history for 2016-2023; it is a benchmark, not a tradable asset |
| Not used | sectors, gold, long bonds, VIX products | No local history covering the development period; the data-check subagent has not supplied them |

All tradable assets come from `data/intraday-hf/` (adjusted QQQ/TQQQ/BIL
1-minute and daily). The 1-minute panel is used for minute marks and for the
execution calendar; the signal itself is daily.

---

## 4. Signal specification (pre-registered)

### 4.1 Inputs

Daily QQQ closes `C_t` (the 15:59 close). All inputs at day `t` use data through
`t-1`, so the target can be set at the prior close and filled at day `t`'s open.

```
r_t        = C_t / C_{t-1} - 1
rv5_t      = std(r_{t-4..t}) * sqrt(252)
rv20_t     = std(r_{t-19..t}) * sqrt(252)
rv_pct_t   = percentile rank of rv20_t over the trailing 252 daily observations
slope_t    = rv5_t / rv20_t - 1
```

`rv5` and `rv20` are shifted one day in the implementation, so the value used
for day `t`'s state is the value known at day `t-1`'s close. `rv_pct` uses the
same shifted series. No future observation enters the rank.

### 4.2 State machine

| State | Condition (using prior close) | Default target |
|---|---|---|
| **PANIC** | `rv_pct >= 0.80` and `slope > +0.10` | 100% BIL |
| **RECOVERY** | `rv_pct >= 0.80` and `slope <= +0.10` | TQQQ risk budget (see 5) |
| **COMPLACENCY** | `rv_pct <= 0.30` and `slope > +0.25` | 100% BIL |
| **NORMAL** | everything else | QQQ risk budget |

State transitions:

- entering PANIC or RECOVERY is allowed immediately;
- leaving a state to NORMAL or COMPLACENCY waits for **5 trading days** in the
  current state, to avoid one-day whipsaw;
- a RECOVERY older than **20 trading days** is closed and cannot re-open until
  the raw state leaves RECOVERY (the hypothesised post-spike window has expired);
- a severe re-acceleration, `slope > +0.50`, exits RECOVERY to PANIC
  immediately, overriding the minimum hold. This is the risk stop: if the
  volatility contraction fails, the trade is wrong.

The same state machine is evaluated every day at the close. There is no
intraday signal in the rebuild; the 1-minute panel is for marks and fills.

### 4.3 Timing

- Day `t`'s target is set from the prior completed daily close and fills at day
  `t`'s first bar open.
- At day `t`'s last bar (15:59, or 13:00 on half days), the target for day
  `t+1` is set from day `t`'s completed close. It fills at day `t+1`'s open.
- The shared harness applies the 2% band and next-bar-open fills. Weights are
  long-only and sum to 1.

---

## 5. Sizing and risk

The strategy is a **risk-budgeted state allocation**, not a binary on/off:

| State | QQQ weight | TQQQ weight | BIL weight |
|---|---:|---:|---:|
| NORMAL | `min(1, 0.20 / rv20)` | 0 | remainder |
| RECOVERY | 0 | `min(1, 0.35 / rv20)` | remainder |
| PANIC | 0 | 0 | 1 |
| COMPLACENCY | 0 | 0 | 1 |

Examples: at QQQ vol 20% the NORMAL book is 100% QQQ; at 25% it is 80% QQQ /
20% BIL. At TQQQ-relevant QQQ vol 35% the RECOVERY book is 100% TQQQ; at 50% it
is 70% TQQQ / 30% BIL. The budget caps exposure at 100%; there is no leverage
beyond 100% TQQQ and no shorting.

Risk controls:

1. **Volatility re-acceleration stop:** if `slope > +0.50` while in RECOVERY,
   move to PANIC at the next open.
2. **Recovery time stop:** after 20 trading days in RECOVERY, move to NORMAL and
   do not re-enter until the raw state leaves RECOVERY.
3. **Minimum hold:** 5 trading days for normal exits; risk-off entries and
   recovery entries are immediate.
4. **No overnight gap stop:** the strategy accepts overnight gap risk; a stop
   would reintroduce the old intraday overlay and is deliberately not used.
5. **Band:** the harness's 2% rebalance band applies. Because weights are
   vol-scaled daily, the band controls small resizes; no extra turnover rule is
   added.

---

## 6. Holding period

- NORMAL: state-dependent; typically weeks to months, reviewed daily.
- RECOVERY: **5-20 trading days**, capped by the time stop; the hypothesis is a
  post-spike window, not a permanent regime.
- PANIC/COMPLACENCY: at least 5 trading days, until volatility normalises or the
  raw state changes.
- All positions are held overnight; there is no intraday flat period.

This is a deliberate change from the original ensemble's session-level crash
exit. The new strategy is a multi-day volatility-cycle strategy.

---

## 7. Expected correlation with the old base

**Expected daily-return correlation: 0.20-0.50; design target < 0.40; hard
rejection above 0.60.** This is an expectation to be measured on the
development period, not a result.

Why it should be low:

- the old base is **100% TQQQ** in calm uptrends; VCR is **QQQ** in normal times,
  so the beta and the return driver differ;
- VCR's TQQQ exposure is concentrated in high-vol contraction windows, when the
  165-day trend base is usually in BIL after a drawdown;
- VCR holds BIL in complacency (low vol rising), when the old base is often
  still long TQQQ;
- multi-day state persistence means VCR does not reproduce the old base's daily
  trend flips.

If the measured correlation is above 0.60, the idea is not independent enough
and the rebuild should be redesigned or retired rather than forced.

Correlation with other rebuilds is also unknown; the design target is < 0.70.
Because the default asset is QQQ and the TQQQ window is post-spike, it should
not collide with trend, stop, or intraday-momentum rebuilds, but this must be
measured by the lead.

---

## 8. Falsifiers (pre-registered)

The strategy is rejected or redesigned if any of the following holds on the
development period:

1. **Base correlation:** daily-return correlation with the 165-day baseline is
   **>= 0.60**.
2. **No recovery premium:** the average forward 5/10/20-day TQQQ-minus-QQQ return
   in RECOVERY is <= 0, or the bootstrap p-value is > 0.10. Report the event
   count; if it is below 30, treat the result as fragile regardless of p.
3. **No risk-adjusted edge:** CAGR <= QQQ buy-and-hold, or Sharpe <= the old
   baseline, or max drawdown >= TQQQ buy-and-hold.
4. **Subperiod instability:** the sign of the RECOVERY excess return flips in
   2016-19, 2020-21 or 2022-23, or the strategy only works in one subperiod.
5. **Parameter knife-edge:** the ±1-step neighbourhood (percentile 0.70/0.80/
   0.90; slope 0.00/0.10/0.20; calm 0.20/0.30/0.40; complacency slope 0.15/
   0.25/0.35; min hold 3/5/10; max recovery 10/20/30; vol targets 0.25/0.35/0.45
   and 0.15/0.20/0.25) does not contain a plateau with the same sign.
6. **Placebo match:** a placebo state machine with the same state durations but
   random entry dates (or random labels) produces the same return. If the
   placebo is indistinguishable, the state labels add nothing.
7. **Cost fragility:** the edge at 5 bp or 10 bp is negative or disappears.
8. **QQQ beta:** correlation with QQQ is > 0.85 and the strategy has no
   appreciable alpha over QQQ; in that case it is a repackaged QQQ beta.
9. **Time-stop dependence:** all the result comes from the 20-day cap or the
   5-day minimum hold; if removing either destroys the edge, the state machine
   is not the source.
10. **Data leakage:** any signal uses the current day's close to trade the same
    day, or the 252-day percentile includes the observation being ranked.

---

## 9. Planned evaluation (when authorized)

Development only, **2016-01-04 -> 2023-12-29**. The holdout (2024-01-02 ->
2026-10-23) is not inspected by this agent.

- Costs: **1 bp headline, 5 bp and 10 bp**.
- Marks: 1-minute equity marks; 2% band; next-open fills.
- Correlation: daily returns vs the 165-day baseline; also vs QQQ/TQQQ for
  interpretation.
- Subperiods: 2016-19, 2020-21, 2022-23.
- Parameter neighbourhood: the grid in falsifier 5.
- Placebo: random state labels/durations, and random RECOVERY entries within
  high-vol periods.
- Event study: RECOVERY episodes, forward 5/10/20-day TQQQ-QQQ and TQQQ-BIL
  returns, bootstrap p-value; count events.
- Benchmarks: TQQQ, QQQ, SPY buy-and-hold, and the original ensemble's
  `result.json` (for context, not a dev comparison).
- 10y/5y windows: run by the lead after freeze, labeled as overlapping the
  holdout; this agent does not inspect them.
- `variants_tried`: includes the pre-pause exploratory grid (binary vol levels,
  continuous vol targets, three-state ladders, hysteresis variants) plus the
  final neighbourhood. The pre-pause work is disclosed, not hidden.

---

## 10. Provenance

| Idea / claim | Source | Link | Role | Evidence / caveat | Confidence |
|---|---|---|---|---|---|
| Original ensemble: vol budget + crash vote | Own prior report and code | local: `research/agents/ensemble-signals/report.md` | starting point | The old base was a 165-day QQQ/TQQQ gate; the new idea must not reuse it | high |
| Volatility clustering and mean reversion | Engle (1982), ARCH, *Econometrica* 50(4) | https://doi.org/10.2307/1912773 | supports assumption | Conditional variance is persistent and mean-reverting; motivates a vol-state machine | high |
| GARCH persistence | Bollerslev (1986), *Journal of Econometrics* 31(3) | https://doi.org/10.1016/0304-4076(86)90063-1 | supports assumption | Volatility shocks decay; justifies a post-spike contraction window | high |
| Leverage / volatility feedback | Christie (1982), *JFE* 10(4) | https://doi.org/10.1016/0304-405X(82)90018-6 | supports assumption | Negative returns raise future volatility; crash states are asymmetric | high |
| Asymmetric volatility | Campbell & Hentschel (1992), *JFE* 31(3) | https://doi.org/10.1016/0304-405X(92)90037-X | supports assumption | Volatility responds more to negative shocks; supports separate panic/recovery states | high |
| Variance risk premium | Bollerslev, Tauchen & Zhou (2009), *RFS* 22(11) | https://doi.org/10.1093/rfs/hhp008 | supports assumption | High variance risk premia predict high future returns; the strategy uses realised vol as a proxy | medium |
| Volatility-managed exposure | Moreira & Muir (2017), *Journal of Finance* 72(4) | https://doi.org/10.1111/jofi.12513 | inspired sizing | Scale exposure by trailing variance; VCR uses a risk budget, not the old 1/3 binary cutoff | high |
| Counter-evidence on vol management | Cederburg, O'Doherty, Wang & Yan (2020), *JFE* 138(1) | https://doi.org/10.1016/j.jfineco.2020.04.002 | counter-evidence | Vol management does not systematically beat unmanaged portfolios; treat H1 as fragile until tested | high |
| High-vol regimes and momentum crashes | Daniel & Moskowitz (2016), *JFE* 122(2) | https://doi.org/10.1016/j.jfineco.2015.12.002 | supports assumption | Crash risk is concentrated in high-vol, high-beta states; supports a separate panic state | high |
| Post-crash reversals | Folkinshteyn (2015), *Investor reaction in stock market crashes and post-crash market reversals* | https://rdw.rowan.edu/cgi/viewcontent.cgi?article=1009&context=business_facpub | supports assumption | Stocks bid down more in crashes tend to rebound more in post-crash reversals; supports RECOVERY | medium |
| Volatility mean reversion around extreme returns | SSRN working paper, *Mean Reversion of Volatility Around Extreme Stock Returns* | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2239938 | supports assumption | Examines volatility mean reversion after extreme returns; author metadata not independently verified | low-medium |
| Exact VCR state machine, thresholds, 5/20-day holds, risk budget | Own hypothesis / no external source | null | inspired rule | No paper prescribes this exact percentile/slope state machine; it is the novel part and must earn its keep | high (as own hypothesis) |
| Data and execution | Local `data/intraday-hf/` and `research/bt.py` | local | data/benchmark | Adjusted QQQ/TQQQ/BIL 1-minute; next-open fills; 1 bp primary; 2% band | high |
| SPY benchmark only | `data/round3/yahoo/SPY-1d-yahoo.parquet` and `SOURCE.md` | local | benchmark | Daily SPY only; no SPY 1-minute history for the development period; not tradable in VCR | high |

The exact state machine is the only genuinely new idea here. The sources support
the pieces (volatility clustering, asymmetric shocks, variance risk, post-crash
reversals), not the specific thresholds. That is why the falsifiers and the
parameter-neighbourhood table matter more than the narrative.

---

## 11. Code map and next steps

- `strategy.py` -- `build_weights(ts, opens, closes, **params) -> (weights, info)`.
  It contains no 165-day (or any 100-250 day) moving-average gate, no old
  `build_weights` call, and no old base weights.
- `main()` is guarded by `--run`; without it, it only prints state counts.
- `result.json` is intentionally absent until the lead authorizes the run.
- Next step after authorization: run the dev grid, pick the parameter set from a
  plateau, fill the neighbourhood/placebo/event tables, then freeze for audit.

**Current status: `design_only_pending_authorization`.** The standalone idea is
untested; it must not be called working until the dev results, correlation and
audit are in hand.
