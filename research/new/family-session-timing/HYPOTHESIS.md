# Session-timing TQQQ: overnight + opening drive, with a conditional late-day leg

**Status:** pre-registered before the final run. Development window only.
**Author:** research subagent, 2026-11-27.
**Directory:** `research/new/family-session-timing/`
**Family:** session / time-of-day timing. No daily trend SMA, no
volatility/drawdown regime as the primary signal, no relative strength, no
drawdown recovery.

---

## 0. Scope and data

| Item | Value |
|---|---|
| Development window | 2016-01-04 .. 2023-12-29 |
| Data | `data/intraday-hf/` adjusted 1-minute QQQ, TQQQ, BIL |
| Fills | next-bar open, `research/bt.py`, 2% band |
| Costs | 1 bp headline; 5 bp and 10 bp also reported |
| Constraints | long-only, weights >= 0, row sum <= 1, idle cash |
| Holdout | never used; the strategy panel is sliced at 2023-12-29 |

The 10-day volatility input is warmed up with QQQ daily closes from
2015-01-02 to 2015-12-31 only. No bar on or after 2024-01-01 enters the
strategy panel or any signal.

---

## 1. Mechanism: the tradeable day has three pieces, not one

A descriptive decomposition of the development window (TQQQ, open-to-open,
2016-2023) gives the premise:

| Segment | Mean / session | Log sum 2016-2023 | Annualised log |
|---|---:|---:|---:|
| Overnight (15:59 open -> next 09:30 open) | +12.5 bp | 1.84 | +25.9% |
| Opening 30m (09:30 -> 10:00) | +6.4 bp | 1.11 | +14.9% |
| Midday (10:00 -> 14:30) | -0.3 bp | -0.67 | -8.0% |
| Last 90m (14:30 -> 15:59) | +2.2 bp | 0.18 | +2.2% |
| Last 30m (15:30 -> 15:59) | -2.8 bp | -0.67 | -8.0% |

Two facts drive the design:

1. **The overnight and the opening drive carry the positive drift.** The
   midday is a drag. A position that owns the close-to-10:00 block and sits
   out 10:00-14:30 keeps the two positive pieces and drops the negative one.
   This is a pure session-window choice, not a daily trend call.
2. **The last 90 minutes is conditional on the session's own trend.** Through
   14:29, split sessions by the TQQQ return from the 09:30 open:

   | Sessions through 14:29 | n | Last-90m mean | Log sum | Win |
   |---|---:|---:|---:|---:|
   | Up (r > 0) | 1,089 | +9.2 bp | 0.89 | 55.8% |
   | Down (r <= 0) | 923 | -6.1 bp | -0.71 | 49.4% |

   The unconditional last 90 minutes is only +2.2 bp/session. The condition
   separates a positive continuation leg from a negative one. Entering at
   14:30 on up sessions and at 15:59 on down sessions costs *no extra fill*:
   either way there is one entry and one exit per day.

So the strategy is a **session-window allocator**:

> Own TQQQ from the close through the next open and the first 30 minutes
> (the two unconditional positive blocks). On a session that is already up
> at 14:29, enter 90 minutes early and also own the late-day continuation.
> Sit in cash through the midday and through the late-day block of a down
> session.

The claimed edge is *when the position is held inside the 24-hour day*, not
a trend filter on daily closes. The position is long every night; the only
daily state variable is the current session's own return at 14:29.

### Sizing overlay

A simple volatility target is applied to the whole sleeve:

```
sigma_k = annualised stdev of the last 10 completed QQQ daily log returns
          through session k-1
s_k     = min(1, 0.25 / sigma_k),  0 if sigma_k is undefined
```

This is disclosed as a risk overlay, not the source of the edge: the raw
strategy (s = 1) is reported separately and is expected to clear the CAGR bar
on its own. The overlay is a round 25% annualised QQQ risk budget (roughly
75% TQQQ volatility at 3x); the 0.20-0.40 plateau is reported.

---

## 2. Exact rules

Universe: QQQ (volatility input only), TQQQ (position), cash. BIL is not
used; idle weight earns 0%, which is conservative.

At **14:29 ET** of session k (the close of the 14:29 one-minute bar; offset
299 from 09:30), with

```
r_k = TQQQ_close(14:29) / TQQQ_open(09:30) - 1
```

the target for the window that ends at 10:00 of session k+1 is:

| State | Entry | Exit |
|---|---|---|
| `r_k > 0` (up session) | 14:30 open of session k | 10:00 open of k+1 |
| `r_k <= 0` (down session) | 15:59 open of session k | 10:00 open of k+1 |

In both cases the position is held through the overnight block. The target
size is `s_k`. The next decision is at 14:29 of session k+1, after the 10:00
exit.

Execution details:

1. The 14:29 signal is a bar close; the entry is the next bar's open (14:30).
   On a down session the same signal sets the target at the 15:58 close,
   which fills at the 15:59 open. The 09:59 exit signal fills at the 10:00
   open. All causal.
