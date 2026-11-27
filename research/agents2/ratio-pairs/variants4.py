"""Froth variants: with a short-term breakdown trigger; partial sizing."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bt_lib as L  # noqa: E402


def main():
    ts, opens, closes = L.load_panel()
    d = L.add_ratio_features(L.daily_frame(ts, opens, closes))
    dates, first, last = L.day_bounds(ts)
    nd = len(first)
    hold, risk_on, _, _ = L.winner_state(ts, opens, closes)
    d["r5"] = d["logr"].diff(5)
    d["r10"] = d["logr"].diff(10)
    d["r20"] = d["logr"].diff(20)
    d["qqq_ext200"] = np.log(d["qqq_c"] / d["qqq_c"].rolling(200).mean())

    def run(label, froth, qqq_frac=1.0, slip=1.0, asset="QQQ"):
        tgt = np.zeros((nd, 3))
        tgt[risk_on & ~froth, 1] = 1
        if froth.any():
            if asset == "QQQ":
                tgt[risk_on & froth, 1] = 1 - qqq_frac
                tgt[risk_on & froth, 0] = qqq_frac
            elif asset == "BIL":
                pass
        tgt[~risk_on, 2] = 1
        if asset == "BIL":
            tgt[froth, :] = (0, 0, 1)
        w = L.weights_from_daily(ts, tgt, first, last, stopped=~hold)
        r = L.metrics(ts, opens, closes, w, slip=slip)
        r5 = L.metrics(ts, opens, closes, w, slip=slip, start=L.START5)
        print(f"{label:48s} 10y {r['cagr']*100:6.2f}/{r['max_drawdown']*100:5.2f}  "
              f"5y {r5['cagr']*100:6.2f}/{r5['max_drawdown']*100:5.2f}  n={int(froth.sum()):4d} "
              f"({froth.mean()*100:4.1f}%)")
        return r, r5

    ext200 = d["ext200"].shift(1).to_numpy()
    ext60 = d["ext60"].shift(1).to_numpy()
    ext20 = d["ext20"].shift(1).to_numpy()
    r5 = d["r5"].shift(1).to_numpy()
    r10 = d["r10"].shift(1).to_numpy()

    print("reference")
    run("winner", np.zeros(nd, bool))
    run("ext200>0.18 -> QQQ", np.nan_to_num(ext200, nan=-9) > 0.18)
    run("ext200>0.18 -> 50/50", np.nan_to_num(ext200, nan=-9) > 0.18, qqq_frac=0.5)
    run("ext200>0.18 -> 25% QQQ", np.nan_to_num(ext200, nan=-9) > 0.18, qqq_frac=0.25)

    print("\nfroth + short-term breakdown")
    for cond_name, cond in (
        ("ext20<0", np.nan_to_num(ext20, nan=1) < 0),
        ("ext20<-0.02", np.nan_to_num(ext20, nan=1) < -0.02),
        ("r5<0", np.nan_to_num(r5, nan=1) < 0),
        ("r10<0", np.nan_to_num(r10, nan=1) < 0),
        ("r5<-0.03", np.nan_to_num(r5, nan=1) < -0.03),
        ("ext60<0", np.nan_to_num(ext60, nan=1) < 0),
    ):
        for th in (0.15, 0.18, 0.22):
            f = (np.nan_to_num(ext200, nan=-9) > th) & cond
            run(f"ext200>{th:.2f} & {cond_name} -> QQQ", f)

    print("\nbreakdown-only (no froth condition)")
    for cond_name, cond in (
        ("ext20<0", np.nan_to_num(ext20, nan=1) < 0),
        ("ext20<-0.03", np.nan_to_num(ext20, nan=1) < -0.03),
        ("r10<-0.05", np.nan_to_num(r10, nan=1) < -0.05),
        ("r10<-0.08", np.nan_to_num(r10, nan=1) < -0.08),
    ):
        run(f"{cond_name} -> QQQ", cond)

    print("\nQQQ-extension control at matched frequency")
    for th in (0.12, 0.14, 0.16):
        f = np.nan_to_num(d["qqq_ext200"].shift(1).to_numpy(), nan=-9) > th
        run(f"QQQ ext200>{th:.2f} -> QQQ", f)
        run(f"QQQ ext200>{th:.2f} -> BIL", f, asset="BIL")


if __name__ == "__main__":
    main()
