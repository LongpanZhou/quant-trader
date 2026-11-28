# Gap continuation: hypothesis and pre-registration

**Family:** `gap-continuation` (new). This is a *continuation* family, not a
gap fade.

**One-line hypothesis.** A large opening gap is a repricing of information.
When the first 30 minutes confirm the direction of the gap, the repricing is
incomplete and the move continues through the session. A gap that is not
confirmed is a different event and is not traded.

**Development window.** 2016-01-04 .. 2023-12-29 only. The shared 1-minute
panel is requested with `end=2023-12-29`; no 2024-2026 bar enters any signal,
weight or statistic. The holdout is not loaded for design.

---

## 1. Why this should exist

The gap is the market's first public estimate of overnight information. If the
estimate is correct, the first 30 minutes should trade in the gap direction as
the rest of the market adjusts. If the gap is a liquidity overreaction, the
first 30 minutes should fail and the gap should fade. These are opposite
trades. The family tests the continuation side only, because the book is
long-only.

The signal is deliberately *not*:

- a short-term reversal (the previous day's close-to-open move is the input,
  and the trade is in the same direction);
- an opening-range breakout (the trigger is the 10:00 close versus the 09:30
  open, not a range boundary);
- a trend gate, volatility target, drawdown event, ML model or
  relative-strength input.

## 2. Exact rules

All times are US/Eastern. Bar offsets are 0-based from 09:30 (offset 0) to
15:59 (offset 389). A weight set after bar `i` fills at bar `i+1`'s open.

| Item | Rule |
|---|---|
| Signal asset | QQQ |
| Trade asset | TQQQ (3x QQQ), weight 1.0, cash otherwise |
| Gap | `QQQ_open(09:30) / QQQ_close(previous 15:59) - 1` |
| Confirmation | `QQQ_close(10:00) / QQQ_open(09:30) - 1` |
| Entry | `gap >= +0.50%` **and** `r30 >= +0.20%`; buy at the **10:01 open** |
| Exit | sell at the **15:59 open** (target zero at the 15:58 close) |
| Hold | 10:01 open through 15:58 close = 358 minutes |
| Overnight | flat; the next-open exit is a neighbour, not the primary |
| Short side | not traded (long-only book); gap-down continuation is out of scope |

**Decision clock.** The gap is known at 09:30. The confirmation is the close
of the 10:00 bar. The decision is taken at 10:00:00, after that close, and the
fill is the next bar's open at 10:01. There is no same-bar fill and no use of
the 10:01 bar in the signal. The exit is decided at the 15:58 close and filled
at the 15:59 open.

**Session filter.** Only sessions with 390 one-minute bars are traded. Short
and half sessions are skipped; they are still used to update the previous
close. This is a data-quality rule, not a regime filter.

## 3. Pre-registered centre and grid

Centre: **gap >= 0.50% QQQ, r30 >= 0.20%, 10:01 -> 15:59, TQQQ 1.0.**

The 8-cell grid varies the two economic thresholds and holds the clock fixed:

| Cell | Gap | r30 |
|---|---:|---:|
| 1 | 0.30% | 0.00% |
| 2 | 0.30% | 0.20% |
| 3 | 0.50% | 0.00% |
| 4 | **0.50%** | **0.20%** (centre) |
| 5 | 0.75% | 0.00% |
| 6 | 0.75% | 0.20% |
| 7 | 1.00% | 0.00% |
| 8 | 1.00% | 0.20% |

The centre is chosen because 0.50% QQQ is roughly a 1.5% TQQQ gap, a visibly
large overnight repricing, and 0.20% is a first-30-minute move that is large
enough not to be one-tick noise. It is not chosen by scanning the return
surface; the grid is reported in full and the centre is allowed to be
non-best.

## 4. Primary bar and kill criteria (stated before results)

Primary performance is the 1 bp headline. The strategy must also survive
5 bp and 10 bp. A candidate is **killed** if any of the following holds:

1. Dev CAGR at 1 bp is below the 36.72% TQQQ development bar.
2. 5 bp CAGR is below zero (cost-fragile).
3. Fewer than 30 independent events or fewer than 100 fills (dead strategy).
4. Fewer than 6 of the 8 grid cells have positive 1 bp CAGR (parameter
   fragility).
5. Negative CAGR in 2 or more of the 3 subperiods (2016-19, 2020-21,
   2022-23).
6. Placebo random-day p-value above 0.10 (the signal does not beat random
   timing).
7. Daily-return correlation above 0.70 with any of the nine current winners
   (not independent).
8. Any weight drift before a truncation cut (look-ahead).

Criterion 1 is the program's absolute-return bar. Criteria 2-8 are robustness
and integrity gates. A strategy can pass 2-8 and still fail 1; that is reported
as a risk-adjusted pass, not as an above-TQQQ replacement.

## 5. Placebos

- **Random days:** draw the same number of full sessions at random, keep the
  10:01 -> 15:59 clock. 200 draws. This asks whether the gap/confirmation
  signal selects better days than the calendar.
- **Random entry:** keep the signal days, move the entry uniformly over
  10:01-10:30, keep the 15:59 exit. 200 draws. This asks whether 10:01 is the
  right moment.
- **Stale signal:** use the previous session's gap and confirmation flags.
  This asks whether the same-day signal is doing the work.
- **Controls:** gap-only (no confirmation), confirmation-only (no gap), and
  gap-up with a down first 30 minutes (the fade). These separate the two legs
  of the signal.

## 6. What would falsify the hypothesis

- A positive gap-only or fade result as strong as the confirmed-gap result
  would mean the confirmation is not the mechanism.
- A flat or negative event mean with a t-stat near zero would mean the gap
  continuation is not present in this sample.
- A random-day placebo that matches the real result would mean the edge is
  calendar drift, not the gap.
- A 2023-only collapse with no earlier evidence would mean the effect is
  regime-specific and should not be promoted.

The report applies these tests and states which ones fired.
