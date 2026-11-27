"""Overlay grid: apply candidate intraday-seasonality overlays to the round-1
winner and score them on 10y / 5y and on the 2017-2021 vs 2022-2026 split.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/intraday-seasonality/variants.py
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
    w_base, diag = lib.build_base(ts, opens, closes)
    dates = cal["dates"]

    i1500 = lib.time_index(ts, first, last, 15, 0)
    i1530 = lib.time_index(ts, first, last, 15, 30)
    q_open = opens[first, 0]
    q_c1530 = closes[i1530, 0]
    t_open = opens[first, 1]
    t_c1530 = closes[i1530, 1]
    q_day = q_c1530 / q_open - 1.0
    q_gap_day = q_c1530 / np.r_[np.nan, closes[i1530[:-1], 0]] - 1.0
    t_day = t_c1530 / t_open - 1.0
    on, _, _ = lib.regime_on(ts, closes)
    dow = cal["dow"]

    base = {}
    r = lib.simulate(ts, opens, closes, w_base, 1.0)
    for label, start, end in (("10y", lib.START10, None), ("5y", lib.START5, None),
                              ("IS", lib.START10, IS_END), ("OOS", IS_END, None)):
        base[label] = lib.window(r, ts, start, end)

    def ev(name, w, note=""):
        r = lib.simulate(ts, opens, closes, w, 1.0)
        row = {"name": name, "note": note, "fills": r["fills"]}
        for label, start, end in (("10y", lib.START10, None), ("5y", lib.START5, None),
                                  ("IS", lib.START10, IS_END), ("OOS", IS_END, None)):
            s = lib.window(r, ts, start, end)
            row[f"{label}_cagr"] = s["cagr"]
            row[f"{label}_dd"] = s["max_drawdown"]
            row[f"{label}_sharpe"] = s["sharpe"]
        return row

    rows = []
    rows.append(ev("BASE winner", w_base))

    # ---------------- last-30-min carve by QQQ day move at 15:30
    for thr in (0.0, -0.005, -0.0075, -0.010, -0.015, -0.020, -0.025, -0.030):
        mask = (q_day < thr)
        w = lib.carve(w_base, cal, (15, 30), (15, 59), ts, mask)
        rows.append(ev(f"last30 QQQday<{thr*100:.2f}%", w, f"n={int(mask.sum())}"))

    # ---------------- last-30-min carve by TQQQ day move
    for thr in (-0.01, -0.02, -0.03, -0.04):
        mask = (t_day < thr)
        w = lib.carve(w_base, cal, (15, 30), (15, 59), ts, mask)
        rows.append(ev(f"last30 TQQQday<{thr*100:.1f}%", w, f"n={int(mask.sum())}"))

    # ---------------- last-30-min carve, calendar
    rows.append(ev("last30 opex", lib.carve(w_base, cal, (15, 30), (15, 59), ts, cal["opex"]),
                   f"n={int(cal['opex'].sum())}"))
    rows.append(ev("last30 wed", lib.carve(w_base, cal, (15, 30), (15, 59), ts, dow == 2),
                   f"n={int((dow==2).sum())}"))
    rows.append(ev("last30 all", lib.carve(w_base, cal, (15, 30), (15, 59), ts, np.ones(len(dow), bool)),
                   f"n={len(dow)}"))
    rows.append(ev("last30 opex+wed", lib.carve(w_base, cal, (15, 30), (15, 59), ts, cal["opex"] | (dow == 2))))
    rows.append(ev("last30 prehol", lib.carve(w_base, cal, (15, 30), (15, 59), ts, cal["pre_hol"]),
                   f"n={int(cal['pre_hol'].sum())}"))

    # ---------------- last hour (15:00) carve
    for thr in (0.0, -0.010, -0.020):
        mask = (q_day < thr)
        w = lib.carve(w_base, cal, (15, 0), (15, 59), ts, mask)
        rows.append(ev(f"last60 QQQday<{thr*100:.2f}%", w, f"n={int(mask.sum())}"))

    # ---------------- lunch carve
    i1200 = lib.time_index(ts, first, last, 12, 0)
    i1400 = lib.time_index(ts, first, last, 14, 0)
    q_morning = closes[i1200, 0] / q_open - 1.0
    for thr in (0.010, 0.015, 0.020):
        mask = (q_morning > thr)
        rows.append(ev(f"lunch carve morning>{thr*100:.1f}%",
                       lib.carve(w_base, cal, (12, 0), (14, 0), ts, mask), f"n={int(mask.sum())}"))
    for thr in (-0.010, -0.015, -0.020):
        mask = (q_morning < thr)
        rows.append(ev(f"lunch carve morning<{thr*100:.1f}%",
                       lib.carve(w_base, cal, (12, 0), (14, 0), ts, mask), f"n={int(mask.sum())}"))
    rows.append(ev("lunch carve opex", lib.carve(w_base, cal, (12, 0), (14, 0), ts, cal["opex"])))

    # ---------------- stop gating
    ones = np.ones(len(dow), bool)
    for name, gate in (("no-stop opex", ~cal["opex"]),
                       ("no-stop pre_opex", ~cal["pre_opex"]),
                       ("no-stop post_opex", ~cal["post_opex"]),
                       ("no-stop prehol", ~cal["pre_hol"]),
                       ("no-stop posthol", ~cal["post_hol"]),
                       ("no-stop fri", dow != 4),
                       ("no-stop mon", dow != 0),
                       ("no-stop opEx-week-not", ~(cal["opex"]))):
        w, _ = lib.build_base(ts, opens, closes, armed_mask=gate)
        rows.append(ev(name, w, f"disarmed={int((~gate).sum())}"))

    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / "variants.csv", index=False)
    show = ["name", "note", "10y_cagr", "10y_dd", "5y_cagr", "5y_dd",
            "IS_cagr", "IS_dd", "OOS_cagr", "OOS_dd", "fills"]
    pd.set_option("display.width", 220)
    out = tab[show].copy()
    for c in show[2:-1]:
        out[c] = (out[c] * 100).round(2)
    print(out.to_string(index=False))
    print("\nBASE 10y", base["10y"]["cagr"] * 100, base["10y"]["max_drawdown"] * 100,
          "5y", base["5y"]["cagr"] * 100, base["5y"]["max_drawdown"] * 100)


if __name__ == "__main__":
    main()
