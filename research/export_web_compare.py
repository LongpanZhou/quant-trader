r"""Export the all-strategy comparison data for the web dashboard.

Writes `web/public/data/compare/research.json` with:
  - normalized daily equity curves for the runnable headline strategies;
  - 5y/10y headline metrics (1 bp, 1-minute equity marks) for every agent,
    read from its result.json via compare_agents.headline_metrics, with
    daily/5-minute agents re-marked on minutes from research/minute_marked.json.

Run research/minute_marks.py first if any coarse-bar agent changed.

Run from the repo root:
    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/export_web_compare.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents2" / "volume-orderflow"))
import bt  # noqa: E402
import fastbt  # noqa: E402
import engine  # noqa: E402
import strategy as agent23  # noqa: E402
from compare_agents import headline_metrics  # noqa: E402

START, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390
OUT = ROOT / "web" / "public" / "data" / "compare" / "research.json"
MINUTE_MARKS = ROOT / "research" / "minute_marked.json"

# Agents deliberately left off the leaderboard. Anything else without readable
# headline metrics stops the export instead of silently disappearing.
EXCLUDED = {
    "gap-capitulation-reversal": "negative result; no overlay beat the winner, so no variant was promoted",
}

NAMES = {
    "daily-regime-minute-entry": "Armed 4% minute stop",
    "ratio-pairs": "Ratio froth",
    "overnight-crash-filter": "First-hour + crash filter",
    "volume-orderflow": "Volume-armed stop",
    "ensemble-signals": "Ensemble crash vote",
    "intraday-momentum": "First-hour momentum",
    "intraday-mean-reversion": "3% prior-close stop",
    "donchian-breakout": "5m Donchian",
    "vol-kelly-overlay": "Volatility ladder",
    "drawdown-stop-overlay": "Drawdown threshold stop",
    "opening-range-breakout": "Opening-range breakout",
    "time-of-day": "Overnight + first 30m",
    "ml-classifier": "ML risk-off overlay",
    "intraday-seasonality": "Late-day de-risk",
    "stop-reentry-recovery": "Gradual stop re-entry",
    "vol-scaled-crash-stop": "ATR-scaled stop",
    "dual-speed-regime": "Dual-speed regime",
    "event-risk-overlay": "OpEx de-risk",
    "dynamic-leverage-throttle": "Dynamic leverage",
    "gap-fill-fade": "Gap-up fade",
    "winner-ensemble-blend": "Winner/ensemble 75/25",
    "drawdown-regime": "Drawdown regime",
    "ml-crash-overlay-winner": "ML crash overlay",
    "letf-rebalance-flow": "Late-rally overlay",
    "risk-parity-hrp": "Risk-parity vol target",
}


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


a1 = load("a1", ROOT / "research" / "agents" / "daily-regime-minute-entry" / "strategy.py")
a4 = load("a4", ROOT / "research" / "agents" / "intraday-momentum" / "strategy.py")
a8 = load("a8", ROOT / "research" / "agents" / "ensemble-signals" / "strategy.py")
a17 = load("a17", ROOT / "research" / "agents2" / "overnight-crash-filter" / "strategy.py")
a21 = load("a21", ROOT / "research" / "agents2" / "ratio-pairs" / "strategy.py")


def daily(ts, eq):
    s = pd.Series(eq, index=ts)
    d = s.groupby(s.index.date).last()
    return pd.Series(d.to_numpy(float), index=pd.to_datetime(d.index))


def metrics_from_equity(ts, eq):
    r = bt.stats({"ts": ts, "equity": eq, "cash": np.zeros_like(eq),
                  "fills": 0, "turnover": 0.0}, BARS)
    return {"cagr": r["cagr"], "max_drawdown": r["max_drawdown"],
            "sharpe": r["sharpe"]}


def main():
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    i0 = bt.start_index(ts, START)
    D = engine.Data()

    w1, _ = a1.build_weights(ts, op, cl)
    w4, _ = a4.build_weights(ts, op, cl)
    w8 = a8.build_weights(ts, op, cl)
    w17 = a17.build_weights(ts, op, cl)
    w21, _ = a21.build_weights(ts, op, cl)
    w23, _ = agent23.build_weights(D)
    # agent23 uses its own panel; align it to the shared 1-minute timestamp grid
    # before blending.  The half-day truncation changed the two panel lengths.
    w23_full = np.zeros_like(w1)
    pos = ts.get_indexer(pd.DatetimeIndex(D.ts))
    ok = pos >= 0
    w23_full[pos[ok]] = w23[ok]
    w23 = w23_full

    blends = {
        "ratio+first": 0.5 * w21 + 0.5 * w17,
        "first+volume": 0.5 * w17 + 0.5 * w23,
        "ratio+volume": 0.5 * w21 + 0.5 * w23,
    }

    curves = {
        "tqqq": (ts[i0:], cl[i0:, 1]),
        "a1": (ts, None),
        "a4": (ts, None),
        "a8": (ts, None),
        "a17": (ts, None),
        "a21": (ts, None),
        "a23": (ts, None),
        "ratio+first": (ts, None),
        "first+volume": (ts, None),
        "ratio+volume": (ts, None),
    }
    weights = {"a1": w1, "a4": w4, "a8": w8, "a17": w17, "a21": w21,
               "a23": w23, **blends}

    series: dict[str, pd.Series] = {}
    for key, (kts, raw) in curves.items():
        if raw is not None:
            s = daily(kts, raw)
        else:
            w = weights[key]
            r = fastbt.run(ts, op, cl, w, START, band=0.02, slippage_bps=1.0)
            s = daily(r["ts"], r["equity"])
        series[key] = s

    frame = pd.DataFrame(series).sort_index()
    frame = frame.loc[frame.index >= pd.Timestamp(START)]
    frame = frame.ffill().dropna(how="all")
    # Normalize every curve to 100 on its first common session.
    first = frame.apply(lambda col: col.dropna().iloc[0])
    frame = frame.div(first, axis=1) * 100.0

    meta = {
        "tqqq": ("TQQQ buy & hold", "#71717a"),
        "a1": ("Armed 4% minute stop", "#93c5fd"),
        "a4": ("First-hour momentum", "#c4b5fd"),
        "a8": ("Ensemble crash vote", "#f0abfc"),
        "a17": ("First-hour + crash filter", "#fbbf24"),
        "a21": ("Ratio froth", "#9ae6a5"),
        "a23": ("Volume-armed stop", "#67e8f9"),
        "ratio+first": ("Ratio + first-hour", "#34d399"),
        "first+volume": ("First-hour + volume", "#f472b6"),
        "ratio+volume": ("Ratio + volume", "#a3e635"),
    }
    out_series = []
    for key, (name, color) in meta.items():
        vals = frame[key].dropna()
        out_series.append({
            "id": key,
            "name": name,
            "color": color,
            "values": [round(float(v), 3) if np.isfinite(v) else None for v in frame[key]],
        })

    # Leaderboard: every agent's result.json headline, 1 bp, minute-marked.
    # Coarse-bar agents (daily / 5-minute decisions) are re-marked on minutes
    # by research/minute_marks.py; run that first after changing them.
    remarked = json.loads(MINUTE_MARKS.read_text(encoding="utf-8"))["agents"]
    metrics = []
    problems = []
    for base in (ROOT / "research" / "agents", ROOT / "research" / "agents2"):
        for agent_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            slug = agent_dir.name
            if slug in EXCLUDED:
                print(f"excluded {slug}: {EXCLUDED[slug]}")
                continue
            path = agent_dir / "result.json"
            if not path.exists():
                problems.append(f"{slug}: no result.json")
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                ten = headline_metrics(slug, data, "10y")
                five = headline_metrics(slug, data, "5y")
            except Exception as error:
                problems.append(f"{slug}: {error}")
                continue
            if not ten or not five:
                problems.append(f"{slug}: no 10y/5y headline metrics in result.json")
                continue
            marks = "1m"
            if slug in remarked:
                ten, five = remarked[slug]["minute"]["10y"], remarked[slug]["minute"]["5y"]
                marks = f"1m (re-marked from {remarked[slug]['rule']})"
            metrics.append({
                "id": slug,
                "name": NAMES.get(slug, slug.replace("-", " ").title()),
                "group": "round 2" if base.name == "agents2" else "round 1",
                "cagr10": float(ten["cagr"]),
                "dd10": float(ten["max_drawdown"]),
                "cagr5": float(five["cagr"]),
                "dd5": float(five["max_drawdown"]),
                "marks": marks,
            })
    if problems:
        raise SystemExit("leaderboard export stopped; fix or add to EXCLUDED:\n  "
                         + "\n  ".join(problems))

    # Benchmarks on the same 1-minute marks.
    bench = {}
    for label, start in (("10y", START), ("5y", START5)):
        j = bt.start_index(ts, start)
        bench[label] = bt.benchmark(cl[j:, 1], ts[j:], BARS)
    daily_sma = remarked["benchmark-daily"]["minute"]
    for slug, name, ten, five in (
        ("benchmark-tqqq", "TQQQ buy & hold", bench["10y"], bench["5y"]),
        ("benchmark-daily", "Daily 165d SMA", daily_sma["10y"], daily_sma["5y"]),
    ):
        metrics.append({"id": slug, "name": name, "group": "benchmark",
                        "cagr10": float(ten["cagr"]), "dd10": float(ten["max_drawdown"]),
                        "cagr5": float(five["cagr"]), "dd5": float(five["max_drawdown"]),
                        "marks": "1m"})

    metrics.sort(key=lambda m: m["cagr10"], reverse=True)
    payload = {
        "generated": str(pd.Timestamp.now().date()),
        "start": str(frame.index[0].date()),
        "end": str(frame.index[-1].date()),
        "dates": [str(d.date()) for d in frame.index],
        "series": out_series,
        "metrics": metrics,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
    print(f"curves: {len(out_series)}, metrics: {len(metrics)}, sessions: {len(frame)}")


if __name__ == "__main__":
    main()
