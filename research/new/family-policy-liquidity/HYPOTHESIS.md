# Policy liquidity / short-rate regime — pre-registration

**Family:** `policy-liquidity`  
**Directory:** `research/new/family-policy-liquidity/`  
**Development window:** 2016-01-04 .. 2023-12-29. No 2024-2026 data enters any
feature, result or robustness calculation; the BIL feature frame is truncated
at the development end before any feature is computed.  
**Status:** development-only study. The lead runs the one-shot holdout.

## 1. Hypothesis

The path of the short rate is a macro-liquidity state variable. The T-bill
yield is the price of cash and the financing cost of leveraged equity. When
policy liquidity is easing, stable and low, or already restrictive but priced,
leveraged equity risk is supported. When the short rate is rising abruptly, or
when the very front end of the bill curve spikes relative to its own trend
(cash hoarding / a policy tightening surprise), the marginal liquidity
available to risk assets is deteriorating and a long TQQQ book should de-risk.

The claim is about the **short-rate path**, not about price trend, volatility,
drawdown, calendar effects, opening-range flow, machine learning, or
QQQ/SPY relative strength. Those families already exist and are excluded from
the primary signal.

## 2. Why this is a new family

The primary signal is the BIL-implied short rate. The strategy does not use:

- a 100-250 day moving-average trend gate;
- volatility targeting or a vol-of-vol filter;
- a drawdown, capitulation or crash event;
- a calendar date window (FOMC, OpEx, turn-of-month, holidays);
- an opening-range, closing-flow or intraday-microstructure signal;
- an ML classifier;
- QQQ/SPY relative strength.

The only price inputs are QQQ/TQQQ/BIL marks for execution and the BIL
total-return path for the rate proxy. The state is a function of the BIL yield
level and its 20/60-session changes.

## 3. BIL-implied short rate: exact definition

BIL is a 1-3 month T-bill ETF. Its adjusted close is a total-return series: it
includes the monthly distributions and is already adjusted for the 2017-11-30
1:2 reverse split in Yahoo's data. The annualised yield proxy is the average
log total return over the last `N` sessions:

```
yN_t    = 100 * (ln A_t - ln A_{t-N}) / N * 252          N = 20, 60
dy60_t  = y60_t - y60_{t-60}
front_t = y20_t - y60_t
```

`A_t` is BIL's adjusted close on session `t`. The features are computed only
from BIL rows at or before the panel's last session. For the development run
the BIL frame is truncated at 2023-12-29 before any feature is calculated.

**Validation of the level.** The inferred path matches the known Fed/Bill
cycle over the development window: about 0% in 2016, 0.9% at end-2017, 2.2% at
end-2018, 1.5% at end-2019, about 0% through 2020-2021, 3.5% at end-2022 and
5.4% at end-2023. This is a qualitative validation only; no external Treasury
series is used.

**Why a low-rate gate is necessary.** BIL trades on a 1-cent grid around $91.5.
One cent is 1.09 bp of price; annualised over 20 sessions that is about 13.8 bp
of yield estimate, and over 60 sessions about 4.6 bp. At a 0.1% yield the
quantisation error is larger than the signal. The strategy therefore treats
`y60 < 1.0%` as a low-rate / abundant-liquidity state and does not act on
front-end noise there. The cost of this gate is stated in the falsifiers: it
also blinds the strategy to the first ~100 bp of a hiking cycle from zero,
which is exactly the 2022 H1 problem.

**No real-rate proxy.** The local panel has no CPI, inflation-expectations or
TIPS series. Subtracting an invented inflation number would violate the
"do not invent external data" rule, so the study is nominal-only. A real-rate
test is explicitly out of scope.

## 4. State machine and exact rules

