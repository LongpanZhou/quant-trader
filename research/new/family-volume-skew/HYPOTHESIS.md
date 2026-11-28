# Intraday volume asymmetry: hypothesis and pre-registration

**Family:** `family-volume-skew` (reserve family).

**One-line hypothesis.** The asymmetry of the intraday volume distribution is
a fragility signal. When up-volume dominates the session, the move is crowded
and the next session tends to give some of it back; when down-volume dominates
and the asymmetry is in the lower part of its recent distribution, supply has
been absorbed and the next session is more balanced. A long-only TQQQ book can
hold the second state and sit in cash in the first.

**Development window.** 2016-01-04 .. 2023-12-29 only. The shared 1-minute
panel and QQQ minute volume are requested with `end=2023-12-29`; no 2024-2026
bar enters any signal, weight or statistic. The holdout is not loaded.

---

## 1. Why this should exist

Volume is not just activity; it says who is doing the trading. A session with
heavy up-volume is a crowded demand state: the marginal buyer has already
acted, and the next session is more vulnerable to profit-taking. A session
with heavy down-volume is a supply-absorption state: sellers have been filled,
and the next session can be more balanced. This is a *fragility* hypothesis,
not a volume-level or volume-acceleration hypothesis.

The primary object is the **up-volume versus down-volume asymmetry**:

```
U_d = sum(volume of 1-min bars with close > open)
D_d = sum(volume of 1-min bars with close < open)
A_d = (U_d - D_d) / (U_d + D_d)
```

`A_d` is scale-free and split-invariant. It is not the volume level (total
volume), not volume acceleration (a short/long volume ratio), and not
volatility (realized variance). The controls in the report separate all three.

The signal is deliberately **not**:

- a trend gate (no moving average, no 100-250 day filter);
- volatility targeting (size is 0 or 1);
- a drawdown/capitulation event;
- a calendar/FOMC/OpEx window;
- opening-range, close-flow, ML or relative-strength.

## 2. Exact rules

All times US/Eastern. Bar offsets are 0-based from 09:30 (0) to 15:59 (389).

| Item | Rule |
|---|---|
| Signal asset | QQQ |
| Trade asset | TQQQ (3x QQQ), weight 1.0; cash otherwise |
| Signal | `A_d = (up-volume - down-volume) / (up + down)` |
| Reference | 40th percentile of `A` over the prior 60 full sessions |
| Entry condition | `A_d < ref_d` (lower part of its recent distribution) |
| Entry | next session 09:30 open |
| Exit | next session 15:59 open (target zero at the 15:58 close) |
| Hold | one session, no overnight position |
| Short side | not traded (long-only book) |

**Decision clock.** The signal is fixed at 15:59:00 on session `d`, after all
390 one-minute bars are complete. The reference uses sessions `d-60 .. d-1`
only (a one-session shift; the current value is not in the reference). The
entry is the next session's 09:30 open; the exit is that session's 15:59 open.
There is no same-bar fill and no future data.

Only sessions with 390 one-minute bars are eligible. Half-days are skipped;
they still update the previous close.

## 3. Pre-registered centre and grid

Centre: **60-session reference, 40th percentile, TQQQ 1.0, one-session hold.**

The 8-cell grid varies the reference window and the percentile:

| Cell | Lookback | Percentile |
|---|---:|---:|
| 1 | 20 | 0.30 |
| 2 | 20 | 0.40 |
| 3 | 40 | 0.30 |
| 4 | 40 | 0.40 |
| 5 | 60 | 0.30 |
| 6 | **60** | **0.40** (centre) |
| 7 | 100 | 0.30 |
| 8 | 100 | 0.40 |

The centre selects about 38% of sessions. The 60-session window is long enough
to estimate a distribution and short enough to adapt to a changing volume
regime. The grid is reported in full and the centre is allowed to be non-best.

## 4. Kill criteria (stated before the confirmatory run)

Primary performance is the 1 bp headline. The strategy must also survive
5 bp and 10 bp. A candidate is killed if any of the following holds:

1. Dev CAGR at 1 bp is below the 36.72% TQQQ development bar.
2. 5 bp CAGR is below zero.
3. Fewer than 30 independent events or fewer than 100 fills.
4. Fewer than 6 of 8 grid cells have positive 1 bp CAGR.
5. Negative CAGR in 2 or more of the 3 subperiods (2016-19, 2020-21, 2022-23).
6. Placebo random-day p-value above 0.10.
7. Daily-return correlation above 0.70 with any of the nine current winners.
8. Any weight drift before a truncation cut.

Criterion 1 is the programme's absolute-return bar. Criteria 2-8 are
robustness and integrity gates.

## 5. Placebos and controls

- **Random days:** draw the same number of full sessions at random, keep the
  next-session 09:30 -> 15:59 clock. 200 draws. This asks whether the volume
  asymmetry selects better days than the calendar.
- **Stale signal:** use the previous session's flag. This asks whether the
  same-day volume is doing the work.
- **Price-only reversal:** hold when the same-day QQQ return is below its
  prior-60-session 40th percentile. This asks whether the signal is just
  "buy after a down day".
- **Breadth:** the same rule using the count of up versus down bars, equal
  weight, instead of volume. This asks whether volume weighting matters.
- **Volume level, realized volatility, top-5 volume concentration,
  minute-volume skew:** each below its prior-60-session 40th percentile. These
  ask whether the primary object is just volume, volatility, concentration, or
  a different skew.
- **Continuation sign:** hold when `A` is above its 60th percentile. This asks
  whether the sign is the one the fragility hypothesis predicts.

## 6. What would falsify the hypothesis

- The price-only or breadth control earning as much would mean the volume
  asymmetry adds nothing.
- The volume-level or realized-vol control earning as much would mean the
  family is a volume/volatility proxy, not a skew signal.
- The continuation sign earning as much would mean the fragility direction is
  wrong.
- A random-day placebo matching the real result would mean the edge is
  calendar drift.
- A stale signal keeping the result would mean the same-day volume is
  irrelevant.

## 7. Design disclosure

The 60-session/40th-percentile centre was fixed during development after a
small scan of lookbacks and percentiles. The grid shows a broad positive
plateau; the centre is the best 1 bp cell at the 60-session window, and the
40-session/40th-percentile cell is nearly identical (41.93% CAGR, 33.06% DD).
The contrarian sign was tested against the continuation sign: the
continuation version loses money (-19.3% CAGR, 89.8% DD at the 60th
percentile), so the report frames the family as a **fragility** signal, not a
continuation signal. This sign choice is data-driven and is disclosed. The
same-day price/volume correlation is 0.476, so the signal is partly a
short-term reversal; the price-only and breadth controls quantify how much the
volume asymmetry adds.
