# Audit — `dual-speed-regime`: reproduction, causality, and the 22.9 pp gap

**Audit date:** 2026-11-27
**Code audited:** `research/revisit/dual-speed-regime/strategy.py` (mtime 2026-11-27 00:38:08)
**Result audited:** `research/revisit/dual-speed-regime/result.json` (mtime 2026-11-27 00:45:26)
**Curve audited:** `research/revisit/curves_full/dual-speed-regime.json` (mtime 2026-11-27 00:21:57)
**Data / harness:** local QQQ/TQQQ/BIL 1-minute parquet, `research/bt.py`; 2016-01-04 → 2026-10-23; 1 bp; 2% band; 1-minute equity marks; `band=0.02`.

No strategy code, parameters, or website files were changed. This audit only reads and re-runs the current code.

`SPEC.md` and `PROVENANCE.md` do not exist in the strategy directory. The spec and provenance are in `report.md` and `HYPOTHESIS.md`; both were last written on 2026-11-26 17:39–17:42, **before** the 2026-11-27 00:19–00:45 tuning runs, and were never updated.

---

## Bottom line

| Item | Result |
|---|---|
| Reproduced dev 1 bp (current code) | **28.7622% CAGR / 45.4538% max DD / 1.0702 Sharpe / 2,735 fills / $752,633.81** |
| `result.json` dev 1 bp | exactly the same; all deltas are **0.0** |
| Causal full 2016-01-04 → 2026-10-23 (current code) | **25.1668% CAGR / 45.4538% max DD / 0.9808 Sharpe / 3,672 fills / $1,129,862.84** |
| Dev slice of the full-panel run | **28.7622% / 45.4538% / 1.0702** — exactly the dev result |
| Cut tests | **0 differing weights** at both cuts; max abs diff **0.0** |
| Published `curves_full` vs pre-tune code | **bit-for-bit match** (0.0 max abs diff over 2,718 days; 5.1543% / 39.3651% / 0.3491 / 7,997 fills) |
| Cause of the 22.9 pp gap | **2026-11-27 00:38 edit `OVERNIGHT=True` + `IDLE="cash"`**: overnight +20.65 pp, cash idle +1.66 pp, both +22.88 pp |
| Verdict | **`code bug` — spec/code mismatch; not look-ahead, not a stale-data problem, not an arithmetic bug.** |

The 28.76% is real and causal for the code as it stands. But the code as it stands is an **overnight-holding** variant that contradicts its own pre-registration (`report.md`, `HYPOTHESIS.md`: "flat every night", "zero overnight", "no entries after 14:29", "not the old base in disguise"). The published 5.15% curve is the **pre-registered intraday-only strategy**, reproduced exactly by the current code's `overnight=False, idle="bil"` path. The gap is a strategy-version mismatch, not a curve/data problem.

---

## 1. Reproduction

Command path:

```python
ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), "2016-01-04", "2023-12-29",
                    "1min", warmup_days=500)
w, info = strategy.build_weights(ts, o, c)          # current defaults: overnight=True, idle="cash"
r = bt.run(ts, o, c, w, "2016-01-04", band=0.02, slippage_bps=1.0)
```

| Variant on the same dev panel | Dev CAGR | Dev max DD | Dev Sharpe | Dev fills | Dev ending equity |
|---|---:|---:|---:|---:|---:|
| **Current code** (`overnight=True, idle="cash"`) | **28.7622%** | **45.4538%** | **1.0702** | **2,735** | **$752,633.81** |
| `result.json` | 28.7622% | 45.4538% | 1.0702 | 2,735 | $752,633.81 |
| Pre-registered intraday (`overnight=False, idle="bil"`) | 5.8866% | 39.3651% | 0.3790 | 5,943 | $157,884.43 |
| Intraday, cash (`overnight=False, idle="cash"`) | 7.5511% | 35.2008% | 0.4542 | 2,971 | $178,822.17 |
| Overnight, BIL (`overnight=True, idle="bil"`) | 26.5324% | 45.3441% | 1.0050 | 5,471 | $654,650.94 |
| `_before_tune/strategy.py` (old half-day exit) | 5.3803% | 38.0200% | 0.3556 | 5,943 | $151,956.24 |

