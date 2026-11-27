# Hypothesis: opening-drive continuation with a five-session hold

**Slug:** `family-intraday-microstructure-b`  
**Family:** `intraday-microstructure`  
**Window:** development only, 2016-01-04 -> 2023-12-29. The 2024-2026
holdout was never used for a signal, weight, parameter or metric.  
**Status:** center and 8-cell grid frozen before the final `strategy.py` run.
The center was chosen from a development-window screen; the selection path is
disclosed in section 6.

---

## 1. Mechanism

TQQQ is a 3x Nasdaq-100 ETF. Its return is mostly earned overnight, but the
intraday open-to-close drift is positive on average and is concentrated in
sessions where buyers absorb the opening auction and keep control. The
opening drive is measured with two simple, causal intraday reference points:

1. **Session open.** The 09:30 opening auction price. A price above the open
   means the session is healing the opening imbalance.
2. **Session VWAP.** The volume-weighted average of QQQ typical price over
   the first 15 minutes. A price above VWAP means the marginal buyer is
   paying above the average traded price, not chasing a fading print.

When QQQ is above both at 09:45, the rest of the session has historically
continued higher. The effect is real but small on a one-day horizon: the
10:00 version earns +0.123%/day from 10:00 to the close on signal days versus
+0.029%/day unconditionally. A one-session strategy is therefore too
turnover-heavy to survive realistic costs. The hypothesis is that the edge
is in **which days** are selected, not in a single close, so the trade should
be held for a small block of sessions:

- five sessions is one trading week, the upper end of the mandate's 2-5
  session range;
- it amortizes the entry/exit cost over five sessions instead of one;
- it captures the overnight and multi-day continuation that the one-session
  version gives up;
- it keeps the decision rule purely intraday: the entry is a 09:45
  price-versus-open/VWAP comparison, not a daily trend, volatility or
  relative-strength regime.

The risk control is time-based: exit at the end of the fifth session and
stay in BIL overnight. No daily SMA, no volatility/drawdown regime, no
relative strength, no hard stop in the primary. The close-auction-strength
exit, the entry-day-VWAP stop, a hard stop and a trailing stop are tested as
variants/overlays and reported.

## 2. Exact frozen rules

Universe: adjusted 1-minute QQQ, TQQQ and BIL, regular session 09:30-16:00
ET. Long only, weights >= 0, sum <= 1. TQQQ is the risk asset; BIL is the
flat asset.

1. **Signal at 09:45 ET.**
   - `p` = QQQ close of the 09:45 bar.
   - `open` = QQQ open of the 09:30 bar.
   - `vwap` = sum(typical price x volume, 09:30..09:45) /
     sum(volume, 09:30..09:45), where typical price = (high+low+close)/3.
   - `signal = (p > open) and (p > vwap)`. Threshold 0.
2. **Entry.** If flat and `signal` is true, target 100% TQQQ on the 09:45 bar
   close. The harness fills at the 09:46 open.
3. **Hold.** Exactly five sessions; the entry session is session 1. The
   position is held overnight between sessions.
4. **Exit.** At the 15:58 close of the fifth session, target 100% BIL. The
   harness fills at the 15:59 open, so the book is flat overnight. A
   half-day uses its own last bars.
5. **Overlap.** Intermediate 09:45 signals are ignored while a five-session
   block is open. After the exit, the next 09:45 signal can start a new
   block.
6. **Costs.** 1 bp headline; 5 bp and 10 bp reported. 2% band, next-open
   fills. No full-sample normalisation.
7. **No stop / no vol target** in the primary. The stop overlays are
   disclosed in the report and rejected.

No look-ahead: the 09:45 signal uses bars through 09:45; the exit is set on
the 15:58 bar and fills at 15:59; every fill is at the next bar's open. The
session open is the 09:30 bar open. There is no use of the prior day's
close, a daily moving average, a volatility estimate or a relative-strength
ratio.

## 3. Why it might beat TQQQ, and the arithmetic against it

