# Round 2: beat the current winner

Round 1 produced 10 strategies. All 10 beat TQQQ buy-and-hold at 1 bp, but the
best genuine minute-executed strategy is:

**Daily QQQ 165-day SMA regime + armed 4% minute stop**

| Window | 1 bp CAGR / DD | 5 bp CAGR / DD | 10 bp CAGR / DD |
|---|---:|---:|---:|
| 10y (2017-01-03..2026-10-23) | **58.80% / 44.56%** | 54.60% / 47.08% | 49.50% / 50.06% |
| 5y (2021-10-25..2026-10-23) | **49.88% / 33.49%** | 45.89% / 34.13% | 41.05% / 34.93% |

Rules: hold 100% TQQQ while QQQ's prior close is above its 165-day SMA,
otherwise BIL. On risk-on days, arm a 4% stop from the session open only when
QQQ's first-minute close is below its prior 20-day SMA times 1.01. If armed and
TQQQ closes 4% below the open, sell at the next minute's open and stay in BIL
for the rest of the day and night. Re-enter next session if the regime is on.

The winner is already robust: 27/27 rolling 3-year windows have lower drawdown
than TQQQ, and 23/27 have higher return. It passes at 10 bp. The bar is now
**the winner**, not just TQQQ.

## Targets

A round-2 strategy should achieve at least one of:

1. **Strict dominance:** higher CAGR *and* lower max DD than the winner on both
   the 10y and 5y windows.
2. **Better drawdown / comparable return:** lower max DD than the winner on
   both windows, with CAGR within 2 pp of the winner and better rolling 3-year
   consistency.
3. **Better consistency:** similar headline CAGR/DD but materially more rolling
   3-year windows where it beats both TQQQ and the winner.

It must still beat TQQQ on CAGR and drawdown in both windows, and should pass at
5 bp. Report 10 bp if it survives. Do not sacrifice the 5-year result to win the
10-year one.

## Data and harness

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
```

```python
import sys
sys.path.insert(0, "research")
import bt

ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1min")
# closes[:,0] QQQ, [:,1] TQQQ, [:,2] BIL
weights = ...  # shape (n,3), long-only, rows sum <= 1
r = bt.run(ts, opens, closes, weights, "2017-01-03", band=0.02, slippage_bps=1.0)
s = bt.stats(r, 252 * 390)
```

Use only the local adjusted QQQ/TQQQ/BIL data under `data/intraday-hf/`.
No new downloads. The harness fills at the next bar's open and charges
slippage on traded notional.

## Round-2 mandates

Agents are assigned one of these families:

1. Blend the winner with the ensemble / other round-1 strategies; test fixed,
   volatility-weighted and drawdown-throttled blends.
2. Replace the fixed 4% stop with an ATR- or volatility-scaled stop and partial
   de-risking to QQQ.
3. Dual-speed regime: 165-day trend plus a faster 20/50-day or 60-minute trend
   filter; exit earlier, re-enter on reclaim.
4. Event-risk overlay: FOMC/CPI/NFP/OpEx/pre-holiday de-risking using only
   ex-ante event dates.
5. Gap-down / capitulation reversal: buy TQQQ after a large QQQ gap down or
   intraday drawdown in a bull regime, hold 1-5 days.
6. Stop re-entry: after the 4% stop, re-enter the same day if TQQQ reclaims
   VWAP/EMA or QQQ reclaims its moving average.
7. Overnight-only / first-hour variants with a crash filter and low turnover.
8. Walk-forward ML crash overlay on the winner, using minute-derived features
   but daily decisions.
9. Dynamic leverage throttle: TQQQ/QQQ/BIL sized by volatility, drawdown and
   trend strength, combined with the winner's stop.
10. A genuinely different idea found online and testable on this data.

## Performance notes

- `bt.panel()` now caches aligned panels under `data/cache/research_panels/`.
  A 1-minute panel load drops from about 8.6 s to about 0.24 s. The cache key
  includes the source parquet mtimes, so edited data invalidates it.
- `research/fastbt.py` provides `fast_sim`/`run`, an exact event-based version
  of `bt.simulate` for piecewise-constant target weights. It matches
  `bt.simulate` with 0.0 equity difference and is much faster for regime/stop
  strategies.
- Run one parameter grid per process. Do not add nested parallelism; the
  machine has 12 logical cores and many agents run concurrently.
- A CUDA 12.3 toolkit and an RTX 3080 are available. CuPy is installed in the
  research Python path. Use `research/gpu_screen.py` for broad daily screens,
  but always re-test the top candidates on the exact 1-minute harness. Daily
  screens overstate intraday execution.



- No look-ahead: a weight set at bar `i` may use only data through bar `i`.
- Next-bar-open fills only; include 1 bp/5 bp costs.
- Long-only unless a strategy explicitly models shorting (do not assume it).
- Regular-session bars only.
- Avoid overfitting: report neighbouring parameters, yearly returns, and
  rolling 3-year windows. Do not promote a single best grid point.
- Do not modify `research/bt.py`, `scripts/`, `web/`, or any core repo file.
  Write only under `research/agents2/<your-slug>/`.

## Deliverables

Each agent writes:

- `research/agents2/<slug>/report.md` — idea, source links, exact rules,
  parameters, 10y/5y metrics, yearly returns, 1/5/10 bp, rolling 3-year
  consistency, pass/fail vs TQQQ and vs the winner.
- `research/agents2/<slug>/result.json` — machine-readable metrics.
- `research/agents2/<slug>/strategy.py` — runnable code.

Report negative results honestly. A strategy that fails to beat the winner but
documents a clean negative is useful.
