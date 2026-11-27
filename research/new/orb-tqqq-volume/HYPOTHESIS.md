# Hypothesis: TQQQ opening-range breakout with volume/ATR confirmation

**Slug:** `orb-tqqq-volume`  
**Status:** final rules and grid frozen before the final `strategy.py` run.
The mechanism was chosen from a development-window screen (2016-2023),
documented in the scratch scripts in this directory.  
**Window:** development only, 2016-01-04 -> 2023-12-29. The 2024-2026
holdout was never loaded, inspected or used for any choice.

The mechanism and thresholds below were chosen from a development-window
screen of the same 2016-2023 data (`explore1.py` .. `explore6.py`,
`ablations.py`); no holdout data was read. The eight-cell grid at the end is
the only grid used for the final result. Scratch screens are kept in this
directory so the selection path is auditable.

---

## 1. Mechanism

TQQQ is a 3x Nasdaq-100 ETF. Its return is mostly earned **overnight**: on the
2016-2023 development window the close-to-close CAGR is 36.15%, the
open-to-close CAGR is 11.89%, and the close-to-open CAGR is 21.62%; about 64%
of the log return is overnight. A strategy that is flat every night therefore
forgoes most of the buy-and-hold return and must earn its keep from intraday
selection.

The hypothesis is that an opening-range breakout on TQQQ has positive
intraday continuation **only when the move is confirmed by participation and
by the prior day's volatility state**:

1. **Gap-up precondition.** A breakout is more likely to hold when the
   session opens above the prior close. A gap-up is the market's first
   aggregate vote; a breakout above the opening range then has dip-buyers
   behind it. Gap-down sessions are excluded because the screen shows their
   post-10:00 drift is negative.
2. **Volume confirmation is a band, not a maximum.** The opening 30-minute
   volume relative to the prior 20 sessions must be in a normal-to-expanded
   band. A dead tape (ratio below ~0.7) has no participation; a 2x+ news
   spike is more often exhaustion/climax than a tradeable trend. The band
   [0.7, 1.6] is the pre-registered expression of "participation, not
   blow-off".
3. **ATR confirmation.** The opening range must not already be a large
   fraction of the daily ATR. If the first 30 minutes has consumed most of
   the day's expected range, the breakout has little room left. The filter is
   `(OR high - OR low) <= 0.6 * ATR14`.
4. **Volatility-scaled disaster stop.** A fixed percentage stop is either
   too tight in high-vol regimes (whipsaw) or too wide in calm ones. The stop
   is `entry - 0.55 * ATR14`, checked on every 1-minute low and filled at the
   next open. The screen shows the stop is load-bearing: without it the
   strategy's CAGR falls from ~18% to ~13% and its drawdown rises from ~21%
   to ~35%.
5. **Exit at the close.** The position is held to the last minutes of the
   session to capture the intraday drift; it is flat overnight. A fixed
   profit target is expected to hurt because the payoff is in the right tail
   (the `core_plus_3pct_target` cell tests this).

The intended edge is therefore a **conditional intraday continuation** on
gap-up days with healthy participation, protected by a volatility-scaled
stop. It is not a claim that the opening range is magic: the placebo tests
below are designed to show whether the day selection or the breakout timing
carries the result.

## 2. Exact rules

Universe: adjusted 1-minute TQQQ, regular session 09:30-16:00 ET. Flat asset:
cash by default (a BIL-flat variant is reported as a cost sensitivity).
Long only, one position at a time, weights sum to <= 1.

1. **Opening range.** `or_hi = max(TQQQ high, 09:30-09:59)`,
   `or_lo = min(TQQQ low, 09:30-09:59)`, `or_vol = sum(volume, 09:30-09:59)`.
   A session needs at least 10 one-minute bars in the range.
2. **Session filters (all known by 10:00).**
   - `gap = today_open / prior_close - 1 > 0`.
   - `rvol = or_vol / mean(or_vol of the prior 20 sessions)` in `[0.7, 1.6]`
     (all 20 prior sessions required; cash until the baseline exists).
   - `(or_hi - or_lo) <= 0.6 * ATR14`, where `ATR14` is the mean true range
     of the prior 14 sessions (shifted one session).
3. **Entry.** First 1-minute bar at or after 10:00 whose **close > or_hi**
   (zero buffer), at most 60 minutes before the session close. Set the
   target weight to 100% TQQQ on that bar's close; the harness fills at the
   next bar's open.
4. **Stop.** `entry_fill - 0.55 * ATR14`. Check every subsequent 1-minute
   low. On a breach, set the weight to 0 on that bar's close; fill at the
   next open. If a bar breaches the stop and a target in the same minute,
   the stop is assumed first (conservative).
5. **Exit.** Stop, optional target, or the second-to-last bar of the session.
   The second-to-last-bar signal fills at the last bar's open, so the book is
   flat overnight. Half days use their own session end (13:00).
