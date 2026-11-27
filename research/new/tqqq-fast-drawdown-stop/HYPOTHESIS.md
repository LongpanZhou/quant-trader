# Fast-drawdown brake on TQQQ

**Status:** pre-registered before the final 1-minute production run. The rules
and the 8-cell grid were fixed before that run; later edits corrected
descriptive numbers only (open-to-open spell moves, sigma arithmetic) and did
not change the rules or the grid.
**Author:** research subagent, 2026-11-27.
**Directory:** `research/new/tqqq-fast-drawdown-stop/`
**Development window only:** 2016-01-04 .. 2023-12-29. The 2024-2026 holdout
is not loaded, inspected or used for selection.

---

## 0. Scope

| Item | Value |
|---|---|
| Development window | 2016-01-04 .. 2023-12-29 |
| Data | adjusted 1-minute QQQ / TQQQ / BIL under `data/intraday-hf/` |
| Fills | next-bar open, `research/bt.py`, 2% band |
| Costs | 1 bp headline; 5 bp and 10 bp reported |
| Constraints | long-only, weights >= 0, row sum <= 1, idle cash at 0% |
| Holdout | never loaded; every panel ends 2023-12-29 |
| Bar | TQQQ dev 36.72% CAGR / 82.29% max DD / 0.82 Sharpe |

The 1-minute archive starts on 2016-01-04, so there is no pre-2016 warm-up.
The first five sessions cannot trigger and the first fifteen cannot re-enter;
the default position is TQQQ, which is also what a buy-and-hold investor holds.

---

## 1. Hypothesis

TQQQ's 82% development drawdown is not a smooth decay. It is a handful of
fast, clustered crashes (2018Q4, 2020Q1, 2022) separated by long bull runs.
A brake that reacts to a **fast loss** should step aside before the acute
phase, and a **slow recovery confirmation** should keep it out of bear-market
rallies while still catching the first durable leg of a V recovery.

The design has two deliberately asymmetric speeds:

1. **Exit fast.** A 14% loss over five sessions is about a 1.5-sigma
   five-day move under an iid normal approximation (68.6% annualised vol),
   and the raw condition is true on 4.7% of the 2,012 development sessions.
   It is deep enough to ignore ordinary pullbacks, but it is not
   ultra-rare; the selectivity comes from the slow re-entry, not from the
   trigger alone. The five-session window also catches a grinding bear leg
   that a single-day stop misses.
2. **Re-enter slow.** After a trigger, wait for TQQQ to close at or above its
   prior 15-session high. A 5- or 10-session high is too fast: it re-enters
   the first bear-market rally and gets stopped again. A 20-session high is
   slower and gives up some CAGR (43.7% / 41.7% in the exploratory surface),
   though it still passes. The viable re-entry band is roughly 12-20
   sessions; the pre-registered grid spans 12-18 around the 15 centre.

The important, uncomfortable point is that the **exit alone is not an edge**.
After a 2-5 day TQQQ loss, forward returns are positive on average: the brake
usually sells into a bounce. The strategy works only because the slow re-entry
turns the exit into a crash-triggered trend filter. The report quantifies this
with the spell attribution and the placebo test.

---

## 2. Exact rules

One decision per session, at the 15:59 close. Let `C_t` be TQQQ's regular
session close. All indicators use data through `C_t`; the target set at the
close fills at the next session's 09:30 open.

**State:** `LONG` (100% TQQQ, the default) or `OFF` (100% BIL).

**LONG -> OFF.** If

```
C_t / C_{t-5} - 1 <= -0.14
```

then go to `OFF` at the close and hold BIL from the next open. A second
trigger while already off changes nothing.

**OFF -> LONG.** If

```
C_t >= max(C_{t-15}, C_{t-14}, ..., C_{t-1})
```

then go back to `LONG` at the close and hold TQQQ from the next open. The
prior-high window excludes today. There is no same-day exit-and-reentry: the
trigger is checked first.

No moving-average gate, no volatility gate, no shorting, no leverage beyond
100% TQQQ. BIL is the only defensive asset.

**Why these numbers.** 14% / 5 sessions / 15-session high is the centre of the
pre-registered grid below. The centre is not the single best cell; it is the
middle of the broad region that survives the neighbourhood, cost, placebo and
cut tests.

---

## 3. Pre-registered grid (8 cells)

The grid is a local neighbourhood, not a full factorial: it varies trigger
duration, trigger depth and re-entry speed one at a time around the centre.
All eight cells are reported in `result.json` and `report.md`.

| # | Cell | Trigger | Re-entry | Role |
|---:|---|---:|---:|---|
| 1 | `k3_d12_R15` | 3-session loss <= -12% | 15-session high | fast 3-day brake, closest to the mandate example |
| 2 | `k4_d14_R15` | 4-session loss <= -14% | 15-session high | faster duration neighbour |
| 3 | `k5_d12_R15` | 5-session loss <= -12% | 15-session high | shallower neighbour |
| 4 | **`k5_d14_R15`** | **5-session loss <= -14%** | **15-session high** | **pre-registered centre** |
| 5 | `k5_d16_R15` | 5-session loss <= -16% | 15-session high | deeper neighbour |
| 6 | `k5_d14_R12` | 5-session loss <= -14% | 12-session high | faster re-entry |
| 7 | `k5_d14_R18` | 5-session loss <= -14% | 18-session high | slower re-entry |
| 8 | `k5_d14_R10` | 5-session loss <= -14% | 10-session high | fast re-entry, expected whipsaw |

