# Strategy research: minute trading vs TQQQ

Goal: find a strategy that **consistently beats TQQQ buy-and-hold** on minute
data with **higher CAGR and lower maximum drawdown**, on both the 10-year and
5-year windows. The benchmark is TQQQ buy-and-hold on the same bars.

## Data and environment

Adjusted 1-minute QQQ/TQQQ/BIL data is in `data/intraday-hf/` (gitignored).
Use only these three symbols unless a specific agent is told otherwise.

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
```

Shared harness: `research/bt.py`. Import it with:

```python
import sys
sys.path.insert(0, "research")
import bt
```

```python
# Daily bars: includes 500 calendar days of warmup before `start`.
ts, opens, closes = bt.panel(("QQQ","TQQQ","BIL"), "2017-01-03", "2026-10-23", "1D")

# Minute bars: same, but rule="1min" (or "5min", "15min", "1h").
# `closes[:, 0]` is QQQ, `[:, 1]` TQQQ, `[:, 2]` BIL.

# weights[i] is the target set at the close of bar i; fills at open i+1.
weights = ...  # shape (n, 3), non-negative, rows sum to <= 1
result = bt.run(ts, opens, closes, weights, "2017-01-03", band=0.02, slippage_bps=1.0)
s = bt.stats(result, bars_per_year=252)          # daily
b = bt.benchmark(closes[bt.start_index(ts,"2017-01-03"):, 1],
                 ts[bt.start_index(ts,"2017-01-03"):], 252)
bt.print_summary("candidate", s, b)
```

For minute bars, `bars_per_year = 252 * 390` for 1m, `252 * 78` for 5m,
`252 * 26` for 15m, `252 * 7` for 1h. The simulator always fills at the next
bar's open and charges slippage on traded notional.

## Benchmark and target

TQQQ buy-and-hold, daily bars, same windows (the harness computes it exactly):

| Window | TQQQ CAGR | TQQQ max DD | TQQQ Sharpe |
|---|---:|---:|---:|
| 10y (2017-01-03 → 2026-10-23) | **39.28%** | **81.68%** | 0.83 |
| 5y (2021-10-25 → 2026-10-23) | **13.47%** | **81.68%** | 0.53 |

A passing strategy must have, on **both** windows:

- CAGR > TQQQ CAGR
- max drawdown < TQQQ max drawdown
- preferably Sharpe > TQQQ Sharpe
- 1 bp primary costs; report 5 bp sensitivity

The daily baseline that already passes is **QQQ above its 165-day SMA → 100%
TQQQ; below → BIL**, with a 2% band and next-open fills:

- 10y: **45.31% CAGR, 58.71% max DD, 1.00 Sharpe**
- 5y: **34.61% CAGR, 36.86% max DD, 0.88 Sharpe**

That baseline is daily, not minute. Your job is to build a minute strategy
(1m/5m decisions, or a daily regime with genuine 1m execution/timing) that
matches or beats it. The daily regime + minute entry/exit overlay is encouraged.

## Rules

- No look-ahead: a weight set at bar `i` can only use data through bar `i`.
- Next-bar-open fills only. Include slippage; no free fills.
- Long-only unless a strategy explicitly models shorting (do not assume it).
- Use regular-session bars only (the harness already filters 09:30–16:00 ET).
- Avoid overfitting: report full-period results plus yearly returns and a
  walk-forward or parameter-stability check. Do not pick the best parameter
  from a grid without showing neighboring values.
- Do not modify `research/bt.py`, `scripts/`, `web/`, or any core repo file.
  Write only under `research/agents/<your-slug>/`.

## Deliverables

Each agent writes:

- `research/agents/<slug>/report.md` — idea, source links, exact rules,
  parameters, 10y/5y metrics, yearly returns, 1bp/5bp, pass/fail.
- `research/agents/<slug>/result.json` — machine-readable metrics.
- `research/agents/<slug>/strategy.py` — runnable code if applicable.

Report honestly if the strategy does not pass. A negative result is useful.
