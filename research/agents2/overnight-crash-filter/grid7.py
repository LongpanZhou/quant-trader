"""Grid 7: neighbourhood of the first-hour hybrid (band x m x vol x stop x thr)."""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

pd.set_option("display.width", 260)
pd.set_option("display.max_rows", 400)

WIN = {"10y": (58.80, 44.56), "5y": (49.88, 33.49)}


def main():
    t0 = time.time()
    ts, o, h, lo, c, v = lab.load_panel()
    d = lab.Days(ts, o, c)
    rows = []
    for band in (0.0, 0.01, 0.02):
        g = d.gate(band=band)
        for m in (45, 60):
            for vm in (0.30, 0.35, 0.40):
                for stop in (0.035, 0.04, 0.05):
                    for thr in (-0.002, 0.0, 0.002):
                        w = lab.build_weights(d, base="signal", m=m, gate=g,
                                              vol_max=vm, stop=stop, signal_thr=thr)
                        rec = {"band": band, "m": m, "vol": vm, "stop": stop, "thr": thr}
                        for start, tag in ((lab.START10, "10y"), (lab.START5, "5y")):
                            r = lab.run_window(ts, o, c, w, start, band=0.02, slippage_bps=1.0)
                            s = lab.stats(r)
                            rec[f"{tag}_c"] = s["cagr"] * 100
                            rec[f"{tag}_d"] = s["max_drawdown"] * 100
                        rec["dom10"] = rec["10y_c"] > WIN["10y"][0] and rec["10y_d"] < WIN["10y"][1]
                        rec["dom5"] = rec["5y_c"] > WIN["5y"][0] and rec["5y_d"] < WIN["5y"][1]
                        rows.append(rec)
                        print(f"  band{band:.2f} m{m} vol{vm:.2f} stop{stop:.3f} thr{thr:+.3f}  "
                              f"10y {rec['10y_c']:6.2f}/{rec['10y_d']:5.2f}  "
                              f"5y {rec['5y_c']:6.2f}/{rec['5y_d']:5.2f}  "
                              f"{'DOM' if rec['dom10'] else '   '}/{'DOM' if rec['dom5'] else '   '} "
                              f"[{time.time()-t0:4.0f}s]")
    df = pd.DataFrame(rows)
    print(f"\n{len(df)} configs; domin10 {df.dom10.sum()}, domin5 {df.dom5.sum()}, both "
          f"{(df.dom10 & df.dom5).sum()}")
    print("\nbest by min(10y_d, 5y_d) subject to CAGR >= winner:")
    sel = df[(df["10y_c"] >= WIN["10y"][0]) & (df["5y_c"] >= WIN["5y"][0])]
    print(sel.sort_values(["5y_d", "10y_d"]).head(20).to_string(index=False, float_format=lambda x: f"{x:6.2f}"))
    df.to_csv(HERE / "grid7.csv", index=False)


if __name__ == "__main__":
    main()
