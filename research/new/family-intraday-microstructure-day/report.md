# Opening-drive intraday (day-only) — report

## Verdict

**Full-window pass, 1 bp only.** The day-only opening-drive strategy earns
**40.97% CAGR / 49.82% max DD / 1.08 Sharpe** over 2016-2026 daily-close marks,
above the TQQQ 37.54% bar with a lower drawdown. The 2024-2026 holdout earns
32.55% CAGR / 49.82% DD / 0.93 Sharpe.

## Development

| Cost | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| 1 bp | 44.12% | 46.72% | 1.13 |
| 5 bp | 19.52% | 50.82% | 0.65 |
| 10 bp | -5.42% | 63.94% | 0.05 |

The strategy trades almost every session, so the 5 bp and 10 bp results are far
below the bar. The 1 bp headline is the only version that clears it.

## Mechanism and family

The signal is intraday price action: a positive gap plus a positive first five
minutes, or a strong first 30 minutes. The position is closed at 15:59, so the
book is flat overnight. No daily trend, volatility or drawdown state is used.

## Robustness

- The 10:00 opening-drive cell is a local ridge; nearby decision times and
  thresholds are weaker, and the surface is not a broad plateau.
- The strategy is highly cost-sensitive: it is a 1 bp-only candidate.
- The full-window pass depends on the 2024-2026 holdout, which is positive but
  weaker than the development period.

## How this differs from existing work

This is a day-only version of the opening-drive microstructure strategy. It
does not use the old 165-day base, a daily trend filter, a volatility regime or
an overnight position. It is a separate family from the session-timing
strategy, which holds through the overnight and opening drive.