The current code reproduces `result.json` to the last bit: `cagr`, `max_drawdown`, `sharpe`, `fills`, and `ending_equity` deltas are all exactly 0.0.

The `_before_tune/result.json` 5.3803% / 38.0200% / 0.3556 is the **older half-day-bug** version (`hard_exit ... or (m == nb - 1)`, which holds the last half-day bar overnight). The current `overnight=False` path uses `m >= nb - 2` and exits inside the half-day session. That half-day fix is worth **+0.51 pp** of dev CAGR (5.3803% → 5.8866%) and **−1.35 pp** of DD; it is *not* the 22.9 pp gap. The published curve matches the **fixed** pre-tune code (5.8866%), not the `_before_tune` snapshot.

The dev `info` for the current code:

```
entries=589, exits=589, stops=496, days=2012, days_traded=1418,
bars=14038, exposure=0.34718, avg_size_when_long=0.84576
```

The strategy is traded on 1,418 of 2,012 dev sessions (70.5%) and holds TQQQ overnight on **847 of 1,996 full dev sessions (42.4%)**, at an average weight of **0.865** when held. This directly contradicts the report's "flat ~80% of calendar time and ~100% of nights."

---

## 2. Causality audit (line by line)

### 2.1 Which bars does the 60-minute EMA use?

`bars_60m` (`strategy.py:63`) walks each session from `first` to `last`, appends `e = f + 59, f + 119, ...` and finally the actual last bar `l`, and records `price[e]`. So the 09:30–10:29 bar uses the **10:29 close**, the 10:30–11:29 bar uses the **11:29 close**, and the last bar uses the **15:59 close** on a full day (13:00 on a half-day).

`ema` (`strategy.py:79`) is a recursive EMA seeded at the first 60-minute bar and updated with the current bar's close. **The current bar is included** (`e = a*v + (1-a)*e` at bar `b`). That is correct *because the signal is evaluated at that bar's close*: the 10:29 bar's close is known at 10:29, and the resulting weight is not filled until 10:30.

There is no full-sample EMA, no look-ahead seeding, and no future bar in `spread[b]`.

### 2.2 Signal → fill timing: next-open, not same-bar

`build_weights` sets `hold[e:nxt] = size`, where `e` is the bar's last minute index and `nxt` is the next bar's end (or `l + 1` at the session end). `bt.simulate` executes `weights[i]` at `opens[i+1]` (`bt.py:488–490`; Rust path identical). Therefore:

- 10:29 signal → **10:30 open** fill;
- 11:29 signal → 11:30 open fill;
- 15:59 signal → **next session's 09:30 open** fill;
- no signal is filled on its own bar.

The weight at minute `e` is the target for the *next* minute's open. The equity at minute `e` is marked at `close[e]` before the trade. This is correct next-open execution.

The 15:29 bar's weight is held through the 15:59 close and over the 15:59→09:30 gap; the 15:59 bar's weight fills at the next 09:30 open and only adjusts the position after the gap. That is causal (the 15:29 and 15:59 closes are both known before their fills), but it is a very different holding period from the pre-registered intraday design.

### 2.3 Weight alignment between the 1-minute panel and the 60-minute signal

The 60-minute bars are built from the **same** `ts/opens/closes` panel, and `ends`/`day_of` are minute indices into that panel. `bt.panel` uses QQQ as the base calendar; TQQQ/BIL are reindexed and forward-filled. `build_weights` explicitly asserts the QQQ and TQQQ 60-minute grids match (`strategy.py:116–117`).

`hold` is a length-`n` minute array; `w[:, 1] = hold`; `bt.run` slices the same indices. There is **no index alignment bug** between the 1-minute panel and the 60-minute signal.