Cell 8 is included because the mandate explicitly suggests a 5/10-session
re-entry. It is the stress test, not a straw man: it clears the loose official
bar (CAGR 38.14%, DD 70.30% < 82.29%) but fails the strict DD < 60% target.
If the 10-session version had also cleared 60% DD, the re-entry-speed story
would be weaker.

**Selection honesty.** The eight cells were fixed after a coarse daily
mechanism scan on the development window, a small 1-minute candidate screen,
and before the final production 1-minute run. The scan is documented in the
report's "what was tried" section. No holdout data entered any decision.

---

## 4. What would falsify the idea

1. **Dev bar.** CAGR <= 36.72% or max DD >= 82.29%.
2. **No plateau.** The centre passes but the duration/depth/re-entry
   neighbours collapse; or only the single best cell passes.
3. **No 60% DD.** The strategy beats the CAGR bar but the DD stays above 60%.
4. **Fragility to one year.** Excluding 2020 or 2022 drops CAGR below the bar.
   (A crash brake is allowed to depend on crashes, but the report must say so.)
5. **Placebo.** Random defensive spells with the same lengths and exposure
   match the observed result; the timing adds nothing.
6. **Look-ahead.** Truncating the panel at a past date changes the weights on
   the overlap.
7. **Costs.** 10 bp costs turn a pass into a fail.
8. **Whipsaw dominance.** Most defensive spells lose money and the few that
   win are one-off artefacts; the spell table and the 2018/2020/2023 episodes
   must show a repeatable crash-avoidance pattern, not a single lucky exit.

---

## 5. Known risks and expected behaviour

- **Bull-market whipsaw is the main cost.** In 2018 the brake sold the
  February low, rebought 25.6% higher, and then took the March correction.
  In 2020 it had a four-session October whipsaw that missed +25.0%. These are
  real costs, not rounding errors.
- **2020 V-recovery is the best case.** The brake exited on 2020-02-24 and
  re-entered on 2020-04-03, avoiding a -51.9% TQQQ move (open to open) and
  then riding the recovery. A holdout without a V-crash will not repeat that.
- **2022 is the second engine.** Three defensive spells avoided roughly
  -31%, -36% and -34% TQQQ moves. A slow bull holdout will not repeat that
  either.
- **Bull-year lag.** The strategy lagged TQQQ in 2019 (+80% vs +133%), 2021
  (+43% vs +83%) and 2023 (+143% vs +198%). A 2024-2026 bull with no crash
  is the main full-window risk. The development CAGR cushion is the defence;
  the report shows the implied full-window CAGR under several hypothetical
  holdout participation rates, without inspecting the holdout.
- **The trigger is a fixed percentage, not volatility-scaled.** A future
  regime with structurally different TQQQ volatility could shift the
  trigger's frequency. The roughly 10-16% depth plateau is the buffer.

---

## 6. Provenance

### The stop-loss / trend-filter mechanism

- Kaminski & Lo (2014), *When do stop-loss rules stop losses?*, Journal of
  Financial Markets 18, 234-254:
  <https://www.sciencedirect.com/science/article/pii/S138641811300030X>.
  Stop-loss rules add value only when returns are not a random walk; in a
  random walk they do not. This is the theoretical reason the exit alone is
  not enough and the re-entry rule matters.
- Faber (2007), *A Quantitative Approach to Tactical Asset Allocation*:
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461>. The slow
  re-entry is a fast version of the same "wait for the trend to repair" idea.
- The repo's own `research/revisit/drawdown-stop-overlay/report.md` found that
  a pure peak stop on TQQQ is overlay-only (8/10/15% peak stops had lower CAGR
  than TQQQ; 12% was a single non-robust point). This mandate is a deliberate
  re-test with a **fast loss** trigger and a **slow high** re-entry, not a
  peak stop.

### TQQQ volatility and the 2020 V

- TQQQ daily log-return volatility over the dev window is 68.6% annualised
  (measured on the development daily closes). A 14% five-session loss is a
  bad week, not a one-day crash; the raw condition is true on 4.7% of
  sessions. The trigger's value is that it marks a fast, clustered loss; the
  slow re-entry does the selection.
- The 2020 episode is the COVID V: TQQQ peaked 2020-02-19, bottomed
  2020-03-23 at about -70%, and recovered through 2020-07-09. The brake's
  2020-02-24 exit / 2020-04-03 re-entry is the V-recovery case the mandate
  asks to be honest about.

### Own choices

- The 5-session / 14% / 15-session-high centre, the 8-cell grid and the
  BIL-only defence are own choices, tested only on the development window.
  No external source specifies these values.
- `research/new/PROGRAM.md` and the task mandate define the dev window, the
  bar, the costs and the holdout protocol.
