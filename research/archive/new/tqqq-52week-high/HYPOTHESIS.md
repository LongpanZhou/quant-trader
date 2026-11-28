# HYPOTHESIS — 52-week-high trend TQQQ (`tqqq-52week-high`)

**Status:** revision 2. Window: 2016-01-04 → 2023-12-29 development only.
The 2024-2026 holdout is never loaded by `strategy.py` (the daily parquet read is
hard-filtered at `2023-12-29`).

## Specification history (disclosed, not hidden)

Revision 1 was pre-registered with the 20-session low taken from **intraday
lows, buffered 2%, confirmed over 2 closes**. A post-run event count showed the
low exit fired **0 times** in eight years: a 2% break below the lowest intraday
low of 20 sessions is almost always deeper than the 10% drawdown stop, so the
rule was decorative and the strategy did not actually implement "exit on a
20-day low". Revision 1 still passed dev at 42.21% CAGR / 45.4% DD / 1.03
Sharpe, but only the 10% stop was active.

Revision 2 fixes the definition to the standard Donchian form: the **lowest
closing price of the prior 20 sessions, no buffer, one close below it**. That
exit is active (22 events). The 10% drawdown stop remains as the disaster
backstop (2 consecutive closes). Both exits are now real. The revision was made
to correct an implementation bug, not to search for a better cell; the revision
2 grid below was frozen before its own results were computed. Both revisions
are reported in `report.md`.

## Claim

QQQ price *proximity to its 52-week high* is a slow, robust bull-regime filter.
A leveraged index near its 52-week high is in a state of positive trend
persistence: holders are not underwater, the marginal seller is scarce, and the
index has already absorbed the available supply. The behavioural story is
anchoring/underreaction (George & Hwang 2004): investors anchor on the old high,
so good news near the high is under-priced and the trend continues. For a 3x
daily-reset ETF the asymmetry is amplified: the regime that produces the high
also has the least path-dependent decay from volatility drag, while the regimes
that produce 20-35% index drawdowns produce 60-85% ETF drawdowns.

The strategy owns TQQQ while QQQ is (a) within 8% of its 52-week intraday high
and (b) above its 20-session SMA, and leaves on a 20-session closing low or a
10% drawdown from the 52-week high. A volatility target scales the TQQQ weight;
the remainder sits in BIL.

Named failure modes:
- **Whipsaw.** A 20-session closing low is a common event in an uptrend. On a
  3x ETF the round-trip cost of a false exit is large (sell 1x, rebuy 3x
  higher). 2019 and 2023 are the expected worst cases.
- **Late re-entry.** After a bear market the 52-week high is stale: QQQ must
  climb back near the old peak before the gate re-opens. That systematically
  misses the first leg of recoveries (H1 2019, H1 2023).
- **2018/2022.** The gate should get out of the Q4-2018 and 2022 bears, but the
  exit is necessarily after the first 10-20% of the decline.

The upside case is that avoiding the three large bear markets (2018Q4, 2020,
2022) more than pays for the whipsaws, so dev CAGR exceeds TQQQ's 36.72% with a
much smaller drawdown.

## Formal rules (all signals through session close t; fills next open)

Signal series: official adjusted QQQ daily OHLC and TQQQ close. 2015 history is
used only to warm the 252-session high before 2016-01-04.

```
H_t     = max(QQQ high[t-251 .. t])              # 52-week high, includes t
dist_t  = QQQ close[t] / H_t - 1
trend_t = SMA20(QQQ close)[t]
L_t     = min(QQQ close[t-20 .. t-1])            # prior 20-session closing low

state s_t:
  s_{t-1}=0 -> s_t=1  iff  dist_t >= -entry_dist  AND  close_t > trend_t
  s_{t-1}=1 -> s_t=0  iff  close_t < L_t
                       or  [dist_t <= -exit_dd for 2 consecutive closes]

weight_t = s_t * min(1, target_vol / sigma_t)
sigma_t  = stdev(log TQQQ returns, 20 sessions) * sqrt(252)
TQQQ weight = weight_t; BIL weight = 1 - weight_t
```

The 2-session confirmation on the 10% stop is a debounce: one close through the
stop is treated as noise, two consecutive closes are a regime break. The
20-session closing-low exit needs one close, the standard Donchian rule.

## Pre-registered base (mandate design point, not selected from the grid)

The base is the mandate's natural design point: 8% proximity, a 10% drawdown
stop, a 20-day closing low, and a 0.85 vol target. It was frozen before the grid
was run. In this particular 8-cell grid it is also the highest-CAGR cell; that
is disclosed rather than hidden, and the surrounding cells are reported in full
so the reader can judge the ridge.

| parameter | value | meaning |
|---|---:|---|
| `entry_dist` | 0.08 | enter within 8% of the 52-week high |
| `entry_confirm` | 1 | first qualifying close enters |
| `exit_dd` | 0.10 | leave at 10% below the 52-week high |
| `dd_confirm` | 2 | consecutive closes below the stop |
| `low_n` | 20 | 20-session closing low |
| `low_source` | close | Donchian low of closes |
| `low_buf` | 0.00 | no buffer |
| `low_confirm` | 1 | one close below the low exits |
| `trend_n` | 20 | QQQ 20-session SMA entry gate |
| `high_n` | 252 | 52-week high |
| `high_source` | high | intraday high (standard 52-week high) |
| `target_vol` | 0.85 | annualised TQQQ vol target |
| `vol_window` | 20 | realised-vol window |

## Pre-registered 8-cell grid (revision 2)

The grid varies one mechanism at a time around the base; it is not expanded
after seeing results.

1. `base`
2. `entry_5` — 5% proximity (stricter momentum gate)
3. `entry_10` — 10% proximity (looser gate, earlier re-entry)
4. `exit_dd_8` — 8% stop (tighter crash exit)
5. `exit_dd_12` — 12% stop (wider crash exit)
6. `dd_confirm_3` — slower 3-close stop confirmation
7. `low_buf_2` — 2% buffer below the 20-session closing low
8. `tv_0.65` — lower volatility target

## Pass condition

Dev CAGR > 36.72% **and** max drawdown < 82.29% (target < 60%). Reported
alongside: Sharpe, TQQQ exposure, time in TQQQ, correlation to TQQQ, yearly
returns, 1/5/10 bp slippage, lag and circular-shift placebos, leave-one-year-out
CAGR, cut tests, and a truncation causality check.

## Known implementation choices

- Signals use the official daily OHLC (the 16:00 print), while fills use the
  1-minute-panel next open (09:30). This is conservative relative to a 15:59
  decision, and is the same convention as the existing research strategies.
- The 52-week high uses intraday highs, the standard definition. The 20-session
  low uses closing prices, the standard Donchian definition.
- No full-sample normalisation, no future data, no 165-day SMA as an input.
  The 165-day SMA is computed only as an external benchmark for correlation.
- Signals are computed on the daily calendar and mapped to the panel sessions;
  a session with no daily print carries the prior state (there are none in the
  development window).