One implementation quirk, not a causality bug: `hold[f : f+59]` is never assigned, so the first 59 minutes of each session are always zero. The 10:29 minute (`e = f+59`) is assigned and fills at 10:30. Thus the strategy is flat 09:30–10:28, holds the 09:30 minute only (the overnight position is sold at 09:31), and re-enters at 10:30. This is the intended "flat first hour" rule, implemented as a one-minute carry rather than a 10:29 carry; the difference is negligible and not the source of the gap.

### 2.4 Normalization, thresholds, parameters

- `EMA_FAST=10`, `EMA_SLOW=30`, `STRONG=0.003`, `ATR_K=2.5`, `WARMUP_BARS=60`, `LAST_ENTRY_OFFSET=299`, `EXIT_OFFSET=359` are fixed constants. No full-sample mean/std/min/max, no z-score, no cross-sectional normalization.
- `atr14` is a rolling 14-bar mean of absolute 60-minute close changes, current bar included; it uses only past/current bars.
- The trailing-stop `high` is the highest TQQQ 60-minute **close** since entry, updated with the current close before the stop test; it never uses a future high.
- `baseline_165_for_correlation` uses a 165-day SMA and prior close; it is measurement-only and is **never called by `build_weights`**.
- `bt.panel(warmup_days=500)` is effectively a no-op: the 1-minute archive starts 2016-01-04, so there is no pre-2016 1-minute warmup. The EMA is seeded at the first 2016 bar and the first 60 60-minute bars are warmup. That is a short warmup, not a look-ahead.

### 2.5 Any use of 2024–2026 in the dev run?

No.

- The dev panel ends at 2023-12-29 15:59; the dev result is 2016-01-04 → 2023-12-29 only.
- The full-panel weight prefix over **781,880 bars** is **bit-identical** to the dev weights: `max_abs_diff = 0.0`, `n_diff_bars = 0`.
- The 2016-2023 slice of the full-panel causal run is **exactly** 28.7622% / 45.4538% / 1.0702 (all deltas 0.0 vs `result.json`).
- The 2024-2026 data is used only for the **full-window** result, which is a separate output. The tuning scripts (`diag.py`, `sweep*.py`, `explore*.py`) use the 2016-2023 dev panel, and `diag.py`/`sweep.py` assert `ts[-1] < 2023-12-30` before running.

### 2.6 Cut tests

The full panel was truncated at the exact timestamps, `build_weights` was rebuilt from the truncated panel, and the result was compared with the corresponding prefix of the full-panel weight matrix.

| Cut | Truncated bars | Last bar in truncated panel | Differing bars before last bar | Max abs diff before last bar | Differing bars (all) | Max abs diff (all) |
|---|---:|---|---:|---:|---:|---:|
| 2020-03-12 11:07 | 409,459 | 2020-03-12 11:06 | **0** | **0.0** | **0** | **0.0** |
| 2022-09-13 10:41 | 654,958 | 2022-09-13 10:40 | **0** | **0.0** | **0** | **0.0** |

Both cuts are completely clean. Even the final partial bar happens to match in both cases (the signal/size did not change at those minutes), so the all-bar diff is also 0. There is no detectable future dependence in the weights.

**Causality conclusion:** the weight construction is causal. The 60-minute signal includes the current bar's close but fills at the next open; the ATR/stop uses only current/past closes; there is no full-sample normalization; there is no 2024-2026 leakage; and two independent cut tests reproduce the full-run weights exactly. **No look-ahead was found.**

---

## 3. The 22.9 pp gap: exact cause

### 3.1 File-level proof

The two curve files are internally consistent with two **different code versions**, not with two different data vintages:

| Comparison | Max abs difference over all daily points |
|---|---:|
| `curves_full/dual-speed-regime.json` vs current code `overnight=False, idle="bil"` full run | **0.0** (2,718 days) |
| `curves/dual-speed-regime.json` (dev) vs current code `overnight=True, idle="cash"` dev run | **0.0** (2,012 days) |
| `curves_full/dual-speed-regime.json` vs current code (defaults) full run | 1,149.82 (normalized units) |

