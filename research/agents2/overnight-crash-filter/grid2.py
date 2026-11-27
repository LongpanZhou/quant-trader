"""Grid 2: volatility crash filters (proper annualised units) on the
overnight and first-30m blocks."""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 300)


def dd_window(ts, eq):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    j = int(np.argmin(dd))
    i = int(np.argmax(eq[: j + 1]))
    return str(ts[i])[:10], str(ts[j])[:10]


def main():
    t0 = time.time()
    ts, o, h, lo, c, v = lab.load_panel()
    d = lab.Days(ts, o, c)
    g0 = d.gate(band=0.0)
    g2 = d.gate(band=0.02)
    vol = d.vol(20, 0)
    voln = d.vol_now(20, 0)
    rows = []

    def add(name, w):
        res = {}
        for start in (lab.START10, lab.START5):
            r = lab.run_window(ts, o, c, w, start, band=0.02, slippage_bps=1.0)
            s = lab.stats(r)
            s["ddwin"] = dd_window(ts[lab.bt.start_index(ts, start):], r["equity"])
            res[start] = s
        rows.append({
            "name": name,
            "10y_cagr": res[lab.START10]["cagr"] * 100,
            "10y_dd": res[lab.START10]["max_drawdown"] * 100,
            "10y_sh": res[lab.START10]["sharpe"],
            "10y_ddwin": res[lab.START10]["ddwin"],
            "5y_cagr": res[lab.START5]["cagr"] * 100,
            "5y_dd": res[lab.START5]["max_drawdown"] * 100,
            "5y_sh": res[lab.START5]["sharpe"],
            "fills": res[lab.START10]["fills"],
        })
        print(f"  {name:40s} 10y {rows[-1]['10y_cagr']:6.2f}/{rows[-1]['10y_dd']:5.2f} "
              f"5y {rows[-1]['5y_cagr']:6.2f}/{rows[-1]['5y_dd']:5.2f} [{time.time()-t0:4.0f}s]")

    print("== overnight, plain SMA, vol filter (through prior close) ==")
    add("overnight", lab.build_weights(d, base="overnight", gate=g0))
    for vm in (0.20, 0.22, 0.25, 0.28, 0.30, 0.35, 0.40):
        add(f"overnight vol<{vm:.2f}", lab.build_weights(d, base="overnight", gate=g0, vol_max=vm))

    print("== overnight, 2% band, vol filter ==")
    add("overnight band2", lab.build_weights(d, base="overnight", gate=g2))
    for vm in (0.20, 0.22, 0.25, 0.28, 0.30, 0.35, 0.40):
        add(f"overnight band2 vol<{vm:.2f}", lab.build_weights(d, base="overnight", gate=g2, vol_max=vm))

    print("== overnight, band2, vol filter using today's 15:58 price ==")
    for vm in (0.25, 0.30, 0.35):
        add(f"overnight band2 volNOW<{vm:.2f}",
            lab.build_weights(d, base="overnight", gate=g2, vol_max=vm, vol_now=True))

    print("== morning30, band2, vol filter ==")
    for vm in (0.25, 0.30, 0.35):
        add(f"morning30 band2 vol<{vm:.2f}", lab.build_weights(d, base="morning", m=30, gate=g2, vol_max=vm))

    print("== morning30, plain, vol filter ==")
    for vm in (0.25, 0.30, 0.35):
        add(f"morning30 vol<{vm:.2f}", lab.build_weights(d, base="morning", m=30, gate=g0, vol_max=vm))

    df = pd.DataFrame(rows)
    print("\n" + df.to_string(index=False, float_format=lambda x: f"{x:6.2f}"))
    df.to_csv(HERE / "grid2.csv", index=False)


if __name__ == "__main__":
    main()
