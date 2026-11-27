# Opening-drive intraday (day-only)

## Hypothesis

TQQQ's intraday opening drive carries information about the rest of the
session. When QQQ gaps up and the first five minutes extend the move, or when
the first 30 minutes are strongly positive, the leveraged ETF tends to continue
into the close. Holding only during that session avoids the overnight gap and
keeps the strategy in the intraday-microstructure family.

## Exact rules

- At 09:35 ET: if QQQ opened above the prior close by more than 0.25% and the
  first five-minute return is positive, buy TQQQ at the 09:35 open.
- Otherwise at 10:00 ET: if the first 30-minute QQQ return is above 0.50%, buy
  TQQQ at the 10:00 open.
- Exit on an 8% close-based trailing stop, or at the 15:59 open otherwise.
- Flat overnight; BIL when no signal.

No daily trend, volatility or drawdown regime is used. The strategy is a
day-only variant of the combined opening-drive strategy; the overnight
reversal sleeve is disabled.

## Development result

2016-01-04 to 2023-12-29, next-open fills, 2% band, 1-minute marks:

| Cost | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 1 bp | **44.12%** | 46.72% | 1.13 |
| 5 bp | 19.52% | 50.82% | 0.65 |
| 10 bp | -5.42% | 63.94% | 0.05 |

Full 2016-2026: **40.97% CAGR / 49.82% DD / 1.08 Sharpe**, holdout 32.55%.

## Honest verdict

Passes the full-window bar, but only at 1 bp. The edge is almost entirely
erased at 5 bp and negative at 10 bp. It is a fragile, high-turnover intraday
strategy, not a cost-robust replacement for TQQQ.
