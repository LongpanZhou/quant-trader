> **Post-test note (2026-11-27):** this file is the pre-registration, not
> the result. The frozen development result is in `../SUMMARY.md`; the
> full 2016-2026 audit, the post-tune variants and the research-validity
> verdicts are in `../WHY_UNDERPERFORM.md`. The published website curve is
> the freeze named in `../SUMMARY.md`.

# Donchian Alignment Ladder (revisit)

**Slug:** `donchian-breakout`
**Status:** **PAUSED — spec/code/report skeleton only.** No backtest has been run
for this rebuild, no `result.json` exists yet, and holdout 2024-2026 has not
been inspected. Backtests resume only after lead/user authorization.
**Dev window:** 2016-01-04 → 2023-12-29
**Original:** `research/agents/donchian-breakout` (shared 165-day QQQ SMA base)

---

## 1. Extracted idea

The genuinely new part of the original strategy was **the 55-bar 5-minute
Donchian breakout as an entry trigger, with ATR/stop management** — not the
165-day QQQ SMA gate or the 0/1 TQQQ/BIL book. Those were the shared base.

A single 55-bar channel by itself is not a complete strategy. The rebuild
therefore keeps the breakout/stop idea but changes the *signal breadth*, the
*holding period*, the *asset ladder* and the *sizing*.

---

## 2. Why the obvious strip-down is not enough

A pre-pause, dev-only calibration (2016-01-04..2023-12-29, 5-minute QQQ,
1 bp, 1-minute marks) tested the single-sleeve version without the 165-day
gate. These are **calibration numbers for the old single-sleeve design, not
results for the new strategy**:

| Single-sleeve variant | Dev CAGR | Dev max DD | Dev Sharpe | Corr vs 165d base |
|---|---:|---:|---:|---:|
| QQQ 55/20, 2.5×ATR trailing | −0.76% | 31.71% | −0.01 | 0.39 |
| QQQ 55/20, 3.0×ATR trailing | 2.13% | 23.50% | 0.24 | 0.41 |
| QQQ 55/20, no ATR stop | 2.31% | 27.90% | 0.25 | 0.43 |
| TQQQ 55/20, 2.5×ATR, 100% | 6.83% | 57.39% | 0.37 | 0.41 |
| TQQQ 55/20, 2.5×ATR, 50% | 5.56% | 32.48% | 0.42 | 0.41 |
| TQQQ 55/20, 2.5×ATR, vol-target 25% | 9.65% | 19.23% | 0.79 | 0.40 |

The raw QQQ breakout is too weak to stand alone, and the TQQQ vol-targeted
version has a better Sharpe but **29,494 fills** because it resized every bar.
That is why the rebuild uses a *multi-horizon alignment ladder* and resizes
only when the alignment changes. These calibration numbers will be replaced
by the final strategy's own dev results after authorization.

---

## 3. Hypothesis

> Breakout trends are more reliable when short, medium and long breakout
> horizons agree. The number of aligned Donchian horizons is a real-time
> measure of trend breadth. Scaling exposure from BIL to QQQ to TQQQ with that
> alignment captures trend persistence and cuts whipsaw exposure, while
> producing a return stream that is distinct from a slow 165-day MA gate.

The old base asks one question — "is QQQ above its 165-day average?" — and
then holds 100% TQQQ. The rebuild asks three questions at three horizons and
uses the answers both to select the asset and to size the position. The
holding period is a blend of ~100 minutes, ~4.6 hours and ~5 days, not a
single daily regime.

---

## 4. Standalone spec

### Universe and data

- QQQ (signal asset), TQQQ (leveraged expression at maximum alignment), BIL
  (defensive asset).
- Adjusted 1-minute data, regular session only.
- Signals on 5-minute bars; equity marked on 1-minute bars.
- Dev: 2016-01-04..2023-12-29. The first 390 five-minute bars (~5 sessions)
  are indicator warmup.

### Sleeves (all on QQQ 5-minute bars; current bar excluded)

| Sleeve | Entry | Exit |
|---|---|---|
| Fast | close > highest high of prior **20** bars | close < lowest low of prior **10** bars **or** close < peak-since-entry − **2.5×ATR(14)** |
| Medium | close > highest high of prior **55** bars | close < lowest low of prior **20** bars |
| Slow | close > highest high of prior **390** bars (5 days) | close < lowest low of prior **156** bars (2 days) |

Each sleeve is a state machine: flat → long on its entry channel, long → flat
on its exit channel (or the fast ATR stop). The fast sleeve's `peak` is the
highest QQQ close since its entry; ATR is Wilder ATR(14) on the 5-minute QQQ
bars.

### Alignment ladder

`A = fast + medium + slow` (0..3).

