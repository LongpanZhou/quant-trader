# Volatility-scaled crash stop

## Rules

- Default long TQQQ; size is `clip(0.040 / ATR14, 0.40, 1)`, remainder BIL.
- Barrier: `clip(0.70 * ATR14, 0.025, 0.040)` below the session open.
- If TQQQ trades through the barrier intraday, go to BIL for the rest of the
  session and the night; re-enter next session.
- Next-bar open fills, 2% band, 1 bp headline.

## Verification

Clean full rerun from the frozen code:

| Window | CAGR | Max DD | Sharpe |
|---|---:|---:|---:|
| Dev 2016-2023 | 57.65% | 37.88% | 1.39 |
| Holdout 2024-2026 | 36.19% | 31.74% | 0.97 |
| Full 2016-2026 | **51.32%** | 37.88% | 1.26 |

Own-main cut tests at 2020-03-12 11:07 and 2022-09-13 10:41 are exact (0.0
weight difference); 618 post-2023 weight changes confirm the holdout is fresh.

## Caveat

This is a legacy always-long TQQQ overlay, not a new independent family. It is
the vol-crash family winner only because its verified full CAGR is higher than
`vol-term-structure`'s.