The harness-computed development benchmark is TQQQ **36.15% CAGR / 82.29%
max DD / 0.80 Sharpe** (the brief quotes 36.72% / 82.29% / 0.82; the 0.57 pp
CAGR difference is the harness's 1-minute mark convention). The strategy is
long TQQQ about 80% of the time and BIL about 20%. It must therefore:

- capture most of TQQQ's upside during the selected blocks, and
- avoid enough of the drawdowns to bring the max DD below 82%, ideally below
  60%.

The 09:45 filter selects roughly 45% of sessions. With five-session blocks
and re-entry after each block, TQQQ exposure is about 80%, so the strategy is
still a high-beta product. The claimed edge is that the selected blocks have
a higher geometric return and a lower drawdown than the unconditional
TQQQ path. The one-session screen shows the selection is not enough by
itself; the five-session hold is doing most of the work by capturing the
overnight/multi-day drift and by earning enough gross return to absorb the
in/out switching cost. It makes fewer round trips than the one-session
version (323 vs 919), but total traded notional is higher because each
switch trades both the TQQQ and BIL legs and the strategy is in TQQQ about
80% of the time.

The honest prior before the final run was **40-50% CAGR / 55-65% DD / 0.9-1.1
Sharpe at 1 bp**, with the 5 bp result near the 36.72% bar and the 10 bp
result below it. The result is expected to be a **cost-robust dev pass at
1-5 bp, not a 10 bp strategy**, and the hold-length plateau was expected to
be the main fragility.

## 4. Pre-registered 8-cell grid

The grid is frozen at the center and run once. All cells use the same entry
signal (QQQ above session open and session VWAP), the same BIL flat asset,
the same 2% band and next-open fills. "Close-strength exit" means: at 15:00,
hold overnight only if QQQ is above both the session open and the session
VWAP (09:30..15:00); otherwise exit at 15:01.

| # | Cell | Decision | Threshold | Hold | Exit |
|---:|---|---:|---:|---:|---|
| 1 | **center** | 09:45 | 0 bp | 5 | fixed, 15:59 |
| 2 | decision 10:00 | 10:00 | 0 bp | 5 | fixed, 15:59 |
| 3 | decision 10:30 | 10:30 | 0 bp | 5 | fixed, 15:59 |
| 4 | threshold 20 bp | 09:45 | 20 bp | 5 | fixed, 15:59 |
| 5 | threshold 50 bp | 09:45 | 50 bp | 5 | fixed, 15:59 |
| 6 | hold 2 | 09:45 | 0 bp | 2 | fixed, 15:59 |
| 7 | hold 3 | 09:45 | 0 bp | 3 | fixed, 15:59 |
| 8 | close-strength exit | 09:45 | 0 bp | 5 | 15:00 close check |

The center is cell 1. The center is **not** the highest 1 bp Sharpe cell:
cell 8 has a higher 1 bp Sharpe (1.06 vs 0.97) but a lower 5 bp CAGR (32.87%
vs 37.39%). The center is chosen for cost robustness and simplicity, not for
the best single number. The threshold-10 bp cell is **not** in the
pre-registered grid; it is reported as an exploratory sensitivity only.

## 5. Falsifiers (fixed before the final run)

| # | Falsifier | What it would mean |
|---:|---|---|
| F1 | 5 bp CAGR <= 36.72% | The result is too turnover-heavy to count. |
| F2 | 10 bp CAGR <= 36.72% | The edge is not investable at realistic costs. |
| F3 | Shuffled-signal placebo p > 0.10 | The 09:45 day selection has no timing edge. |
| F4 | Hold-length neighbors (N=4, N=6) are far below the N=5 result | The N=5 result is a path artifact, not a plateau. |
| F5 | 10:00 and 10:30 cells do not beat the bar | The 09:45 minute is a local spike, not a robust opening-drive window. |
| F6 | Entry-day-VWAP stop improves CAGR/DD | The fixed hold is the wrong risk control. |
| F7 | Hard/trailing stop improves DD without hurting CAGR | A stop overlay is load-bearing and should be disclosed. |
| F8 | 2016-2019 or 2020-2023 is below the bar | The result is not consistent across halves. |

The report must state each result, including failures, and must not re-tune
after a holdout. The 2024-2026 window remains untouched.

## 6. Selection path disclosure

The center and grid were fixed after a development-window screen of the same
2016-2023 data. The screen tested decision times 09:40/09:45/09:50/10:00/
10:30, thresholds 0/10/20/50 bp, hold lengths 2-7 and fixed/close-strength
exits. The center was chosen because:

- 09:45 is the earliest checkpoint in the mandate and leaves the most of the
  session for continuation; the VWAP uses the opening auction plus 15
  one-minute bars.
- Five sessions is the upper end of the lead's 2-5 session instruction and
  minimizes the number of round trips; it is a natural one-week holding
  period.
- The fixed exit is simpler and more cost-robust than the close-strength
  exit at 5 bp.

This is **not a blind pre-registration**. The center is also a local peak in
the hold-length curve, and the exploratory 10 bp threshold is much better
than the pre-registered 20 bp cell. The report flags both as selection risk.
The grid is reported in full, including the cells that fail.

## 7. Expected result and decision rule

- **Pass at 1 bp** if CAGR > 36.72%, max DD < 60% and Sharpe > 0.82.
- **Pass at 5 bp** if CAGR > 36.72% and max DD < 82.29%.
- **Fail at 10 bp** is acceptable only if reported; it means the strategy is
  a 1-5 bp strategy, not an all-cost winner.
- If the center fails at 5 bp, the best honest failure is reported and the
  family is not changed.

Expected: 1 bp 40-50% CAGR / 55-65% DD / 0.9-1.1 Sharpe; 5 bp 30-40% CAGR;
10 bp 20-30% CAGR. The likely verdict is a fragile dev pass, not a robust
family winner.

## 8. Family purity and distinctness

- **No daily trend SMA, no volatility/drawdown regime, no relative
  strength.** The only signal inputs are QQQ's 09:30 open, its 09:45 close
  and the 09:30-09:45 VWAP. The exit is a fixed session count.
- **Intraday-microstructure family.** The mechanism is the opening drive
  (price vs opening auction and opening VWAP), not a daily regime.
- **Distinct from `orb-tqqq-volume`:** that strategy uses a 30-minute opening
  range, volume/ATR filters, an ATR stop and a one-session hold. This one
  uses price vs open/VWAP, no volume/ATR filter, no stop, and a five-session
  hold.
- **Distinct from `intraday-close-momentum`:** this signal is at 09:45, not
  at the close.
- **Distinct from the daily SMA baseline:** no moving average or daily trend
  state is used.
- **BIL is the mandated flat asset**, not a hidden cash return.

## 9. Reproduction

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
$env:BT_THREADS = "1"
python research\new\family-intraday-microstructure-b\strategy.py
```

`strategy.py` writes `result.json` and prints the 1/5/10 bp headline, the
8-cell grid at 1 bp and 5 bp, yearly returns and the placebo.