| Alignment | Target |
|---:|---|
| 0 or 1 | 100% BIL |
| 2 | 100% QQQ |
| 3 | TQQQ at `w`, remainder BIL; `w = clip(0.30 / annATR_TQQQ, 0.20, 1.0)` |

`annATR_TQQQ = ATR(14)/TQQQ_close × sqrt(252×78)` at the bar when the
alignment changes to 3. `w` is held until the alignment changes, so the
strategy does not resize every bar. The 30% volatility target and 20% floor
are risk-budget choices, not optimised parameters.

### Execution, costs and constraints

- `weights[i]` is set at the close of 5-minute bar `i` and filled at the open
  of bar `i+1`.
- 2% band; 1 bp headline, 5 bp and 10 bp sensitivity.
- Long-only, weights sum to 1, gross exposure ≤ 1.
- No 165-day (or any 100–250-day) moving-average gate. The 165-day baseline is
  computed **only** for the correlation benchmark and is never an input to
  `build_weights`.
- No shorting; no borrow cost needed.

---

## 5. Expected correlation and distinctness

**Expected daily-return correlation vs the old 165-day base: 0.35–0.60.**
The old base is 100% TQQQ on ~78% of days. The rebuild is TQQQ only at 3/3
alignment (expected ~20–30% of bars), QQQ at 2/3, and BIL at 0–1/3. The QQQ
middle state and the BIL states dilute the TQQQ beta. The pre-pause
single-sleeve QQQ version measured 0.39; the slow sleeve and the TQQQ state
could raise that. The upper end of the range is deliberately honest: if the
measured dev correlation lands at 0.55–0.60 the strategy is too close to the
old base and must be revised before it can pass.

**Falsifier:** dev correlation ≥ 0.60 → the rebuild is still the old base in
disguise.

**Other distinctness:** the slow 390-bar sleeve gives a multi-day holding
period the old 55-bar overlay did not have; the alignment ladder changes the
asset (QQQ vs TQQQ) as well as the size; the fast ATR stop is a per-sleeve
risk rule rather than the old daily MA exit.

---

## 6. What would falsify the strategy

1. Dev correlation with the 165-day base **≥ 0.60**.
2. Dev 1 bp CAGR **≤ 0** or Sharpe **< 0.30**.
3. The alignment ladder is **not better than the best single sleeve on a
   risk-adjusted basis, and its correlation is not lower** — i.e. the breadth
   signal adds nothing.
4. 5 bp or 10 bp CAGR loses **more than half** of the 1 bp edge (turnover too
   high).
5. A ±1-step parameter change flips the sign or changes CAGR by **> 50%**
   (parameter cliff).
6. Negative in **two of three** sub-periods (2016–19, 2020–21, 2022–23).
7. Placebo: the actual CAGR is **not above the 95th percentile** of 200
   circular-shift placebos (p > 0.05).
8. Fewer than 100 alignment changes/round trips and a block-bootstrap
   **p > 0.05**.
9. Alpha vs QQQ **≤ 0** — the strategy is only QQQ beta, not a breakout edge.

---

## 7. Provenance

| Rule / claim | Source | Role | Evidence |
|---|---|---|---|
| 20-bar and 55-bar breakout entries; 10-bar and 20-bar exits | Original Turtles, *The Original Turtle Trading Rules* (2003), <https://therobusttrader.com/wp-content/uploads/OriginalTurtle-Trading-Rules.pdf>; mirror <https://www.tradingblox.com/originalturtles/originalturtlerules.htm> | inspired rule | System 1: 20-day breakout / 10-day exit. System 2: 55-day breakout / 20-day exit. Breakout = preceding N days' high/low. |
| 2N volatility stop | Same Turtle rules | inspired and adapted | The Turtles used a 2N stop. This rebuild uses 2.5×ATR(14) on the fast sleeve; the multiplier is an own risk choice. |
| Current bar excluded from the channel | proea.app, *Donchian Channel Strategy* (2026), <https://proea.app/en/blog/donchian-channel-strategy>; Titan FX, <https://research.titanfx.com/technical-analysis/other-indicators/what-is-donchian-channel> | inspired rule | StockCharts: "Price Channels are based on prices prior to the current period." Used for `prior_max`/`prior_min`. |
| 390/156 slow sleeve (5-day / 2-day) | Own extension | own test | No external source prescribes a 5-day/2-day 5-minute channel. It is the slow trend leg of the ladder, not a 100–250-day MA. |
| Three-horizon alignment ladder | Own synthesis | own test | No external source. The breadth/alignment mechanism is the new idea. |
| TQQQ volatility target (30%, 20% floor) | Own risk rule | own test | Standard volatility targeting; not a paper-specific rule. The 30%/20% choices are risk-budget defaults to be checked in the ±1-step table. |
| 165-day QQQ SMA baseline | `research/README.md` / `research/bt.py` (internal) | benchmark only | Used only to compute the correlation and the old-base comparison. It is **not** an input to `build_weights`. |
| Dual Thrust range breakout | QuantConnect, *Dual Thrust Trading Algorithm* (2018), <https://www.quantconnect.com/research/15258/dual-thrust-trading-algorithm/> | tested only | Sibling breakout idea; not used in the core ladder. The original's dual-thrust variant is documented in the original report. |

