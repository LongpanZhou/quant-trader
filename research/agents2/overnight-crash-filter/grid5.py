"""Grid 5: faster crash gates + parameter surface around the first-hour hybrid."""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

pd.set_option("display.width", 260)
pd.set_option("display.max_rows", 300)


def dd_window(ts, eq):
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    j = int(np.argmin(dd)); i = int(np.argmax(eq[: j + 1]))
    return f"{str(ts[i])[:10]}..{str(ts[j])[:10]}"


def main():
    t0 = time.time()
    ts, o, h, lo, c, v = lab.load_panel()
    d = lab.Days(ts, o, c)
    g2 = d.gate(band=0.02)
    g0 = d.gate(band=0.0)
    qc = d.dclose[:, 0]
    rows = []

    def add(name, w):
        rec = {"name": name}
        for start, tag in ((lab.START10, "10y"), (lab.START5, "5y")):
            r = lab.run_window(ts, o, c, w, start, band=0.02, slippage_bps=1.0)
            s = lab.stats(r)
            rec[f"{tag}_c"] = s["cagr"] * 100
            rec[f"{tag}_d"] = s["max_drawdown"] * 100
            rec[f"{tag}_s"] = s["sharpe"]
            rec[f"{tag}_w"] = dd_window(ts[lab.bt.start_index(ts, start):], r["equity"])
            rec[f"{tag}_f"] = s["fills"]
        rows.append(rec)
        print(f"  {name:44s} 10y {rec['10y_c']:6.2f}/{rec['10y_d']:5.2f}  "
              f"5y {rec['5y_c']:6.2f}/{rec['5y_d']:5.2f} [{time.time()-t0:4.0f}s]")

    # ---- fast crash gates as an extra mask on the regime ----
    def fast_gate(kind, thr):
        g = g2.copy()
        if kind == "ret5":
            r5 = np.full(d.nd, np.nan)
            r5[5:] = qc[5:] / qc[:-5] - 1
            g &= ~(r5 < thr)
        elif kind == "ret1":
            r1 = np.r_[np.nan, qc[1:] / qc[:-1] - 1]
            g &= ~(r1 < thr)
        elif kind == "dd10":
            hi = pd.Series(qc).rolling(10).max().to_numpy()
            g &= ~(qc / hi - 1 < -thr)
        return g

    print("== extra fast crash gates (applied to the overnight entry) ==")
    base_kw = dict(base="signal", m=60, vol_max=0.35, stop=0.04)
    for kind, thr in (("ret5", -0.04), ("ret5", -0.06), ("ret1", -0.02), ("ret1", -0.03), ("dd10", 0.04)):
        add(f"H2 + {kind}{thr:+.2f}",
            lab.build_weights(d, gate=fast_gate(kind, thr), **base_kw))
    add("P2 + ret5-0.06",
        lab.build_weights(d, base="morning", m=30, gate=fast_gate("ret5", -0.06), vol_pct_max=0.95))

    print("== H2 vol surface ==")
    for vm in (0.28, 0.30, 0.32, 0.38):
        add(f"H2 vol<{vm:.2f}", lab.build_weights(d, base="signal", m=60, gate=g2, vol_max=vm, stop=0.04))

    print("== H2 signal threshold ==")
    for thr in (-0.005, -0.002, 0.002):
        add(f"H2 thr{thr:+.3f}",
            lab.build_weights(d, base="signal", m=60, gate=g2, vol_max=0.35, stop=0.04, signal_thr=thr))

    print("== H2 m surface ==")
    for m in (45, 75, 90):
        add(f"H2 m={m}", lab.build_weights(d, base="signal", m=m, gate=g2, vol_max=0.35, stop=0.04))

    print("== H2 stop = none / armed ==")
    add("H2 no stop", lab.build_weights(d, base="signal", m=60, gate=g2, vol_max=0.35))
    add("H2 stop4 arm20", lab.build_weights(d, base="signal", m=60, gate=g2, vol_max=0.35, stop=0.04, stop_arm_ma20=True))

    print("== H2 regime band ==")
    add("H2 band0", lab.build_weights(d, base="signal", m=60, gate=g0, vol_max=0.35, stop=0.04))
    for b in (0.01, 0.03):
        add(f"H2 band{b:.2f}", lab.build_weights(d, base="signal", m=60, gate=d.gate(band=b), vol_max=0.35, stop=0.04))

    df = pd.DataFrame(rows)
    print("\n" + df.to_string(index=False, float_format=lambda x: f"{x:6.2f}"))
    df.to_csv(HERE / "grid5.csv", index=False)


if __name__ == "__main__":
    main()
