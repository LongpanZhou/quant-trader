"""Grid 8: afternoon-exit threshold surface with 1/5/10 bp costs."""
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
WIN = {"10y": {"1": (58.80, 44.56), "5": (54.60, 47.08), "10": (49.50, 50.06)},
       "5y": {"1": (49.88, 33.49), "5": (45.89, 34.13), "10": (41.05, 34.93)}}


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
                rec[f"{tag}_{int(slip)}_s"] = s["sharpe"]
                if slip == 1.0:
                    rec[f"{tag}_f"] = s["fills"]
        rows.append(rec)
        line = f"  {name:34s}"
        for tag in ("10y", "5y"):
            for k in (1, 5, 10):
                line += f" {tag}{k}bp {rec[f'{tag}_{k}_c']:6.2f}/{rec[f'{tag}_{k}_d']:5.2f}"
        print(line + f"  f{rec['10y_f']} [{time.time()-t0:4.0f}s]")

    for band, g in ((0.0, g0), (0.01, d.gate(band=0.01)), (0.02, g2)):
        for thr in (-0.010, -0.0075, -0.005, -0.0025, 0.0, 0.0025):
            add(f"b{band:.2f} thr{thr:+.4f}",
                lab.build_weights(d, base="signal", m=60, gate=g, vol_max=0.35,
                                  stop=0.04, signal_thr=thr))

    df = pd.DataFrame(rows)
    df.to_csv(HERE / "grid8.csv", index=False)
    # pass/fail summary at 5bp
    print("\n5bp pass/fail vs winner (CAGR>w, DD<w):")
    for _, r in df.iterrows():
        ok10 = r["10y_5_c"] > WIN["10y"]["5"][0] and r["10y_5_d"] < WIN["10y"]["5"][1]
        ok5 = r["5y_5_c"] > WIN["5y"]["5"][0] and r["5y_5_d"] < WIN["5y"]["5"][1]
        print(f"  {r['name']:26s} 10y {r['10y_5_c']:6.2f}/{r['10y_5_d']:5.2f} {'PASS' if ok10 else 'fail'}   "
              f"5y {r['5y_5_c']:6.2f}/{r['5y_5_d']:5.2f} {'PASS' if ok5 else 'fail'}")


if __name__ == "__main__":
    main()