**Rejected as the base:**

- **165-day QQQ SMA gate.** Banned shared base; also the reason the original
  was 0.86-correlated with every other strategy.
- **Single 55-bar 5-minute overlay.** Pre-pause dev CAGR −0.76% (QQQ) to
  +9.65% (TQQQ vol-targeted), but the TQQQ version had 29,494 fills. It is a
  component, not a standalone strategy.
- **Classic standalone 20/10 and 55/20 systems.** They were tested in the
  original and failed on minute bars; they survive here only as sleeves inside
  the alignment ladder.
- **Dual-thrust day trade / flat-overnight variants.** Tested in the original
  and failed; not used.

---

## 8. Test plan after authorization

All runs are dev-only (2016-01-04..2023-12-29) until the lead runs the frozen
strategy on the holdout once.

1. **Headline:** dev 1 bp / 5 bp / 10 bp CAGR, max DD, Sharpe, fills,
   turnover, exposure; 1-minute marks.
2. **Correlation:** daily returns vs the 165-day base, dev period.
3. **Parameter neighbourhood (one-at-a-time):**
   - fast entry 15 / 20 / 25;
   - medium entry 45 / 55 / 65;
   - slow entry 300 / 390 / 480;
   - ATR k 2.0 / 2.5 / 3.0;
   - target vol 0.25 / 0.30 / 0.35.
   Chosen values must sit on a plateau.
4. **Sub-periods:** 2016–19, 2020–21, 2022–23.
5. **Placebo:** 200 circular shifts of the alignment/weight series; report the
   actual CAGR percentile and p-value.
6. **Event count:** number of alignment changes and round trips; block
   bootstrap p-value if < 100 events.
7. **Benchmarks:** TQQQ, QQQ and BIL buy-and-hold on dev; SPY unavailable for
   2016–2023 locally; original strategy's 10y/5y from its `result.json` for
   the lead's comparison.
8. **Correlation with other rebuilds:** lead computes after all rebuilds;
   target < 0.70.

Command (after authorization only):

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
cd C:\Users\27175\Desktop\quant-trader-research
python research\revisit\donchian-breakout\strategy.py --dev
```

`strategy.py` refuses to run without `--dev`. It loads only the dev window and
writes `result.json` with `windows.dev`; `holdout`, `10y` and `5y` stay empty
for the lead's frozen run.

---

## 9. Results (PENDING — backtests paused)

No final results yet. The table below is the shape the frozen run will fill.

| Window | Cost | CAGR | Max DD | Sharpe | Fills | Turnover | Exposure |
|---|---|---:|---:|---:|---:|---:|---:|
| dev | 1 bp | — | — | — | — | — | — |
| dev | 5 bp | — | — | — | — | — | — |
| dev | 10 bp | — | — | — | — | — | — |
| holdout | 1 bp | — | — | — | — | — | — |
| 10y | 1 bp | — | — | — | — | — | — |
| 5y | 1 bp | — | — | — | — | — | — |

Correlation vs 165-day base: **—** (dev, to be measured).
Correlation vs other rebuilds: **—** (lead, after all rebuilds).

---

## 10. Limitations and open questions

- **Data.** Only QQQ/TQQQ/BIL have 2016–2023 minute data locally. SPY in the
  dukascopy cache is 2026-only, so the SPY benchmark and any sector/bond/gold
  extension are unavailable for dev. The rebuild stays in the QQQ/TQQQ/BIL
  universe.
- **Long-only.** `bt.py` does not model shorts; the ladder cannot profit from
  down-breakouts. A long/short version would need a different engine and a
  borrow-cost model.
- **Turnover.** The alignment ladder is designed to resize only when the
  alignment changes, but the fast sleeve can still flip often. The 5 bp/10 bp
  sensitivity is the key test.
- **Path dependence.** The 10y/5y windows overlap the holdout and must be run
  by the lead, not by this agent.
- **Not a TQQQ-beating strategy by design.** The goal is a distinct, complete
  strategy with a low correlation to the old base. If it has a positive
  risk-adjusted edge and survives the falsifiers, it is a useful diversifier
  even at a lower CAGR than the original's published windows.
