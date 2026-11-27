"""Uniform 2016-2026 All-strategies data: existing + verified new strategies."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
HERE = ROOT / "research" / "revisit"
CURVES = HERE / "curves_full"
NEW = ROOT / "research" / "new"
NEW_CURVES = NEW / "curves"
META = json.loads((NEW / "META.json").read_text(encoding="utf-8"))
VISIBLE = [s for s in META["strategies"] if s.get("visible", True)]
LIBRARY = json.loads((NEW / "LIBRARY.json").read_text(encoding="utf-8"))
FAMILY = {s["slug"]: s.get("family", "other") for s in LIBRARY["strategies"]}
FAMILY_WINNERS = {
    "ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
    "drawdown-recovery-v2", "fomc-opex-window", "family-session-timing",
    "family-short-reversal", "family-rebalance-flow",
    "family-intraday-microstructure-day", "family-ml-microstructure",
}
OUT = ROOT / "web" / "public" / "data" / "compare" / "all.json"
START, END = "2016-01-04", "2026-10-23"

NAMES = {
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
    "ratio-froth": "Ratio froth",
}
PALETTE = [
    "#9ae6a5", "#93c5fd", "#fbbf24", "#f472b6", "#c4b5fd", "#67e8f9",
    "#f87171", "#fb923c", "#facc15", "#a3e635", "#34d399", "#22d3ee",
    "#818cf8", "#c084fc", "#f59e0b", "#84cc16", "#14b8a6", "#38bdf8",
    "#a78bfa", "#e879f9", "#fca5a5", "#fdba74", "#fde047", "#bef264",
    "#6ee7b7", "#d8b4fe", "#fda4af", "#7dd3fc", "#f9a8d4", "#fcd34d",
    "#86efac", "#c7d2fe", "#fca5a5", "#f0abfc", "#a5b4fc", "#fde68a",
    "#99f6e4", "#fecaca", "#ddd6fe", "#bbf7d0",
]
for _s in VISIBLE:
    NAMES[_s["slug"]] = _s["name"]


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


def main():
    curves = {}
    for path in sorted(CURVES.glob("*.json")):
        payload = json.loads(path.read_text())
        curves[payload["slug"]] = pd.Series(
            payload["values"], index=pd.to_datetime(payload["dates"])
        )
    for s in VISIBLE:
        path = NEW_CURVES / f"{s['slug']}.json"
        if not path.exists():
            raise SystemExit(f"missing verified new curve: {path}")
        payload = json.loads(path.read_text())
        curves[payload["slug"]] = pd.Series(
            payload["values"], index=pd.to_datetime(payload["dates"])
        )
    print("strategies", len(curves))

    sys.path.insert(0, str(ROOT / "research"))
    import bt
    ts, _, cl = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=0)
    for key, col, name in (("tqqq", 1, "TQQQ buy & hold"), ("qqq", 0, "QQQ buy & hold")):
        s = pd.Series(cl[:, col], index=pd.DatetimeIndex(ts))
        s = s.groupby(s.index.date).last()
        s.index = pd.to_datetime(s.index)
        curves[key] = s / s.iloc[0] * 100.0
        NAMES[key] = name

    all_dates = sorted(set().union(*(set(s.index) for s in curves.values())))
    all_dates = [d for d in all_dates if pd.Timestamp(START) <= d <= pd.Timestamp(END)]
    idx = pd.Index(all_dates)
    for key, curve in curves.items():
        if curve.index.min() > pd.Timestamp(START) + pd.Timedelta(days=7):
            print(f"WARN {key} starts {curve.index.min().date()} (flat before first mark)")
        if curve.index.max() < pd.Timestamp(END) - pd.Timedelta(days=7):
            print(f"WARN {key} ends {curve.index.max().date()} (forward-filled to {END})")
    # bfill gives a strategy that only starts trading later (e.g. ml-classifier,
    # TRADE_START 2017-01-03) a flat cash segment for the uniform 2016 window;
    # ffill carries the last mark to the uniform end.
    frame = pd.DataFrame({k: v.reindex(idx).ffill().bfill() for k, v in curves.items()})
    for col in frame.columns:
        first = frame[col].dropna().iloc[0]
        frame[col] = frame[col] / first * 100.0

    series = []
    metrics = []
    strategy_i = 0
    for key in frame.columns:
        is_bench = key in ("tqqq", "qqq")
        color = "#71717a" if key == "tqqq" else "#a1a1aa" if key == "qqq" else PALETTE[strategy_i]
        if not is_bench:
            strategy_i += 1
        series.append({
            "id": key,
            "name": NAMES.get(key, key.replace("-", " ").title()),
            "color": color,
            "values": [None if pd.isna(v) else float(v) for v in frame[key]],
        })
        m = stats(frame[key])
        metrics.append({
            "id": key,
            "name": NAMES.get(key, key.replace("-", " ").title()),
            "cagr": m["cagr"],
            "dd": m["dd"],
            "sharpe": m["sharpe"],
            "benchmark": is_bench,
            "family": "benchmark" if is_bench else FAMILY.get(key, "other"),
            "family_winner": (not is_bench) and key in FAMILY_WINNERS,
        })
    metrics.sort(key=lambda m: (m["benchmark"], -m["cagr"]))
    OUT.write_text(json.dumps({
        "generated": "2026-11-27",
        "start": START,
        "end": END,
        "window": "2016-2026",
        "dates": [str(d.date()) for d in frame.index],
        "series": series,
        "metrics": metrics,
        "note": "All strategies use the same 2016-2026 window, 1 bp costs and "
                "daily-close metrics; each series is that strategy's frozen "
                "published version.",
    }, indent=1), encoding="utf-8")
    print(f"wrote {OUT}: {len(frame)} days, {len(series)} curves, {len(metrics)} metrics")


if __name__ == "__main__":
    main()