For each session `k` (decision at the 15:59 close, executed at the next
session's 09:30 open):

| State | Condition | Target |
|---|---|---|
| `LOW` | `y60 < 1.00%` | 100% TQQQ |
| `HIGH` | `y60 >= 4.00%` | 100% TQQQ |
| `TIGHTENING` | `1.00% <= y60 < 4.00%` and `dy60 >= +0.40%` | 100% BIL |
| `STRESS` | `1.00% <= y60 < 4.00%` and `front >= +0.15%` | 100% BIL |
| `STABLE` | `1.00% <= y60 < 4.00%` and neither risk-off condition | 100% TQQQ |

`TIGHTENING` and `STRESS` are OR-ed. Risk-off is 100% BIL; risk-on is 100%
TQQQ. There is no partial sizing, no volatility target and no stop. The 2%
band is the harness default; with binary TQQQ/BIL weights it only affects the
two legs of a switch.

**Parameter rationale (round numbers, auditable selection).**
A coarse exploration of the same development window preceded the choice of
centre. The centre below is a round-number cell, not the grid maximum; the
full 108-cell grid and ablations are reported in `robustness.json` so the
selection is auditable.

- `LO = 1.00%`: the zero-bound / quantisation floor for BIL. Below it the
  1-cent grid dominates `y20 - y60`.
- `HI = 4.00%`: a round restrictive-policy level. Above it the short rate is
  already clearly restrictive and a front-end spike is more likely a T-bill
  supply/technical move (debt ceiling, bill issuance) than a new policy shock.
- `FRONT_T = 0.15%`: the 20-day yield rising 15 bp above the 60-day yield.
  At $91.5 this is about 1.1 standard deviations of the 20-day estimate.
- `SLOPE_T = 0.40%`: a 40 bp rise in the 60-day yield over 60 sessions. This
  is a genuine hiking cycle, not a single 25 bp move.

**Decision clock.** Daily. The state is read at the 15:59 close of session `k`
and filled at the 09:30 open of session `k+1`. The weight is held from the
open to the close of each session. The first session uses the last completed
pre-panel state (2015-12-31); it is not a same-session decision. The weekly and
monthly clock variants are reported as robustness checks, not as the primary.

## 5. Activity floor

Target: at least **100 full-window fills** or a clearly justified event count
of at least 30. Each TQQQ/BIL switch produces two fills (one sell and one buy).
With roughly 90 exits and 90 entries the expectation is about 360 fills,
comfortably above the floor. A result below 100 fills would be rejected as
structurally too slow rather than shipped.

## 6. Falsifiers / kill criteria (fixed before the final run)

The strategy is rejected if any of the following holds:

1. Full-window 1 bp CAGR `<= 36.72%`, or Sharpe `<= 0.82`, or max drawdown
   `>= 82.29%`.
2. Fewer than 100 fills or fewer than 30 entries.
3. Fewer than 6 of 8 pre-registered neighbouring cells clear the TQQQ bar.
4. Circular-shift placebo p-value `> 0.10` on CAGR.
5. Daily-return correlation `> 0.90` with any current family winner.
6. Ex-2020 CAGR `< 25%` (single-year dependence).
7. 10 bp CAGR `< 25%` (cost fragility).
8. 2022-2023 subperiod CAGR `< -10%` (inflation-regime failure).

Additional fragility flags, not automatic kills: 2022-2023 subperiod CAGR `< 0`;
max drawdown `> 70%`; 2023 underperformance vs TQQQ `> 50 pp`; 2020 log excess
`> 50%` of the net log excess.

## 7. Pre-registered tests

- Headline development metrics at 1, 5 and 10 bp; TQQQ buy-and-hold benchmark.
- 108-cell parameter grid: `LO` in {0.75, 1.00, 1.25}, `HI` in {3.50, 4.00,
  4.50}, `FRONT_T` in {0.10, 0.15, 0.20, 0.25}, `SLOPE_T` in {0.25, 0.40,
  0.55}. The delivered centre is the round-number cell; the grid is reported
  as a plateau test.
- Subperiods 2016-2019, 2020-2021, 2022-2023.
- Circular-shift placebo: 300 daily shifts (offset 60..N-60) and 50 one-minute
  shifts. The same state path is randomly re-aligned with returns; this tests
  timing skill while preserving the state's autocorrelation and activity.
- Daily-return correlations with the nine current family winners: ratio-froth,
  vol-scaled-crash-stop, relative-value-tqqq, fomc-opex-window,
  family-session-timing, family-short-reversal, family-rebalance-flow,
  family-intraday-microstructure-day, family-ml-microstructure.
- Ablations: no high band, no low band, front-only, slope-only, TQQQ
  buy-and-hold.
- Clock variants: daily, weekly, monthly.

## 8. Expected failure modes (stated ex ante)

- **2022 H1.** The spot T-bill yield is backward-looking. The `LOW` gate keeps
  the book long while the Fed hikes from zero, so the max drawdown is likely to
  remain close to TQQQ's. The strategy can only de-risk after the bill yield
  has already moved.
- **2023.** A high-rate bull market. The `HIGH` band and the slow tightening
  filter may lag the rally; the strategy can underperform TQQQ by a wide margin.
- **Whipsaw.** Brief front-end spikes produce 1-3 session exits, especially in
  2018-2019. The average holding period is short even though the core position
  is long.
- **BIL quantisation.** Below 1% the signal is noise. The low gate is necessary
  but blinds the strategy to the first 100 bp of a hiking cycle.
- **Beta.** The strategy is long TQQQ about 85% of the time. It is a TQQQ
  timing overlay, not independent alpha; high correlation with the existing
  winners is expected.

## 9. Reproduction

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research/new/family-policy-liquidity/strategy.py
python research/new/family-policy-liquidity/robustness.py
```

`strategy.py` regenerates `result.json`; `robustness.py` regenerates
`robustness.json`.
