"""Build one uniform All-strategies dataset: 27 strategies + 2 benchmarks.

No passed/rejected/original groups. Every strategy uses the same common
2017-2023 window and the same daily-curve metrics.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
HERE = ROOT / "research" / "revisit"
CURVES = HERE / "curves"
COMPARE = ROOT / "web" / "public" / "data" / "compare"
OUT = COMPARE / "all.json"
START, END = "2017-01-03", "2023-12-29"

REBUILD_NAMES = {
    "daily-regime-minute-entry": "Crash-continuation short",
    "donchian-breakout": "Donchian alignment ladder",
    "drawdown-regime": "Deep drawdown recovery",
    "drawdown-stop-overlay": "Failed-breakdown spring",
    "dual-speed-regime": "Intraday 60-minute trend",
    "dynamic-leverage-throttle": "Volatility-shock recovery",
    "ensemble-signals": "Volatility contraction recovery",
    "event-risk-overlay": "OpEx cycle",
    "gap-capitulation-reversal": "Quiet capitulation",
    "gap-fill-fade": "Failed gap-up fade",
    "intraday-mean-reversion": "Post-capitulation reversal",
    "intraday-momentum": "Time-of-day leverage ladder",
    "intraday-seasonality": "Close-flow exhaustion",
    "letf-rebalance-flow": "Relative Nasdaq flow dip",
    "ml-classifier": "Unsupervised regime allocator",
    "ml-crash-overlay-winner": "Leverage-decay timing",
    "opening-range-breakout": "Opening-range failed-breakdown reclaim",
    "overnight-crash-filter": "Night continuation / day reversal",
    "ratio-pairs": "Ratio-cycle standalone",
    "risk-parity-hrp": "Volatility-state risk parity",
    "stop-reentry-recovery": "LETF overshoot recovery",
    "time-of-day": "Closing-pressure overnight carry",
    "vol-kelly-overlay": "Vol-spike reflation",
    "vol-scaled-crash-stop": "Vol-scaled crash system",
    "volume-orderflow": "Participation exhaustion",
    "winner-ensemble-blend": "Two-stream risk parity",
}
PALETTE = [
    "#9ae6a5", "#93c5fd", "#fbbf24", "#f472b6", "#c4b5fd", "#67e8f9",
    "#f87171", "#fb923c", "#facc15", "#a3e635", "#34d399", "#22d3ee",
    "#818cf8", "#c084fc", "#f59e0b", "#84cc16", "#14b8a6", "#38bdf8",
    "#a78bfa", "#e879f9", "#fca5a5", "#fdba74", "#fde047", "#bef264",
    "#6ee7b7", "#d8b4fe", "#fda4af",
]


def stats(values: pd.Series) -> dict:
    v = values.dropna()
    eq = v.to_numpy()
    years = (v.index[-1] - v.index[0]).days / 365.25
    peak = np.maximum.accumulate(eq)
    rets = np.diff(eq) / eq[:-1]
    return {
        "cagr": float((eq[-1] / eq[0]) ** (1 / years) - 1) if years > 0 else 0.0,
        "dd": float(-(eq / peak - 1).min()),
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() else 0.0,
    }


def main() -> None:
    curves: dict[str, pd.Series] = {}
    names: dict[str, str] = {}
    benchmark: dict[str, bool] = {}

    # 26 rebuilds
    for path in sorted(CURVES.glob("*.json")):
        payload = json.loads(path.read_text())
        slug = payload["slug"]
        curves[slug] = pd.Series(payload["values"], index=pd.to_datetime(payload["dates"]))
        names[slug] = REBUILD_NAMES.get(slug, slug.replace("-", " ").title())
        benchmark[slug] = False

    # original leader as just another strategy
    old = json.loads((COMPARE / "research.json").read_text())
    ratio = next((s for s in old["series"] if s["id"] == "a21"), None)
    if ratio:
        curves["ratio-froth"] = pd.Series(
            ratio["values"], index=pd.to_datetime(old["dates"])
        )
        names["ratio-froth"] = "Ratio froth"
        benchmark["ratio-froth"] = False

    # benchmarks
    base = json.loads(OUT.read_text()) if OUT.exists() else None
    # benchmarks are rebuilt from the same 1m panel below
    import sys
    sys.path.insert(0, str(ROOT / "research"))
    import bt
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=0)
    for key, col, label in (("tqqq", 1, "TQQQ buy & hold"), ("qqq", 0, "QQQ buy & hold")):
        s = pd.Series(cl[:, col], index=pd.DatetimeIndex(ts))
        s = s.groupby(s.index.date).last()
        s.index = pd.to_datetime(s.index)
        curves[key] = s / s.iloc[0] * 100.0
        names[key] = label
        benchmark[key] = True

    all_dates = sorted(set().union(*(set(s.index) for s in curves.values())))
    all_dates = [d for d in all_dates if pd.Timestamp(START) <= d <= pd.Timestamp(END)]
    idx = pd.Index(all_dates)
    frame = pd.DataFrame({k: v.reindex(idx).ffill() for k, v in curves.items()})
    for col in frame.columns:
        first = frame[col].dropna().iloc[0]
        frame[col] = frame[col] / first * 100.0

    series = []
    metrics = []
    color_i = 0
    for key in frame.columns:
        is_bench = benchmark[key]
        color = "#71717a" if key == "tqqq" else "#a1a1aa" if key == "qqq" else PALETTE[color_i]
        if not is_bench:
            color_i += 1
        series.append({
            "id": key,
            "name": names[key],
            "color": color,
            "values": [None if pd.isna(v) else float(v) for v in frame[key]],
        })
        m = stats(frame[key])
        metrics.append({
            "id": key,
            "name": names[key],
            "cagr": m["cagr"],
            "dd": m["dd"],
            "sharpe": m["sharpe"],
            "benchmark": is_bench,
        })

    metrics.sort(key=lambda m: (m["benchmark"], -m["cagr"]))
    OUT.write_text(json.dumps({
        "generated": "2026-11-27",
        "start": START,
        "end": END,
        "window": "2017-2023",
        "dates": [str(d.date()) for d in frame.index],
        "series": series,
        "metrics": metrics,
        "note": "All strategies use the same 2017-2023 daily window and the same rules.",
    }, indent=1), encoding="utf-8")
    print(f"wrote {OUT}: {len(frame)} days, {len(series)} curves, {len(metrics)} metrics")


if __name__ == "__main__":
    main()
