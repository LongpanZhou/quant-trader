"""Grid 9: vol-threshold refinement for the cost-robust variant + DD windows."""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

pd.set_option("display.width", 280)
pd.set_option("display.max_rows", 300)


def ddw(ts, eq):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    j = int(np.argmin(dd)); i = int(np.argmax(eq[: j + 1]))
    return f"{str(ts[i])[:10]}..{str(ts[j])[:10]}"


def main():
    t0 = time.time()
    ts, o, h, lo, c, v = lab.load_panel()
    d = lab.Days(ts, o, c)
    g0 = d.gate(band=0.0)
    g2 = d.gate(band=0.02)
    rows = []

    def add(name, w):
        rec = {"name": name}
        for start, tag in ((lab.START10, "10y"), (lab.START5, "5y")):
            for slip in (1.0, 5.0, 10.0):
                r = lab.run_window(ts, o, c, w, start, band=0.02, slippage_bps=slip)
                s = lab.stats(r)
                rec[f"{tag}_{int(slip)}_c"] = s["cagr"] * 100
                rec[f"{tag}_{int(slip)}_d"] = s["max_drawdown"] * 100
                if slip == 1.0:
                    rec[f"{tag}_w"] = ddw(ts[lab.bt.start_index(ts, start):], r["equity"])
                    rec[f"{tag}_f"] = s["fills"]
                    rec[f"{tag}_s"] = s["sharpe"]
        rows.append(rec)
        print(f"  {name:30s} 10y {rec['10y_1_c']:6.2f}/{rec['10y_1_d']:5.2f} "
              f"{rec['10y_5_c']:6.2f}/{rec['10y_5_d']:5.2f} {rec['10y_10_c']:6.2f}/{rec['10y_10_d']:5.2f} | "
              f"5y {rec['5y_1_c']:6.2f}/{rec['5y_1_d']:5.2f} {rec['5y_5_c']:6.2f}/{rec['5y_5_d']:5.2f} "
              f"{rec['5y_10_c']:6.2f}/{rec['5y_10_d']:5.2f}  f{rec['10y_f']} "
              f"w5y {rec['5y_w']} [{time.time()-t0:4.0f}s]")

    for g, btag in ((g0, "b0"), (g2, "b2")):
        for vm in (0.25, 0.28, 0.30, 0.32, 0.35, 0.40):
            add(f"{btag} thr-0.005 vol{vm:.2f}",
                lab.build_weights(d, base="signal", m=60, gate=g, vol_max=vm, stop=0.04, signal_thr=-0.005))
    for g, btag in ((g0, "b0"), (g2, "b2")):
        for vm in (0.28, 0.30, 0.35):
            add(f"{btag} thr-0.0025 vol{vm:.2f}",
                lab.build_weights(d, base="signal", m=60, gate=g, vol_max=vm, stop=0.04, signal_thr=-0.0025))

    df = pd.DataFrame(rows)
    df.to_csv(HERE / "grid9.csv", index=False)


if __name__ == "__main__":
    main()
