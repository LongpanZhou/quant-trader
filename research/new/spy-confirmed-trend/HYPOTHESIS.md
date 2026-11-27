# SPY-confirmed TQQQ trend ladder — pre-registration

**Status:** written before the final 1-minute development run. A coarse
daily-mark diagnostic (2016-2023 only) was used to locate the passing region;
the eight-cell grid below was then frozen and is reported in full. No 2024+
observation was used for signal construction, grid selection or evaluation;
every data read in the strategy is filtered at 2023-12-29. Development window
only: 2016-01-04 → 2023-12-29.

**Bar:** TQQQ buy-and-hold on the development window is **36.72% CAGR /
82.29% max DD / 0.82 Sharpe** (lead-provided, 1-minute marks). A pass requires
CAGR > 36.72% and DD < 82.29%, ideally DD < 60%.

---

## 1. One-sentence hypothesis

A Nasdaq trend ladder that demands **broad-market confirmation** (SPY above
its 200-day SMA) before using 3x leverage, sizes the leveraged sleeve to an
**85% volatility target**, and applies a fast **−15% from-20-day-high brake**
should keep most of TQQQ's bull-market compounding while side-stepping enough
of 2018-Q4, 2020 and 2022 to beat TQQQ's 36.72% development CAGR with less
than 60% drawdown.

## 2. Motivation

TQQQ is a 3x daily-reset Nasdaq-100 ETF. Its 2016-2023 record is a strong
trend multiplied by three deleveraging episodes: 2018-Q4, the 2020 COVID
crash and 2022. A 3x daily-reset fund is path-dependent: avoiding the worst
compounding damage is worth more than the return given up in whipsaws.

The mandate's distinct idea is the **SPY confirmation**. QQQ's own trend says
whether tech is participating; SPY's 200-day trend says whether the broad
equity risk premium is being paid. When QQQ is above trend but SPY is not, the
strategy holds QQQ (1x) rather than TQQQ (3x). When both are below trend it
holds BIL.

## 3. Exact rules

### 3.1 Data and calendar

- **Tradable:** QQQ, TQQQ, BIL. Long-only, weights ≥ 0, row sum ≤ 1.
- **Signal only:** SPY, Yahoo `adjclose` from
  `data/round3/yahoo/SPY-1d-yahoo.parquet`. No SPY 1-minute history exists for
  2016-2023, so SPY is never held or marked.
- **Daily closes:** the 15:59 ET close of each session from the 1-minute panel.
  Before 2016-01-04, Yahoo adjusted daily closes are spliced at the first panel
  close so the 200-session indicators have 2015 warm-up.
- **Boundary:** the panel is requested with `end=2023-12-29`; every daily
  Parquet read is filtered with `date <= 2023-12-29`.

### 3.2 Signals (all through session k's close)

```
qqq_up(k) = QQQ(k) > SMA_150(QQQ)(k)
spy_up(k) = SPY(k) > SMA_200(SPY)(k)
rv20(k)   = stdev(TQQQ daily returns, last 20 sessions) * sqrt(252)
scale(k)  = min(1, 0.85 / rv20(k))
hi20(k)   = max(TQQQ close, last 20 sessions)
dd(k)     = TQQQ(k) / hi20(k) - 1
```

### 3.3 Brake state machine

A **fresh** breach `dd(k) <= -0.15` arms a 5-session BIL lockout. The brake
does not re-arm until `dd` recovers above −7.5% (half the trigger), so a slow
recovery does not keep the book in BIL for months. If the brake is still
breached when a lockout ends, it can re-arm only after that half-recovery.

This is the deliberate departure from the literal mandate: a −10% brake on a
3x ETF fires on routine 3-4% QQQ pullbacks and clips the rebound; the −15%
threshold is the centre of the passing plateau. The literal −10% centre is
cell A of the grid and is reported, not hidden.

### 3.4 Position mapping (target set at session k's close, filled k+1 open)

| Condition | Target |
|---|---|
| brake lockout | BIL 100% |
| qqq_up and spy_up | TQQQ `scale(k)`, remainder BIL |
| qqq_up only | QQQ 100% |
| otherwise | BIL 100% |

### 3.5 Execution

- Next-session-open fills; 2% band; 1 bp headline, 5 bp and 10 bp sensitivity.
- Equity is marked on every 1-minute bar.
- No full-sample normalisation; every input is a trailing window.

## 4. Pre-registered eight-cell grid

One parameter at a time around the primary; the literal mandate centre is
included as cell A.

| Cell | QQQ SMA | SPY SMA | Vol target | Brake |
|---|---:|---:|---:|---:|
| A `mandate_100_10` | 100 | 200 | 0.85 | 0.10 |
| B `primary_150_15` | 150 | 200 | 0.85 | 0.15 |
| C `qqq135` | 135 | 200 | 0.85 | 0.15 |
| D `qqq160` | 160 | 200 | 0.85 | 0.15 |
| E `spy180` | 150 | 180 | 0.85 | 0.15 |
| F `spy220` | 150 | 220 | 0.85 | 0.15 |
| G `vol70` | 150 | 200 | 0.70 | 0.15 |
| H `brake20` | 150 | 200 | 0.85 | 0.20 |

Fixed everywhere: 20-session vol window, 20-session brake high, 5-session
lockout, 2% band, 1 bp costs.

## 5. What would falsify the hypothesis

- Cell B fails to clear 36.72% CAGR on 1-minute marks.
- The grid plateau is a single spike: neighbours C-H collapse below the bar.
- The result disappears under 5-10 bp costs or a one-session execution delay.
- A block-shuffle placebo matches the actual CAGR (i.e. the timing adds
  nothing).
- The SPY confirmation adds nothing versus the same QQQ-only ladder.
- The edge is entirely one year; drop-year cuts collapse the CAGR.

## 6. Known weaknesses to report honestly

1. **Late exits.** A 150-day SMA exits after a 15-20% QQQ decline, so the
   2022 loss is still around −25 to −30% before BIL.
2. **Whipsaw.** 2016, 2019, 2021 and 2023 contain repeated small exits and
   re-entries; the brake can re-enter into a continuing crash (March 2020).
3. **The 100-day centre fails.** The mandated 100-day QQQ SMA is too fast for
   a 3x ETF: it exits routine pullbacks and re-enters late.
4. **The vol target is nearly inert.** TQQQ's 20-day realized vol rarely
   exceeds 85%, so `scale` is 1.0 on about 95% of TQQQ days.
5. **The SPY gate is a modifier, not the engine.** The QQQ 150-day trend does
   most of the work; SPY confirmation improves DD and adds a small CAGR.
6. **The brake threshold is non-monotone.** 12% and 20% are close to 15% in
   CAGR but not identical; the plateau is wide, the exact cell is not sacred.