The full curve is **bit-for-bit** the pre-tune strategy: 5.1543% full CAGR / 39.3651% DD / 0.3491 Sharpe / 7,997 fills, identical to the file's stored metrics. The dev curve is **bit-for-bit** the current strategy: 28.7622% / 45.4538% / 1.0702 / 2,735 fills.

### 3.2 Timestamps and the actual code diff

| Time (2026-11-27) | Event |
|---|---|
| 00:19:07 / 00:19:19 | `diag.py` / `diag.log`: pre-tune diagnostics, 5.89% at 1 bp |
| 00:20–00:24 | `sweep_a/b/c/d.log`, `placebo2.log`: overnight variants tested on the **dev** period |
| 00:21:57 | `curves_full/dual-speed-regime.json` captured from the **pre-tune** code |
| 00:31:20 | `_before_tune/strategy.py` snapshot |
| **00:38:08** | **`strategy.py` edited: `OVERNIGHT = True`, `IDLE = "cash"`** |
| 00:45:26 | `result.json` and `curves/dual-speed-regime.json` written from the **current** code |

The diff between `_before_tune/strategy.py` and the current `strategy.py` is exactly the overnight redesign:

```diff
-EXIT_OFFSET = 359            # 15:29 bar close -> flat at 15:30
+EXIT_OFFSET = 359            # 15:29 bar close -> flat at 15:30 (intraday mode only)
+# Tuning 2026-11-27 (see DIAGNOSIS.md): hold across sessions while the 60-minute
+# trend is up, and leave idle equity in cash instead of swapping BIL in and out.
+OVERNIGHT = True
+IDLE = "cash"
```

and in `build_weights`:

```diff
-            hard_exit = (e >= f + exit_offset) or (m == nb - 1)
-            can_enter = (b >= warmup_bars) and (e <= f + last_entry_offset)
+            if overnight:
+                hard_exit = False
+                can_enter = (b >= warmup_bars) and np.isfinite(s)
+            else:
+                hard_exit = (e >= f + exit_offset) or (m >= nb - 2)
+                can_enter = ((b >= warmup_bars) and (e <= f + last_entry_offset)
+                             and not hard_exit)
...
-            w[:, 2] = 1.0 - hold
+            if idle == "bil":
+                w[:, 2] = 1.0 - hold
+            elif idle != "cash":
+                raise ValueError(...)
```

There is a comment referring to `DIAGNOSIS.md`, but that file does not exist in the strategy directory. There is no corresponding update to `report.md` or `HYPOTHESIS.md`; both still describe the intraday-only design.

### 3.3 Exact decomposition of the gap

On the identical dev panel, changing only the two flags:

| Step | Dev CAGR | Increment |
|---|---:|---:|
| Pre-registered intraday, BIL | 5.8866% | — |
| → cash idle (`idle="cash"`) | 7.5511% | **+1.6645 pp** |
| → overnight hold, BIL (`overnight=True`) | 26.5324% | **+20.6458 pp** |
| → overnight + cash (current) | 28.7622% | **+2.2298 pp** over overnight-BIL |
| Total gap vs pre-registered | | **+22.8756 pp** |

So: **90.2% of the 22.9 pp gap is the overnight flag**, 7.3% is the cash-vs-BIL idle choice, and 2.5% is the interaction. On the full window the same decomposition is 5.1543% → 25.1668% (**+20.01 pp**), with overnight accounting for 92.2%.

This is not a minute-vs-daily marks effect: the daily-close CAGRs are within 0.01 pp of the 1-minute-mark CAGRs for both variants (current 28.76% vs 28.76%; pre-tune 5.89% vs 5.89%). The marks change the drawdown (45.45% vs 44.79% for the current), not the 22.9 pp CAGR gap.

### 3.4 Cost sensitivity (full window, 1-minute marks)