6. **Costs.** 1 bp headline; 5 bp and 10 bp reported. Next-open fills,
   2% band.

No look-ahead: the opening range ends at 09:59; the gap uses the 09:30 open;
the volume baseline is the prior 20 sessions; ATR is prior 14 sessions; every
fill is at the next bar's open. No full-sample normalisation.

## 3. Why it might beat TQQQ, and the arithmetic against it

TQQQ's 36.72% dev CAGR is the bar. The strategy is capped at 1x TQQQ and is
flat overnight, so it gives up the ~21.6%/yr overnight drift. It must
therefore earn more than 36.72% from the ~11.9%/yr unconditional intraday
drift, i.e. the per-day geometric intraday edge needs to be about **2.8x**
the unconditional one (0.1245%/day vs 0.0447%/day), or ~25 pp more annual
return. The screen's best conditional cells are ~0.3-0.5% per trade on
30-60 trades/yr, which compounds to roughly 15-25%/yr, not 37%/yr.

So the honest prior is that **this mandate probably cannot pass**. The
strategy can still be a useful result if it delivers a much better Sharpe /
Calmar than TQQQ at a lower drawdown, and if the falsifiers below are
reported rather than tuned away.

## 4. Falsifiers (fixed before the final run)

| # | Falsifier | What it would mean |
|---|---|---|
| F1 | The selected ORB days' mean open-to-close return is not above the unconditional +0.10%/day. | The day filter has no selection edge. |
| F2 | The random-day placebo (same entry-time mix, same stop) matches the strategy, one-sided p > 0.10. | The selected days are not special. |
| F3 | Random entry times on the *same* days match or beat the strategy. | The opening-range timing is not the edge. |
| F4 | Removing the volume band improves CAGR and Sharpe. | Volume confirmation is not useful. |
| F5 | Removing the ATR stop improves CAGR or DD. | The stop is not load-bearing. |
| F6 | The failed-breakdown reclaim variant beats the breakout variant. | The direction/mechanism is wrong. |
| F7 | At 5 bp the CAGR falls below QQQ buy-and-hold (18.9%). | The edge is too cost-sensitive to be investable. |
| F8 | Dev CAGR <= 36.72%. | Fails the mandate's pass bar. |

The report must state each result, including failures, and must not re-tune
after seeing the holdout.

## 5. Pre-registered parameter grid (8 cells, 1 bp)

Fixed constants: entry buffer 0 bps, 60-minute entry cutoff, one trade per
session, 100% TQQQ while in, cash flat, 2% band, next-open fills.

| # | Cell | OR min | Gap | Volume band | OR/ATR cap | Stop | Target |
|---:|---|---:|---|---|---:|---:|---:|
| 1 | **core** | 30 | >0 | [0.7, 1.6] | 0.6 | 0.55 ATR | none |
| 2 | no volume filter | 30 | >0 | off | 0.6 | 0.55 ATR | none |
| 3 | no OR/ATR filter | 30 | >0 | [0.7, 1.6] | off | 0.55 ATR | none |
| 4 | tighter stop | 30 | >0 | [0.7, 1.6] | 0.6 | 0.35 ATR | none |
| 5 | wider stop | 30 | >0 | [0.7, 1.6] | 0.6 | 0.75 ATR | none |
| 6 | shorter range | 15 | >0 | [0.7, 1.6] | 0.6 | 0.55 ATR | none |
| 7 | longer range | 45 | >0 | [0.7, 1.6] | 0.6 | 0.55 ATR | none |
| 8 | profit target | 30 | >0 | [0.7, 1.6] | 0.6 | 0.55 ATR | +3% |

The plateau, not the best cell, is the result. Expected effect for the core:
**15-25% CAGR, 20-35% max DD, Sharpe 0.9-1.2**, with a likely failure on the
36.72% CAGR bar.

## 6. Distinctness from existing work

- `research/agents/opening-range-breakout`: QQQ/TQQQ ORB but **held overnight
  for weeks** behind a 165-day QQQ SMA; the intraday-only variants failed.
  This strategy is intraday-only, flat every night, has no moving-average
  gate, and uses volume/ATR confirmation with an ATR stop.
- `research/revisit/opening-range-breakout`: QQQ **failed-breakdown reclaim**
  (reversal), 0.5% risk sizing. This is TQQQ **breakout continuation** with
  100% weight. The reclaim is tested here as a falsifier and loses.
- `research/revisit/volume-orderflow`: five-session hold after a
  volume-absorption event. This is a one-session intraday trade.
- `research/agents2/volume-orderflow`, `agents2/intraday-momentum`: different
  assets, holding periods and signals. No code or weights are reused.

## 7. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\orb-tqqq-volume\strategy.py
```

`strategy.py` writes `result.json` and prints the dev 1/5/10 bp results and
the eight-cell grid.
