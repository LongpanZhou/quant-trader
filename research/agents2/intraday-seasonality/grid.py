"""Focused grid for the last-hour continuation overlay, with cost sensitivity and
an explicit in-sample / out-of-sample walk-forward.

Rule: on a risk-on session where QQQ's 15:30 price is below its session open by
more than `thr`, sell TQQQ at the 15:01 open and buy back at the 15:59 open.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/intraday-seasonality/grid.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import lib  # noqa: E402

OUT = Path(__file__).resolve().parent
IS_END = "2022-01-01"


def main():
    ts, opens, closes = lib.load_panel()
    cal = lib.calendar(ts)
    first, last = cal["first"], cal["last"]
    w_base, _ = lib.build_base(ts, opens, closes)
    dates = cal["dates"]

    i1400 = lib.time_index(ts, first, last, 14, 0)
    i1430 = lib.time_index(ts, first, last, 14, 30)
    i1500 = lib.time_index(ts, first, last, 15, 0)
    i1530 = lib.time_index(ts, first, last, 15, 30)
    q_open = opens[first, 0]
    q_c1530 = closes[i1530, 0]
    q_c1400 = closes[i1400, 0]
    q_c1430 = closes[i1430, 0]
    q_c1500 = closes[i1500, 0]
    dc = closes[last, 0]
    ma20 = pd.Series(dc).rolling(20).mean().to_numpy()
    ma_prev = np.r_[np.nan, ma20[:-1]]
    below_ma20 = dc < ma_prev
    on, _, _ = lib.regime_on(ts, closes)

    sig_open = q_c1530 / q_open - 1.0
    sig_1400 = q_c1400 / q_open - 1.0
    sig_1430 = q_c1430 / q_open - 1.0
    sig_1500 = q_c1500 / q_open - 1.0

    rows = []

    def ev(name, w, note, slip=1.0):
        r = lib.simulate(ts, opens, closes, w, slip)
        row = {"name": name, "note": note, "fills": r["fills"], "slip": slip}
        for label, start, end in (("10y", lib.START10, None), ("5y", lib.START5, None),
                                  ("IS", lib.START10, IS_END), ("OOS", IS_END, None)):
            s = lib.window(r, ts, start, end)
            row[f"{label}_cagr"] = s["cagr"]
            row[f"{label}_dd"] = s["max_drawdown"]
            row[f"{label}_sharpe"] = s["sharpe"]
        return row

    rows.append(ev("BASE", w_base, "winner"))

    # ---------- threshold x start-time grid
    for start_name, sig, start_hm in (
        ("14:00", sig_1400, (14, 0)),
        ("14:30", sig_1430, (14, 30)),
        ("15:00", sig_1500, (15, 0)),
    ):
        for thr in (0.0, -0.0025, -0.005, -0.0075, -0.010, -0.015, -0.020):
            mask = sig < thr
            w = lib.carve(w_base, cal, start_hm, (15, 59), ts, mask)
            rows.append(ev(f"{start_name} thr{thr*100:.2f}", w, f"n={int(mask.sum())}"))

    # ---------- MA20 gate variants (15:00 start)
    for thr in (-0.0025, -0.005, -0.010):
        for gate_name, gate in (("belowMA20", below_ma20), ("aboveMA20", ~below_ma20)):
            mask = (sig_1500 < thr) & gate
            w = lib.carve(w_base, cal, (15, 0), (15, 59), ts, mask)
            rows.append(ev(f"15:00 thr{thr*100:.2f} {gate_name}", w, f"n={int(mask.sum())}"))

    # ---------- 15:30 start (last 30m) for comparison
    sig_1530 = q_c1530 / q_open - 1.0
    for thr in (0.0, -0.005, -0.010):
        mask = sig_1530 < thr
        w = lib.carve(w_base, cal, (15, 30), (15, 59), ts, mask)
        rows.append(ev(f"15:30 thr{thr*100:.2f}", w, f"n={int(mask.sum())}"))

    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / "grid.csv", index=False)
    cols = ["name", "note", "10y_cagr", "10y_dd", "5y_cagr", "5y_dd",
            "IS_cagr", "IS_dd", "OOS_cagr", "OOS_dd", "fills"]
    out = tab[cols].copy()
    for c in cols[2:-1]:
        out[c] = (out[c] * 100).round(2)
    pd.set_option("display.width", 240)
    print(out.to_string(index=False))

    # ---------- cost sensitivity for finalists
    print("\n=== cost sensitivity ===")
    finalists = {
        "thr0.00": sig_1500 < 0.0,
        "thr-0.25": sig_1500 < -0.0025,
        "thr-0.50": sig_1500 < -0.005,
        "thr-0.75": sig_1500 < -0.0075,
        "thr-1.00": sig_1500 < -0.010,
        "thr-0.50 belowMA20": (sig_1500 < -0.005) & below_ma20,
    }
    crows = []
    for nm, mask in finalists.items():
        w = lib.carve(w_base, cal, (15, 0), (15, 59), ts, mask)
        for slip in (1.0, 5.0, 10.0):
            r = lib.simulate(ts, opens, closes, w, slip)
            row = {"name": nm, "slip": slip}
            for label, start, end in (("10y", lib.START10, None), ("5y", lib.START5, None),
                                      ("IS", lib.START10, IS_END), ("OOS", IS_END, None)):
                s = lib.window(r, ts, start, end)
                row[f"{label}_cagr"] = s["cagr"]
                row[f"{label}_dd"] = s["max_drawdown"]
            crows.append(row)
    ctab = pd.DataFrame(crows)
    ctab.to_csv(OUT / "cost.csv", index=False)
    cc = ctab.copy()
    for c in cc.columns[2:]:
        cc[c] = (cc[c] * 100).round(2)
    print(cc.to_string(index=False))


if __name__ == "__main__":
    main()
