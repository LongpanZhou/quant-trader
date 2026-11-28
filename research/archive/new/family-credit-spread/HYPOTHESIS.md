# Credit spread — pre-registration

**Family:** `credit-spread`  
**Directory:** `research/new/family-credit-spread/`  
**Development window:** 2016-01-04 .. 2023-12-29. No 2024-2026 row enters any
feature, result or robustness calculation. External series are truncated at the
development end before the features are computed.  
**Status:** development-only study. The lead runs the one-shot holdout.

## 1. Hypothesis

The high-yield / duration ratio is a direct price of credit risk appetite. When
HYG outperforms IEF, credit investors are willing to take default risk in
exchange for spread; when HYG underperforms IEF, the marginal credit buyer is
de-risking and the equity risk premium is likely to follow. A long TQQQ book
should be held when credit is improving and moved to BIL when it is
deteriorating. The signal is the **relative total return of high-yield credit
versus duration**, not a price trend, volatility state, drawdown, calendar
window, intraday flow, ML forecast or relative-strength gate.

The claim is deliberately directional and is falsifiable: if credit momentum
does not lead QQQ/TQQQ returns in the development window, the family is
rejected.

## 2. Why this is a new family

The primary signal is the HYG/IEF total-return ratio and its 20/60-session
change. The strategy does not use:

- a 100-250 day moving-average trend gate;
- volatility targeting / vol-of-vol scaling;
- a drawdown, capitulation or crash event;
- a calendar date window;
- an opening-range, closing-flow or intraday-microstructure signal;
- an ML classifier;
- a QQQ/SPY or TQQQ/QQQ relative-strength gate.

HYG and IEF are used only as signal inputs. The only price inputs for execution
are QQQ/TQQQ/BIL marks.

## 3. Exact definitions

For each external close date `t`:

```
cr_t   = ln( HYG_adjclose_t / IEF_adjclose_t )
cr20_t = cr_t - cr_{t-20}
cr60_t = cr_t - cr_{t-60}
```

Both ETFs' adjusted closes are total-return series (distributions included), so
the ratio is a relative total-return index. The ratio and its changes are
computed on the external calendar and reindexed to the QQQ session calendar
with a forward fill. The feature frame is truncated at the development end
before any feature is calculated.

## 4. State machine and exact rules

A two-level hysteresis with a 1.5% deadband on the 20-session change:

```
if cr20_t >= +0.005   ->  risk-on   (100% TQQQ)
if cr20_t <= -0.010   ->  risk-off  (100% BIL)
else                  ->  hold previous state
```

The +0.5% entry and -1.0% exit are round numbers: credit is "improving" when
the high-yield/duration ratio has out-total-returned duration by half a percent
over a month, and "deteriorating" when it has given up a full percent. The
0.5%-1.0% band is the deadband. The asymmetry is intentional: a deterioration
of 1% is a larger move in the ratio's own distribution than a 0.5% improvement,
so the exit is harder to trigger than the entry.

The decision is taken from the session's official external close, written at
that session's 15:59 bar and filled at the next session's 09:30 open. Idle
capital is BIL. No 2024+ row is loaded.

## 5. Pre-registered parameter box

Centre: `on = +0.005`, `off = -0.010`, 20-session change.

The 8-cell plateau is the 3 x 3 grid of `on` in {0.000, 0.005, 0.010} and
`off` in {-0.015, -0.010, -0.005}; the centre is the middle cell and the eight
neighbours are the plateau. A 60-session variant is reported as an ablation,
not as a second centre.

## 6. Falsifiers / kill criteria (pre-registered)

The family is rejected if any of the following holds on the development window:

1. **Return:** 1 bp CAGR is below the TQQQ development bar of 36.72%, or the
   Sharpe is below 0.82, or max drawdown is worse than 82.29%.
2. **Activity:** fewer than 100 full fills and fewer than 30 independent state
   changes.
3. **Plateau:** fewer than 6 of the 8 neighbours clear the TQQQ CAGR bar.
4. **Placebo:** circular-shift placebo p-value above 0.10 on CAGR.
5. **Sign:** the credit-improving state earns a lower forward TQQQ return than
   the credit-deteriorating state. A directional hypothesis that points the
   wrong way is falsified even if a timing overlay happens to make money.
6. **Overlap:** correlation above 0.85 with any of the nine existing winners.
7. **Cost:** 10 bp CAGR below the TQQQ 1 bp bar (36.72%).

These are stated before the headline run. A negative result is reported as a
negative result.
