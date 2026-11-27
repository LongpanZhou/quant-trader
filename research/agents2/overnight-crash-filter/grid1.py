"""Variant grid: overnight / first-hour blocks with crash filters."""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 200)


def main():
    t0 = time.time()
    ts, o, h, lo, c, v = lab.load_panel()
    d = lab.Days(ts, o, c)
    g0 = d.gate(band=0.0)
    g2 = d.gate(band=0.02)
    ma20 = d.ma(20)
    gm20 = np.r_[False, d.dclose[:-1, 0] > ma20[:-1]]

    rows = []

    def add(name, w, note=""):
        res = {}
        for start in (lab.START10, lab.START5):
            r = lab.run_window(ts, o, c, w, start, band=0.02, slippage_bps=1.0)
            s = lab.stats(r)
            res[start] = s
        rows.append({
            "name": name,
            "10y_cagr": res[lab.START10]["cagr"] * 100,
            "10y_dd": res[lab.START10]["max_drawdown"] * 100,
            "10y_sh": res[lab.START10]["sharpe"],
            "5y_cagr": res[lab.START5]["cagr"] * 100,
            "5y_dd": res[lab.START5]["max_drawdown"] * 100,
            "5y_sh": res[lab.START5]["sharpe"],
            "fills10": res[lab.START10]["fills"],
            "note": note,
        })
        print(f"  {name:44s} 10y {rows[-1]['10y_cagr']:6.2f}/{rows[-1]['10y_dd']:5.2f}  "
              f"5y {rows[-1]['5y_cagr']:6.2f}/{rows[-1]['5y_dd']:5.2f}  [{time.time()-t0:5.0f}s]")

    print("== bases, plain 165 SMA ==")
    add("full (daily baseline control)", lab.build_weights(d, base="full", gate=g0))
    add("overnight", lab.build_weights(d, base="overnight", gate=g0))
    add("morning30", lab.build_weights(d, base="morning", m=30, gate=g0))
    add("morning60", lab.build_weights(d, base="morning", m=60, gate=g0))
    add("signal30 (E2-like)", lab.build_weights(d, base="signal", m=30, gate=g0))

    print("== bases, 2% band ==")
    add("overnight band2", lab.build_weights(d, base="overnight", gate=g2))
    add("morning30 band2", lab.build_weights(d, base="morning", m=30, gate=g2))
    add("morning60 band2", lab.build_weights(d, base="morning", m=60, gate=g2))

    print("== vol filter on overnight (plain SMA) ==")
    for vm in (0.25, 0.30, 0.35):
        add(f"overnight vol<{vm:.2f}", lab.build_weights(d, base="overnight", gate=g0, vol_max=vm))
        add(f"morning30 vol<{vm:.2f}", lab.build_weights(d, base="morning", m=30, gate=g0, vol_max=vm))

    print("== MA20 short-term gate ==")
    add("overnight sma165&ma20", lab.build_weights(d, base="overnight", gate=g0 & gm20))
    add("morning30 sma165&ma20", lab.build_weights(d, base="morning", m=30, gate=g0 & gm20))
    add("morning60 sma165&ma20", lab.build_weights(d, base="morning", m=60, gate=g0 & gm20))

    print("== gap exit (first30) ==")
    for ge in (0.01, 0.02):
        add(f"morning30 gapexit{ge:.2f}", lab.build_weights(d, base="morning", m=30, gate=g0, gap_exit=ge))

    print("== stop from session open ==")
    for st in (0.02, 0.03, 0.04):
        add(f"morning30 stop{st:.2f}", lab.build_weights(d, base="morning", m=30, gate=g0, stop=st))
        add(f"morning60 stop{st:.2f}", lab.build_weights(d, base="morning", m=60, gate=g0, stop=st))
    add("morning60 stop0.03 arm20", lab.build_weights(d, base="morning", m=60, gate=g0, stop=0.03, stop_arm_ma20=True))

    df = pd.DataFrame(rows)
    print("\n" + df.to_string(index=False, float_format=lambda x: f"{x:6.2f}"))
    df.to_csv(HERE / "grid1.csv", index=False)


if __name__ == "__main__":
    main()
