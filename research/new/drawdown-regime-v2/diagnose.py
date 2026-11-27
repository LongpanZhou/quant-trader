"""Dev-only diagnostics for the drawdown-regime repair.

Exploratory sweep, NOT the pre-registered grid.  Loads 1-minute data only
through 2023-12-29 and QQQ daily rows only through 2023-12-29.

    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/drawdown-regime-v2/diagnose.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390

spec = importlib.util.spec_from_file_location(
    "ddr_old", ROOT / "research" / "revisit" / "drawdown-regime" / "strategy.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
# Never touch daily rows after the development end.
S._qqq_daily = lambda end=DEV_END: _qqq_daily_dev(end)


def _qqq_daily_dev(end: str = DEV_END):
    path = ROOT / "data" / "intraday-hf" / "QQQ-1d-yahoo.parquet"
    d = pd.read_parquet(path, columns=["date", "adjclose"],
                        filters=[("date", "<=", pd.Timestamp(end).date())])
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d = d.sort_values("date")
    assert d["date"].max() <= pd.Timestamp(end).date()
    return d["date"].to_numpy(), d["adjclose"].to_numpy(float)


def _stats(r):
    s = bt.stats(r, BPY)
    return {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "fills",
                                     "turnover")}


def run_variants(ts, o, c, variants):
    rows = []
    ws, infos = [], []
    for name, params in variants:
        w, info = S.build_weights(ts, o, c, params=params)
        ws.append(w)
        infos.append(info)
    for bp in (1.0,):
        rs = bt.run_many(ts, o, c, ws, DEV_START, 0.02, bp)
        i0 = bt.start_index(ts, DEV_START)
        for j, ((name, params), info, r) in enumerate(zip(variants, infos, rs)):
            s = _stats(r)
            wd = ws[j][i0:]
            rows.append(dict(
                name=name, params=params,
                n=info["n_episodes"],
                exposure=float(np.mean(wd[:, 1] > 0)),
                days=int((wd[:, 1] > 0).sum()),
                cagr=s["cagr"], dd=s["max_drawdown"], sharpe=s["sharpe"],
                fills=s["fills"],
                entry_years=[int(e["entry_date"][:4]) for e in info["episodes"]],
                episodes=[{k: e.get(k) for k in ("entry_date", "exit_date", "days", "ret",
                                                  "exit_reason", "trough")}
                          for e in info["episodes"]],
            ))
    return rows


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min",
                        warmup_days=500)
    assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")

    variants = [("base", {})]
    for v in (0.10, 0.12, 0.15, 0.18):
        variants.append((f"deep_dd={v}", {"deep_dd": v}))
    for v in (10, 15, 30):
        variants.append((f"entry_break={v}", {"entry_break": v}))
    for v in (40, 90, 120):
        variants.append((f"hold={v}", {"hold": v}))
    for v in (10, 30):
        variants.append((f"exit_low={v}", {"exit_low": v}))
    for v in (0.02, 0.03, 0.08):
        variants.append((f"rearm={v}", {"rearm": v}))
    variants += [
        ("rearm=0.00", {"rearm": 0.0}),
        ("rearm=0.01", {"rearm": 0.01}),
    ]
    rows = run_variants(ts, o, c, variants)
    for r in rows:
        print(f"{r['name']:16s} n={r['n']:2d} expo={r['exposure']*100:5.1f}% "
              f"days={r['days']:4d} cagr={r['cagr']*100:6.1f}% "
              f"dd={r['dd']*100:5.1f}% sharpe={r['sharpe']:5.2f} "
              f"years={r['entry_years']}")

    # Combinations that keep >=20% exposure.
    combos = [
        ("A 15/20/90/20/05", {"deep_dd": 0.15, "hold": 90}),
        ("B 15/20/60/10/03", {"deep_dd": 0.15, "exit_low": 10, "rearm": 0.03}),
        ("C 15/10/60/20/03", {"deep_dd": 0.15, "entry_break": 10, "rearm": 0.03}),
        ("D 15/10/90/20/03", {"deep_dd": 0.15, "entry_break": 10, "hold": 90,
                               "rearm": 0.03}),
        ("E 18/20/90/20/05", {"deep_dd": 0.18, "hold": 90}),
        ("F 15/15/90/20/03", {"deep_dd": 0.15, "entry_break": 15, "hold": 90,
                               "rearm": 0.03}),
        ("G 12/20/60/20/03", {"deep_dd": 0.12, "rearm": 0.03}),
        ("H 15/20/60/20/02", {"deep_dd": 0.15, "rearm": 0.02}),
        ("I 20/20/90/20/00", {"hold": 90, "rearm": 0.0}),
        ("J 15/20/90/20/00", {"deep_dd": 0.15, "hold": 90, "rearm": 0.0}),
        ("K 15/20/60/20/00", {"deep_dd": 0.15, "rearm": 0.0}),
        ("L 15/20/90/10/05", {"deep_dd": 0.15, "hold": 90, "exit_low": 10}),
        ("M 10/20/90/20/05", {"deep_dd": 0.10, "hold": 90}),
        ("N 12/20/90/20/05", {"deep_dd": 0.12, "hold": 90}),
        ("O 10/20/75/20/05", {"deep_dd": 0.10, "hold": 75}),
        ("P 12/20/90/10/05", {"deep_dd": 0.12, "hold": 90, "exit_low": 10}),
        ("Q 10/20/90/10/05", {"deep_dd": 0.10, "hold": 90, "exit_low": 10}),
        ("R 12/20/75/10/05", {"deep_dd": 0.12, "hold": 75, "exit_low": 10}),
        ("S 10/20/60/10/05", {"deep_dd": 0.10, "exit_low": 10}),
        ("T 15/20/75/10/05", {"deep_dd": 0.15, "hold": 75, "exit_low": 10}),
        ("U 08/20/60/10/05", {"deep_dd": 0.08, "exit_low": 10}),
        ("V 10/20/60/12/05", {"deep_dd": 0.10, "exit_low": 12}),
        ("W 10/20/60/15/05", {"deep_dd": 0.10, "exit_low": 15}),
        ("X 10/15/60/10/05", {"deep_dd": 0.10, "entry_break": 15, "exit_low": 10}),
        ("Y 10/20/45/10/05", {"deep_dd": 0.10, "hold": 45, "exit_low": 10}),
        ("Z 10/20/75/10/05", {"deep_dd": 0.10, "hold": 75, "exit_low": 10}),
        ("AA 12/20/60/10/05", {"deep_dd": 0.12, "exit_low": 10}),
        ("AB 12/20/60/15/05", {"deep_dd": 0.12, "exit_low": 15}),
        ("AC 12/20/45/10/05", {"deep_dd": 0.12, "hold": 45, "exit_low": 10}),
        ("AD 10/20/60/15/03", {"deep_dd": 0.10, "exit_low": 15, "rearm": 0.03}),
        ("AE 20/20/90/15/05", {"hold": 90, "exit_low": 15}),
        ("AF 15/20/90/15/05", {"deep_dd": 0.15, "hold": 90, "exit_low": 15}),
        ("AG 10/20/90/15/05", {"deep_dd": 0.10, "hold": 90, "exit_low": 15}),
        ("AH 12/20/90/15/05", {"deep_dd": 0.12, "hold": 90, "exit_low": 15}),
        ("AI 15/20/60/15/05", {"deep_dd": 0.15, "exit_low": 15}),
        ("AJ 15/20/120/15/05", {"deep_dd": 0.15, "hold": 120, "exit_low": 15}),
        ("AK 15/20/90/20/05", {"deep_dd": 0.15, "hold": 90, "exit_low": 20}),
        ("AL 18/20/90/15/05", {"deep_dd": 0.18, "hold": 90, "exit_low": 15}),
    ]
    print("\n-- combinations")
    rows2 = run_variants(ts, o, c, combos)
    for r in rows2:
        print(f"{r['name']:20s} n={r['n']:2d} expo={r['exposure']*100:5.1f}% "
              f"days={r['days']:4d} cagr={r['cagr']*100:6.1f}% "
              f"dd={r['dd']*100:5.1f}% sharpe={r['sharpe']:5.2f} "
              f"years={r['entry_years']}")
        for e in r["episodes"]:
            print(f"    {e['entry_date']} -> {e['exit_date'] or 'open':10s} "
                  f"{e['days']:3d}d {e['ret']*100:7.2f}% {e['exit_reason']}")

    payload = {"single": rows, "combos": rows2}
    (HERE / "diagnose.json").write_text(json.dumps(payload, indent=1, default=float))
    print("\nwrote", HERE / "diagnose.json")


if __name__ == "__main__":
    main()