| Variant | 0 bp | 1 bp | 5 bp | 10 bp |
|---|---:|---:|---:|---:|
| Current (`overnight=True, idle="cash"`) | 28.576% | 25.167% | 12.412% | −1.718% |
| Pre-registered (`overnight=False, idle="bil"`) | 11.509% | 5.154% | −16.842% | −37.981% |

The pre-registered intraday strategy fails its own 5 bp falsifier on the dev period (`CAGR > 5%`, `Sharpe > 0.40`): at 5 bp it is −16.28% CAGR / −0.75 Sharpe on dev and −16.84% / −0.80 on the full window. The current overnight variant is more cost-robust because it holds longer and trades less (3,672 vs 7,997 fills), but that is a different strategy.

---

## 4. Causal full-window result

Built by calling the **current** `build_weights` on the full 2016-01-04 → 2026-10-23 panel and then running the full period. Because the construction is causal, this is the same weight matrix a live run would have produced at each date.

| Window | Current code (`overnight=True, cash`) | Pre-registered (`overnight=False, BIL`) |
|---|---:|---:|
| Dev 2016-01-04 → 2023-12-29 | **28.7622% / 45.4538% / 1.0702** | 5.8866% / 39.3651% / 0.3790 |
| Holdout 2024-01-02 → 2026-10-23 | 15.5739% / 20.3488% / 0.7067 | 3.1157% / 25.0660% / 0.2570 |
| **Full 2016-01-04 → 2026-10-23** | **25.1668% / 45.4538% / 0.9808** | **5.1543% / 39.3651% / 0.3491** |

Full-window current: 3,672 fills, turnover 14,929.6×, exposure 0.3453, ending equity $1,129,862.84.
Full-window pre-registered: 7,997 fills, turnover 8,042.2×, exposure 1.0000 (all equity in TQQQ or BIL), ending equity $172,093.53.

Daily-close version of the current full curve: 25.2078% CAGR / 44.7851% DD / 0.9574 Sharpe. The daily-close drawdown is smaller than the 1-minute-mark 45.4538% because the worst intraday mark is not the daily close.

Yearly returns (current vs pre-registered vs TQQQ):

| Year | Current | Pre-registered | TQQQ |
|---|---:|---:|---:|
| 2016 | +15.8% | +8.0% | +19.9% |
| 2017 | +28.3% | +8.3% | +114.5% |
| 2018 | +34.1% | −6.8% | −20.8% |
| 2019 | +12.6% | −1.8% | +148.2% |
| 2020 | +153.1% | +8.3% | +104.1% |
| 2021 | +25.3% | −3.1% | +81.1% |
| 2022 | −34.0% | −14.6% | −79.4% |
| 2023 | +70.0% | +64.2% | +192.0% |
| 2024 | +34.0% | +0.4% | +62.4% |
| 2025 | +10.0% | −3.7% | +32.1% |
| 2026 YTD | +1.8% | +12.7% | +22.6% |

The current variant's 2020 (+153%) and 2023 (+70%) are the dominant years; 2022 is −34%. The pre-registered intraday strategy is small-positive in 2016/2017/2020, negative in 2018/2019/2021/2022, and dominated by 2023 (+64.2%).

---

## 5. What the current variant actually is

The current code is **not** the intraday 60-minute trend strategy described in `report.md` / `HYPOTHESIS.md`. It is an overnight-holding TQQQ strategy:

- It holds TQQQ overnight on **847 of 1,996 full dev sessions (42.4%)**, average weight **0.865** when held. Over the full window: **1,137 of 2,675 full sessions (42.5%)**, average weight 0.864.
- The 15:59→09:30 overnight gap contributes **$305,128 of $1,179,159 gross P&L (25.9%)** over 2016-2026. The overnight-gap log component is **0.622 of 2.425 total log return (25.7%; 30.2% of the additive component logs)**. Compounded in isolation, the overnight gap is ~5.93%/yr and the remaining intraday path is ~14.22%/yr (these two components do not add linearly because of compounding/cross terms).
- The strategy's daily return correlation with TQQQ is **0.4795** (0.6379 on active days); with QQQ it is 0.4770. The `result.json` correlation with the 165-day baseline is 0.3996 (0.4985 active), which passes the <0.60 falsifier but does not make the return stream independent of TQQQ beta.
- The 09:30–10:30 window is almost entirely skipped (only the 09:30 minute is held), but the overnight gap is exactly the part of TQQQ's return that the pre-registered design wanted to avoid (round-2 report: overnight +1,355% vs intraday +81% over 2017-2026). The tune re-introduced the old base's dominant return source.