2. The 10-day volatility uses only completed daily returns through k-1.
3. No moving-average trend gate of any length. No drawdown or volatility
   *regime* switch. The only volatility use is the continuous sizing overlay.
4. No shorting, no leverage above 1.0 total weight, no BIL.

---

## 3. Why it should beat TQQQ

| | TQQQ B&H | Expected strategy |
|---|---:|---:|
| CAGR | 36.72% | 45-60% |
| Max DD | 82.29% | 38-55% |
| Sharpe | 0.82 | 1.2-1.4 |
| Average TQQQ weight (clock time) | 100% | ~70-75% |

The return edge comes from dropping the negative midday and the negative
late-day block of down sessions. The drawdown edge comes from the same
selection plus the vol target: 2022 is a slow bear, the strategy is in cash
for about 5.2 hours of an average session (6 hours on down sessions, 4.5 on
up sessions), and it owns less when QQQ 10-day vol is above 25%.

The strategy is still a TQQQ beta product. It is long every night and
correlated with TQQQ; it is not market-neutral.

---

## 4. Falsifiers

| # | Falsifier | Decision if it fails |
|---|---|---|
| F1 | Raw strategy (no vol target) CAGR <= 36.72% or DD >= 82.29% at 1 bp | The session window alone is not enough; fail |
| F2 | Any of the 8 pre-registered grid cells is below 36.72% CAGR or above 82.29% DD at 1 bp | Reject as a narrow ridge |
| F3 | Random-entry-minute placebo reaches the real CAGR with p >= 0.10 | The 14:30/15:59 timing is not special |
| F4 | Random-subset placebo (same number of early entries, random days) reaches the real CAGR with p >= 0.10 | The condition does not select the right sessions |
| F5 | Stale signal (yesterday's 14:29 return) matches the real CAGR | The signal is a persistent regime, not session timing |
| F6 | Excluding 2020 or excluding 2022 drops the strategy below 36.72% | One-period wonder |
| F7 | Constant exposure at the strategy's average size matches the vol-target CAGR | The overlay is the edge; simplify to constant size |
| F8 | Daily-return correlation to TQQQ > 0.95 | It is B&H with extra steps |
| F9 | At 5 bp CAGR falls below 36.72% | Cost-fragile; report prominently, do not hide |

F9 is expected to be the binding weakness: the strategy pays two fills a day
(one exit, one entry). The 1 bp headline is the mandated convention; 5 bp
and 10 bp are reported as stress.

---

## 5. Pre-registered grid (8 cells)

Decision time (the bar whose close is the signal; entry on the next bar)
times the up-session threshold. Exit is always 10:00; sizing is the 0.25 vol
target.

| Cell | Decision (bar close) | Entry (next open) | Threshold |
|---|---|---|---:|
| 1 | 13:59 | 14:00 | 0.0% |
| 2 | 13:59 | 14:00 | +0.5% |
| 3 | 14:29 | 14:30 | 0.0% |
| 4 | 14:29 | 14:30 | +0.5% |
| 5 | 14:59 | 15:00 | 0.0% |
| 6 | 14:59 | 15:00 | +0.5% |
| 7 | 15:29 | 15:30 | 0.0% |
| 8 | 15:29 | 15:30 | +0.5% |

The centre is cell 3: 14:30 / 0%. It is a round 90 minutes before the close
and the natural "session is up" threshold, not the best of a search. Every
cell is reported in `result.json` and `report.md`, including any that fail.

Neighbours reported but not used to choose the centre: entry 14:15/14:45;
threshold -0.25%/+0.25%; exit 09:45/10:15/10:30/11:00; vol target
0.20/0.30/0.35/0.40; vol lookback 5/20; QQQ instead of TQQQ as the intraday
signal; raw (no vol target); constant size at the average.

---

## 6. Placebos and cuts

- **Random-entry-minute placebo:** keep the overnight + opening 30m and the
  vol target, but draw each session's entry minute uniformly from 10:01-15:59
  (after the 10:00 exit, so the entry is a genuine new entry) independent of
  the session return. 100 draws. If the real 14:30/15:59 rule is special, the
  real CAGR should sit in the top tail.
- **Random-subset placebo:** keep the entry-time distribution and the number
  of early entries, but choose which sessions enter at 14:30 at random. 100
  draws. This isolates the *selection* of sessions.
- **Stale signal:** use session k-1's 14:29 return to choose k's entry.
- **Cut tests:** exclude each calendar year in turn; report the strategy and
  TQQQ on the same cut. Subperiods 2016-2019, 2020-2021, 2022-2023.

## 7. Process note

The segment decomposition in section 1 was measured on the development
window, because that is the only window available. The strategy parameters
were then fixed from economic reasoning (the close-to-open and opening-drive
premia, the 90-minute late-day window, the round 0% threshold, the 25% vol
budget), and the 8-cell grid above was frozen before the final
`strategy.py` run. No 2024+ data was inspected. The report states the
cost fragility and the concentration honestly, including the fact that the
late-day condition is only about a 2-sigma effect on its own.
