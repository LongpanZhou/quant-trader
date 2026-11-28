# Spec: participation exhaustion long (`volume-orderflow`)

**Frozen spec v1 — 2026-11-26. Not yet run. Backtests paused.**
Development period: 2016-01-04 → 2023-12-29. Holdout 2024-01-02 → 2026-10-23 is
never touched by this agent.

---

## 1. Universe and data

| Role | Symbol | Source |
|---|---|---|
| Signal (volume, range, returns) | QQQ | `data/intraday-hf/QQQ-1m.parquet` |
| Expression (3× long) | TQQQ | `data/intraday-hf/TQQQ-1m.parquet` |
| Cash / risk-off | BIL | `data/intraday-hf/BIL-1m.parquet` |

**Why no new universe.** The brief permits sectors, bonds, gold and vol products,
but every candidate needs 1-minute history to be minute-marked, and the local
data has only QQQ/TQQQ/BIL from 2016. `data/cache/dukascopy/SPY` contains 60
daily `.bi5` files covering 2026-08-31 → 2026-11-20 only, and `data/round3/` is
empty. A cross-sectional sector-ETF version of this idea was designed and dropped
for exactly this reason (see `provenance.md`, rejected items). Free 1-minute
history back to 2016 is not available for sector ETFs, so the honest choice is a
single-asset event strategy on the assets that do have minute data.

## 2. Signal (event definition)

Computed once per session `d` from that session's own bars (09:30–15:59 ET, or the
last bar on a half day). Every input is known at the 15:59 close of `d`.

```
q_open[d]   = QQQ open of the first bar of session d
q_close[d]  = QQQ close of the last bar of session d
q_high[d]   = max QQQ high over session d
q_low[d]    = min QQQ low over session d
q_vol[d]    = sum QQQ volume over session d

rvol[d]     = q_vol[d] / mean(q_vol[d-20 .. d-1])          # 20 prior sessions
intraday[d] = q_close[d] / q_open[d] - 1
clv[d]      = ( (q_close-q_low) - (q_high-q_close) ) / (q_high - q_low)   if range > 0
            = 0                                                          if range = 0

event[d]    =  rvol[d] >= 1.5
           AND intraday[d] <= -0.008
           AND clv[d] >= 0.0
```

- `rvol` uses the **previous 20 sessions only** (`shift(1)`); the event session's
  own volume is the numerator and is not part of the baseline.
- Warm-up: the first 20 sessions of the panel have no `rvol` and cannot produce an
  event. The panel is loaded with 500 calendar days of warm-up before 2016-01-04,
  so the first dev session is already warm.
- Non-finite `rvol` (zero-volume sessions) → no event.
- The three thresholds are **fixed a priori** at 1.5 / −0.8% / 0.0 and are not
  chosen from the data. `clv >= 0` means "closed in the upper half of the range".

## 3. Position and holding period

- A signal on session `d` opens a position at the **open of session d+1** and
  holds it for **5 complete sessions**, exiting at the **open of session d+6**.
  (The engine trades at session opens; a session-open to session-open convention
  keeps spec and code identical.)
- A new signal while a position is open **extends** the holding window to
  `max(current exit, new signal + 5)`. No pyramiding, no early exit.
- Exposure during a held session: **100% TQQQ**. Otherwise **100% BIL**.
- Long-only. No leverage beyond holding the 3× ETF. Weights sum to 1.
- **No price stop, no trailing stop, no re-entry rule.** The only exit is the
  five-session clock. This is deliberate: a stop would reintroduce the original
  overlay and make the result unattributable to participation.

Mapping to the engine (weights set at bar *i*, filled at open *i+1*):

```
W[d]        = 1 if session d is inside a holding window, else 0     # 1 = TQQQ
weight[i,1] = W[day_of(i)]        for every bar that is NOT the last bar of its session
weight[i,1] = W[day_of(i) + 1]    for the last bar of each session   (W[nd] := 0)
weight[i,2] = 1 - weight[i,1]                                        # BIL
```

Why the last-bar exception: a target written at bar *i* only trades at
`open[i+1]`. Writing `W[d]` on the last bar of session *d* would therefore fill at
the open of session *d+1* — one bar later than the session it belongs to. Writing
`W[d+1]` there makes the next session's open the fill point, so the position
during session *d* is exactly `W[d]`. Consequence, stated explicitly: a holding
window covers `hold` full sessions **plus the overnight after the last one** —
entry at the open of `d+1`, exit at the open of `d+hold+1`. There is no
15:59 trade.

Because every bar of a session carries the same target except the last, and
because the book is always 100% of a single asset, the 2% band never triggers an
intra-session rebalance. One fill pair per event (~10–20 events/yr), so costs are
second order.

## 4. Parameters (primary) and declared neighbourhood

| Parameter | Primary | Declared neighbours (±1 step) |
|---|---|---|
| rvol threshold | 1.5 | 1.2, 1.8 |
| intraday decline threshold | −0.8% | −0.5%, −1.2% |
| close-location filter | `clv ≥ 0` | no filter (`clv ≥ −1`) |
| holding period | 5 sessions | 3, 10 |
| rvol baseline | 20 sessions | 60 sessions |
| size | 100% | 50% |

The primary is one cell of a 3×3×2×3 surface; the report must show the whole
surface and may only claim a plateau, never the best cell. Parameters were fixed
before any test of this event definition — the only prior information is the
aggregate sign in `hypothesis.md` §6, which used a different (close-to-close)
event definition.

## 5. Costs, marks, benchmarks

- Headline 1 bp one-way; 5 bp and 10 bp also reported. Band 2%.
- Minute marks on the 1-minute panel (the strategy already trades on minutes).
- Benchmarks: TQQQ buy-and-hold, QQQ buy-and-hold, BIL, and the 165-day baseline
  *(benchmark and correlation reference only — never used as a gate)*.
- Cash while out is 100% BIL, so no separate cash yield is modelled.

## 6. Overfitting controls (all required by the brief)

1. Variants tried, counted and listed.
2. The parameter-neighbourhood table from §4, with the plateau rule.
3. Sub-periods 2016–19, 2020–21, 2022–23.
4. Placebo: the same number of randomly chosen 5-session windows, 500 draws,
   reporting the fraction of draws whose mean return ≥ the real event mean.
5. Event count and a one-sided bootstrap p-value (events < 100 by construction).
6. Correlation of daily returns with (a) the 165-day baseline and (b) every
   rebuilt strategy the lead reports. Target: < 0.60 and < 0.70.

## 7. Expected correlation with the old base

The book is long TQQQ only inside ~25–40% of sessions, and those sessions follow
intraday declines — a state in which the 165-day baseline is more often in BIL
than average. Expected daily-return correlation with the baseline: **0.2–0.4**,
comfortably below the 0.60 limit, and it should be *positive but modest* rather
than zero (both books are long Nasdaq beta some of the time). If the measured
correlation is ≥ 0.60 the design is rejected under F6, not defended.

## 8. Runtime contract

`strategy.py` exposes:

```python
build_weights(ts, opens, closes, highs, lows, volumes) -> (weights, info)
```

and a `main()` that writes `result.json`. **`main()` refuses to run unless the
process is started with `--authorized`**, because backtests are paused as of
2026-11-26. `build_weights` is importable and testable without writing anything.

Look-ahead contract: `build_weights` may read bar `i` to set `weight[i]`; the
engine fills at `open[i+1]`. Session aggregates (`q_close`, `q_vol`, `clv`) are
computed from bars ≤ the session's last bar, and a session's position is only
`W[d]` — set from the previous session's close — so no same-session information
reaches that session's trade.