The `sweep_a.log` makes the selection explicit:

| Variant | Dev 1 bp CAGR / DD / Sharpe |
|---|---:|
| V0 current (intraday, BIL, tiers) | 5.89% / 39.4% / 0.38 |
| V1 cash idle | 7.55% / 35.2% / 0.45 |
| V5 overnight hold (BIL, tiers) | 26.31% / 45.3% / 1.00 |
| V6 overnight, cash, no tiers | 32.25% / 50.1% / 1.09 |
| Current (overnight, cash, tiers) | 28.76% / 45.5% / 1.07 |

The overnight variants were selected on the dev period after the pre-registered design had been tested and failed at 5 bp. `result.json` still says `variants_tried: 0` and `status: passed`; the sweep logs show **51 grid points** (`sweep_a` 10, `sweep_b` 26, `sweep_c` 1, `sweep_d` 14) plus the placebos. The pre-registered intraday strategy would be **rejected** on its own falsifiers (5 bp CAGR −16.28%, Sharpe −0.75; 10 bp CAGR −37.59%); the "passed" status is only true for the post-hoc overnight variant.

---

## 6. 2026-05-26 bad prints and half-days

### 2026-05-26

| Symbol | Bars | Bad highs >5% over body | Bad lows >5% under body | Max high over body | Max close-to-close move |
|---|---:|---:|---:|---:|---:|
| QQQ | 390 | 0 | 0 | +1.22% | ±0.13% |
| TQQQ | 390 | **6** | 0 | **+11.03%** | ±0.47% |
| BIL | 390 | 0 | 0 | +0.01% | ±0.01% |

The TQQQ bad prints are six 1-minute bars (four 5-minute bars) between 09:35 and 09:55 with highs 8.1–11.0% above the bar body (e.g. the 09:35 5-minute bar: open 79.82, high 88.62, low 79.56, close 79.90). They are **highs only**; the TQQQ closes and QQQ prints are clean.

`build_weights` uses **closes only**:
- QQQ `bar_close_q` for the 60-minute EMA signal;
- TQQQ `bar_close_t` for the ATR(14) and the trailing-stop high (the docstring calls it a "close-to-close ATR proxy");
- no `high`/`low` column is ever read.

Therefore the corrupted highs cannot enter the signal, the ATR, or the stop. On 2026-05-26 the strategy was long 331 minutes at weight 1.0, TQQQ returned +1.80%, and the strategy returned −0.04% — no anomalous P&L. The 2022-06-21 TQQQ suspect **low** cluster is likewise unused.

### Half-days

- 21 half-days in the full panel; every one has **211 bars** (09:30–13:00 inclusive), last bar **13:00**, and **no after-hours prints**. `bt.load_1m` truncates at 13:00, so the data is clean.
- `bars_60m` makes the last half-day bar 12:30–13:00 and uses the 13:00 close. The current `overnight=True` variant holds through the half-day close and can enter at the 13:00 close (fill next open); the pre-tune `overnight=False` variant exits at 12:29 (second-to-last bar) and is flat overnight.
- That is a **design** difference, not a data corruption. It does, however, violate the pre-registered "no entries after 14:29" and "flat every night" rules in the current variant.

---

## 7. Verdict

**`code bug` — spec/code mismatch. Not look-ahead; not a stale-data or arithmetic problem.**

The numerical question is settled:

