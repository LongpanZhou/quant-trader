# Fill/turnover aggregation fix

**Scope:** reporting only. No strategy weights, signals, parameters, META,
website or exporter code was changed.  `research/bt.py` and
`research/new/run_holdout.py` were edited; a regression script and this note
were added; `research/new/drawdown-recovery-v2/holdout.json` was regenerated
from the same frozen weights.

---

## 1. What was wrong

`run_holdout.py::minute_stats` masked the array fields (`equity`, `cash`) to
the requested window, but `bt.simulate` returns `fills` and `turnover` as
scalars.  The mask comprehension left those scalars untouched, and
`bt.stats` copied them straight into every window.  Every window in
`holdout.json` therefore printed the **full-run** 35 fills / 702.04x, even
though CAGR/DD/Sharpe/exposure were correctly sliced.

The strategy was not at fault: `bt.run` on the dev panel always returned 27
fills, and the full weights' dev slice returned 27 fills / 202.24x.

## 2. Fix

### `research/bt.py`

- `bt.run(..., fill_log=False)` and `bt.simulate(..., fill_log=False)` gained
  an optional flag.
- With `fill_log=True`, the result also contains `fills_log`: one dict per
  trade:

  ```python
  {"ts": Timestamp, "notional": float, "symbol": int, "side": "buy"|"sell"}
  ```

  `symbol` is the panel column index (0=QQQ, 1=TQQQ, 2=BIL), and `notional`
  is the post-slippage traded notional.
- The compiled simcore result remains the authoritative source for equity,
  cash, aggregate fills and turnover.  A Python reference pass produces only
  the log when simcore is available; without simcore the Python result is
  used directly.  This keeps CAGR/DD/Sharpe/equity exactly unchanged.
- `bt.simulate_python(..., fill_log=False)` is backward-compatible.  The
  aggregate `fills` and `turnover` are unchanged; the log is additive.

### `research/new/run_holdout.py`

- `bt.run(..., fill_log=True)` is used in `main`.
- `minute_stats` now requires the log and slices it with
  `[lo, hi + 1 day)`, matching the existing inclusive end-date window:
  - `fills` = number of log entries in the window;
  - `traded_notional` = sum of their notionals;
  - `turnover` = `traded_notional / window_start_equity`.
- The window start equity is the **first marked equity in the window**
  (`rr["equity"][0]`), not the full-run start equity.  Each window now also
  records `traded_notional`, `turnover_start_equity` and
  `turnover_denominator: "window_start_equity"`.
- A missing log raises a clear error instead of silently returning full-run
  scalars.

### Denominator convention

`turnover = sum(notional of fills in window) / equity at the first bar of the
window`.

- Dev and full start at **$100,000**, so their values are the same as the old
  global `bt.simulate` turnover: **202.24x** and **702.04x**.
- The holdout starts at the **$3,685,636.63** equity marked at 2024-01-02
  09:30, so its turnover is **13.56x**, not the old global 499.80x.
- The 10y and 5y windows start at $118,129.55 and $1,499,600.79, so their
  values are **591.96x** and **41.11x**.
- Cross-window turnover comparisons should use the explicit
  `turnover_start_equity` or the `traded_notional` numerator.  If the lead
  prefers a single global denominator for comparability, the one-line change
  is to divide by the original `START_EQUITY` instead; the counts and
  notionals are unaffected.

## 3. Before/after — `drawdown-recovery-v2/holdout.json`

All rows are the `windows.*.1bp` block.  The old file reported the full-run
35 / 702.04x in every window.

| Window | Old fills | Old turnover | New fills | New turnover | New traded notional | New start equity |
|---|---:|---:|---:|---:|---:|---:|
| dev | 35 | 702.04x | **27** | **202.24x** | $20,224,116.11 | $100,000.00 |
| holdout | 35 | 702.04x | **8** | **13.56x** | $49,979,727.99 | $3,685,636.63 |
| full | 35 | 702.04x | **35** | **702.04x** | $70,203,844.10 | $100,000.00 |
| 10y | 35 | 702.04x | **32** | **591.96x** | $69,927,596.13 | $118,129.55 |
| 5y | 35 | 702.04x | **16** | **41.11x** | $61,647,761.98 | $1,499,600.79 |

Unchanged exactly (old = new to the stored precision):

- dev CAGR 57.626%, DD 43.392%, Sharpe 1.2547, exposure 78.785%, ending
  equity $3,783,755.38;
- holdout CAGR 31.641%, DD 39.198%, Sharpe 0.8076, exposure 86.207%, ending
  equity $7,973,171.47;
- full CAGR 49.987%, DD 43.392%, Sharpe 1.1223, exposure 80.712%, ending
  equity $7,973,171.47;
- 10y/5y metrics identical to the old rows;
- daily curve values identical (max abs diff 0.0; the curve JSON is
  byte-identical);
- benchmark blocks identical.

