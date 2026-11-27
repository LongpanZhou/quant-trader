"""Grid 6: causal fast crash gates (using the 15:59-known price), applied
only to the overnight leg."""
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
    qc, qn = d.dclose[:, 0], d.dc_now[:, 0]
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
        print(f"  {name:46s} 10y {rec['10y_c']:6.2f}/{rec['10y_d']:5.2f}  "
              f"5y {rec['5y_c']:6.2f}/{rec['5y_d']:5.2f} [{time.time()-t0:4.0f}s]")

    # causal same-day return: 15:59 print vs prior close
    r1_now = np.r_[np.nan, qn[1:] / qc[:-1] - 1.0]
    # 10-day drawdown from the 10-day high close, using the 15:59 print
    hi10 = pd.Series(qc).rolling(10).max().to_numpy()
    hi10 = np.r_[np.nan, hi10[:-1]]
    dd10_now = qn / hi10 - 1.0
    print("skipped nights by gate (10y):")
    for thr in (-0.015, -0.02, -0.025, -0.03):
        sel = (r1_now < thr)
        print(f"  ret1<{thr:+.3f}: {int(sel[lab.bt.start_index(ts, lab.START10):].sum())} nights, "
              f"{int((sel & g2)[lab.bt.start_index(ts, lab.START10):].sum())} in regime")
    for thr in (0.03, 0.04, 0.06):
        sel = (dd10_now < -thr)
        print(f"  dd10<-{thr:.2f}: {int(sel[lab.bt.start_index(ts, lab.START10):].sum())} nights, "
              f"{int((sel & g2)[lab.bt.start_index(ts, lab.START10):].sum())} in regime")

    print("\n== P1 pure overnight + fast gate (overnight only) ==")
    for kind, vals in (("ret1", (-0.015, -0.02, -0.025, -0.03)), ("dd10", (0.03, 0.04, 0.06))):
        for thr in vals:
            nm = ~(r1_now < thr) if kind == "ret1" else ~(dd10_now < -thr)
            add(f"P1 + {kind}{thr:+.03f}",
                lab.build_weights(d, base="overnight", gate=g2, vol_max=0.35, night_mask=nm))

    print("\n== P2 morning30 + fast gate (overnight only) ==")
    for kind, thr in (("ret1", -0.02), ("ret1", -0.03), ("dd10", 0.04)):
        nm = ~(r1_now < thr) if kind == "ret1" else ~(dd10_now < -thr)
        add(f"P2 + {kind}{thr:+.03f}",
            lab.build_weights(d, base="morning", m=30, gate=g2, vol_pct_max=0.95, night_mask=nm))

    print("\n== H2 (signal60) + fast gate (overnight only) ==")
    for kind, thr in (("ret1", -0.015), ("ret1", -0.02), ("ret1", -0.025), ("ret1", -0.03),
                      ("dd10", 0.03), ("dd10", 0.04), ("dd10", 0.06)):
        nm = ~(r1_now < thr) if kind == "ret1" else ~(dd10_now < -thr)
        add(f"H2 + {kind}{thr:+.03f}",
            lab.build_weights(d, base="signal", m=60, gate=g2, vol_max=0.35, stop=0.04, night_mask=nm))

    print("\n== H1 (signal30) + fast gate (overnight only) ==")
    for kind, thr in (("ret1", -0.02), ("ret1", -0.03), ("dd10", 0.04)):
        nm = ~(r1_now < thr) if kind == "ret1" else ~(dd10_now < -thr)
        add(f"H1 + {kind}{thr:+.03f}",
            lab.build_weights(d, base="signal", m=30, gate=g2, vol_max=0.35, stop=0.04, night_mask=nm))

    df = pd.DataFrame(rows)
    print("\n" + df.to_string(index=False, float_format=lambda x: f"{x:6.2f}"))
    df.to_csv(HERE / "grid6.csv", index=False)


if __name__ == "__main__":
    main()