1. The 28.76% dev result is **real and causal**. It reproduces exactly, the full-panel dev slice is identical, and both cut tests are clean.
2. The published 5.15% full curve is **also real** and is **bit-for-bit the pre-registered intraday-only strategy** (`overnight=False, idle="bil"`).
3. The 22.9 pp gap is the **2026-11-27 00:38 edit `OVERNIGHT=True` + `IDLE="cash"`**: overnight +20.65 pp, cash +1.66 pp, both +22.88 pp. The curve predates the edit; the dev curve and `result.json` postdate it.
4. The current code holds TQQQ overnight on ~42.5% of sessions at ~0.86 weight, contradicts `report.md` and `HYPOTHESIS.md` ("flat every night", "zero overnight", "no entries after 14:29", "not the old base in disguise"), and its `result.json` still advertises the old intraday hypothesis. `variants_tried: 0` is also inconsistent with the sweep logs.

**Recommendation.** Pick one and make the artifacts consistent:

- **If the pre-registered intraday strategy is the intended one:** set `OVERNIGHT=False`, `IDLE="bil"` (and keep the half-day fix), keep the 5.15% full curve, and mark the strategy **rejected** on its own 5 bp/10 bp falsifiers. Do not publish 28.76% for it.
- **If the overnight variant is the intended one:** treat it as a **new pre-registration**, rewrite `report.md`/`HYPOTHESIS.md` (holding period, overnight exposure, 42.5% of nights, cash leg), disclose the **51** grid points tried, and regenerate the full curve from the causal matrix at **25.1668% CAGR / 45.4538% DD / 0.9808 Sharpe** (2016-2026). Do not describe it as an "intraday-only" or "independent" strategy; its daily correlation with TQQQ is 0.48 (0.64 active) and the overnight gap is ~26% of gross P&L.

The causal full curve for the current code is saved at:

`research/revisit/audit/dual_speed_causal_curve.json`

(2,718 daily closes, 2016-01-04 → 2026-10-23, normalized to 100.0 at 2016-01-04, last value 1,129.86.)

---

## Appendix — audit artifacts

| File | Contents |
|---|---|
| `research/revisit/audit/dual_speed_audit.py` | Reproduction, variants, cut tests, full causal run, bad-print/half-day checks |
| `research/revisit/audit/dual_speed_audit.json` | Machine-readable results |
| `research/revisit/audit/dual_speed_audit.log` | Run log |
| `research/revisit/audit/dual_speed_decomp.py` | P&L attribution, correlations, holdout windows |
| `research/revisit/audit/dual_speed_decomp.json` | Machine-readable attribution |
| `research/revisit/audit/dual_speed_log_attrib.py` | Overnight-gap vs intraday log attribution |
| `research/revisit/audit/dual_speed_log_attrib.json` | Machine-readable log attribution |
| `research/revisit/audit/dual_speed_costs.json` | 0/1/5/10 bp full-window cost table |
| `research/revisit/audit/dual_speed_causal_curve.json` | Causal 2016-2026 daily curve for the current code |
| `research/revisit/audit/dual_speed.md` | This report |

Key exact numbers:

- Dev current: `cagr=0.28762159940790033`, `max_drawdown=0.454537821492901`, `sharpe=1.0702496503924006`, `fills=2735`, `ending_equity=752633.8066529032`.
- Full current: `cagr=0.2516684957362607`, `max_drawdown=0.454537821492901`, `sharpe=0.980799993887224`, `fills=3672`, `ending_equity=1129862.8383283443`, `years=10.801446878089589`.
- Full pre-registered: `cagr=0.05154321783294935`, `max_drawdown=0.3936505375226431`, `sharpe=0.3491122366485257`, `fills=7997`, `ending_equity=172093.5323821629`.
- Curve comparison: `curves_full` vs pre-tune max abs diff `0.0`; `curves` dev vs current max abs diff `0.0`.
- Cut tests: 409,459 and 654,958 truncated bars; 0 differing bars; max abs diff 0.0.
- Weight prefix: 781,880 bars; 0 differing bars; max abs diff 0.0.