Partition check: `full.fills = dev.fills + holdout.fills = 27 + 8 = 35`;
`full.traded_notional = $20,224,116.11 + $49,979,727.99 = $70,203,844.10`
(compact-float difference 0.0).

## 4. Second-strategy test

`research/new/test_fill_aggregation.py` runs two frozen strategies through
the new path and checks:

- `bt.run(fill_log=True)` and `bt.run(fill_log=False)` have the same fills,
  turnover, equity and cash;
- `len(fills_log) == full fills`;
- `sum(log notional) / $100k == old full-run turnover` (relative float
  tolerance);
- `full == dev + holdout` for fills and notional;
- each window's turnover equals its notional / its start equity;
- the full row still matches the existing `holdout.json` full row.

Run:

```powershell
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research/new/test_fill_aggregation.py
```

Output:

```
loading full 1-minute panel ...
panel 1,056,144 bars 2016-01-04 09:30:00-05:00 .. 2026-10-23 15:59:00-04:00
drawdown-recovery-v2: weights (1056144, 3) (0.3s), simulating ...
  dev 27 / 202.24x  hold 8 / 13.56x  full 35 / 702.04x  old full 35/702.04  (7.8s)
family-session-timing: weights (1056144, 3) (0.1s), simulating ...
  dev 4048 / 41691.68x  hold 1417 / 1894.66x  full 5465 / 106998.79x  old full 5465/106998.79  (6.3s)

slug                     dev fills/turn   hold fills/turn   full fills/turn   old full
drawdown-recovery-v2        27/   202.24x     8/   13.56x     35/   702.04x  35/702.04
family-session-timing     4048/ 41691.68x  1417/ 1894.66x   5465/106998.79x  5465/106998.79

OK: fill totals and per-window notional partition cleanly.
```

For `family-session-timing`, the full-window totals still match the old
full-run values exactly: **5,465 fills / 106,998.78882237663x**, and
`full = dev + holdout` for both fills and notional
(4,048 + 1,417 = 5,465).  The old `family-session-timing/holdout.json` was
read for the comparison but was not overwritten.

### Compiled/Python parity

The first version of the log computed book equity with
`np.dot(shares, px)`.  The Rust simcore accumulates the same dot product
sequentially, so a borderline 2% band rebalance can differ in the last bit.
On `vol-scaled-crash-stop` this produced **3,949 log fills against 3,950
compiled fills**; on `family-rebalance-flow` it produced **2,054 against
2,052**.  `simulate_python` now uses the same sequential accumulation as
`simcore`; the logs report **3,950** and **2,052** fills respectively, matching
the compiled totals.  `vol-scaled` turnover is **51,802.23649312577x** against
compiled **51,802.23649312578x**.  This changes only the reference log, not
the compiled metrics.

## 5. Files changed

| File | Change |
|---|---|
| `research/bt.py` | optional `fill_log` path in `run`, `simulate`, `simulate_python` |
| `research/new/run_holdout.py` | per-window log slicing, window-start-equity turnover, `fill_log=True`, prints fills/turnover |
| `research/new/test_fill_aggregation.py` | new read-only regression test |
| `research/new/drawdown-recovery-v2/holdout.json` | regenerated from the same frozen weights |
| `research/new/curves/drawdown-recovery-v2.json` | re-emitted by the runner; byte-identical to the old file |
| `research/new/FILL_AGGREGATION_FIX.md` | this note |

No `strategy.py`, weights, parameters, META, website or exporter files were
modified.

## 6. Remaining limitations

1. **Stale per-strategy JSONs.**  All existing `holdout.json` files were
   regenerated with the fixed runner after the summation-order fix.  Any
   strategy added later must be run through
   `python research/new/run_holdout.py <slug>`; the old runner silently
   copied full-run scalars into every window.
2. **Python log pass cost.**  `fill_log=True` runs the compiled simulation
   for the metrics and a Python reference pass for the log.  It adds roughly
   6-8 seconds per full 1M-bar strategy in the test; the metrics are not
   recomputed from Python when simcore is available.  If this becomes a
   bottleneck, the log can be added to the Rust simcore.
3. **Float rounding.**  The log's notional sum can differ from the compiled
   `traded` total by a few micro-dollars on a multi-billion-dollar notional
   (7.6e-6 on $10.7B for `family-session-timing`; 1e-14 on
   `vol-scaled-crash-stop` after the summation-order fix).  Fill counts now
   match exactly.  The regression test uses a relative tolerance for the
   notional equality.
4. **Log persistence.**  `holdout.json` stores window aggregates, not the
   per-fill log itself.  The log is in memory during the run.  If a durable
   fill artifact is needed, it can be written separately.
5. **Symbol field.**  The log's `symbol` is the panel column index
   (0=QQQ, 1=TQQQ, 2=BIL), because `bt.py` does not know ticker names.  The
   runner's panel convention is fixed.
6. **No re-tuning.**  The second-strategy test used the frozen
   `family-session-timing` weights and only compared accounting.  No holdout
   selection or parameter change was made.
