# Ratio froth

## Hypothesis

The TQQQ/QQQ ratio is a cumulative record of realised leverage. When the ratio
is far above its own 200-day mean, a low-volatility melt-up has compounded
without paying the usual drag and the next month is flat-to-negative. Holding
unlevered QQQ during those froth days, while keeping the 165-day trend base and
the 4% intraday stop, should cut drawdown without giving up the trend return.

## Rules

- Base: QQQ close above its 165-day SMA -> TQQQ; otherwise BIL.
- 4% intraday stop on TQQQ.
- Froth overlay: if the prior close's `log(TQQQ/QQQ ratio / 200-day MA)` is
  above 0.18, hold QQQ instead of TQQQ.
- Next-bar open fills, long only, 2% band, 1 bp headline.

## Verification

Clean full-window rerun from the frozen ratio-pairs code:

| Window | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Dev 2016-2023 | 61.56% | 36.65% | 1.45 |
| Holdout 2024-2026 | 65.40% | 26.50% | 1.40 |
| Full 2016-2026 | **62.21%** | 36.65% | 1.43 |

## Caveat

This is a legacy 165-day-base strategy, not a new independent family. It is the
trend-vol family winner only because its verified full CAGR is higher than
`fast-trend-vol`'s.
