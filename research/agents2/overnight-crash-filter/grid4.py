"""Grid 4: refine the first-hour hybrids, then cost sensitivity of finalists."""
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
    j = int(np.argmin(dd))
    i = int(np.argmax(eq[: j + 1]))
    return f"{str(ts[i])[:10]}..{str(ts[j])[:10]}"


def main():
    t0 = time.time()
    ts, o, h, lo, c, v = lab.load_panel()
    d = lab.Days(ts, o, c)
    g2 = d.gate(band=0.02)
    g0 = d.gate(band=0.0)
    rows = []

    def add(name, w, costs=(1.0,), verbose=True):
        rec = {"name": name}
        for start, tag in ((lab.START10, "10y"), (lab.START5, "5y")):
            for slip in costs:
                r = lab.run_window(ts, o, c, w, start, band=0.02, slippage_bps=slip)
                s = lab.stats(r)
                rec[f"{tag}_{slip:.0f}_c"] = s["cagr"] * 100
                rec[f"{tag}_{slip:.0f}_d"] = s["max_drawdown"] * 100
                rec[f"{tag}_{slip:.0f}_s"] = s["sharpe"]
                if slip == 1.0:
                    rec[f"{tag}_ddwin"] = dd_window(ts[lab.bt.start_index(ts, start):], r["equity"])
                    rec[f"{tag}_fills"] = s["fills"]
        rows.append(rec)
        if verbose:
            print(f"  {name:42s} 10y {rec['10y_1_c']:6.2f}/{rec['10y_1_d']:5.2f}  "
                  f"5y {rec['5y_1_c']:6.2f}/{rec['5y_1_d']:5.2f}  [{time.time()-t0:4.0f}s]")

    print("== signal60 vs signal30 with filters ==")
    for m in (30, 60):
        add(f"signal{m} band2 vol<.35", lab.build_weights(d, base="signal", m=m, gate=g2, vol_max=0.35))
        add(f"signal{m} band2 vol<.35 stop4",
            lab.build_weights(d, base="signal", m=m, gate=g2, vol_max=0.35, stop=0.04))
        add(f"signal{m} band2 vol<.35 stop4 arm",
            lab.build_weights(d, base="signal", m=m, gate=g2, vol_max=0.35, stop=0.04, stop_arm_ma20=True))
        add(f"signal{m} band2 volpct<.95 stop4",
            lab.build_weights(d, base="signal", m=m, gate=g2, vol_pct_max=0.95, stop=0.04))

    print("== stop surface (signal30, band2, vol<.35) ==")
    for st in (0.03, 0.035, 0.045, 0.05):
        add(f"signal30 stop{st:.3f}",
            lab.build_weights(d, base="signal", m=30, gate=g2, vol_max=0.35, stop=st))

    print("== vol surface (signal30, band2, stop4) ==")
    for vm in (0.28, 0.30, 0.40):
        add(f"signal30 vol<{vm:.2f} stop4",
            lab.build_weights(d, base="signal", m=30, gate=g2, vol_max=vm, stop=0.04))

    print("== regime surface (signal30, vol<.35, stop4) ==")
    add("signal30 band0 stop4", lab.build_weights(d, base="signal", m=30, gate=g0, vol_max=0.35, stop=0.04))
    add("signal30 band3 stop4", lab.build_weights(d, base="signal", m=30, gate=d.gate(band=0.03), vol_max=0.35, stop=0.04))
    add("signal30 band5 stop4", lab.build_weights(d, base="signal", m=30, gate=d.gate(band=0.05), vol_max=0.35, stop=0.04))

    df = pd.DataFrame(rows)
    print("\n" + df.to_string(index=False, float_format=lambda x: f"{x:6.2f}"))
    df.to_csv(HERE / "grid4.csv", index=False)

    # ---------------- cost sensitivity of finalists ----------------
    finalists = {
        "P1 overnight band2 vol<.35": lab.build_weights(d, base="overnight", gate=g2, vol_max=0.35),
        "P2 morning30 band2 volpct<.95": lab.build_weights(d, base="morning", m=30, gate=g2, vol_pct_max=0.95),
        "P3 morning30 band2 vol<.35 stop4": lab.build_weights(d, base="morning", m=30, gate=g2, vol_max=0.35, stop=0.04),
        "H1 signal30 band2 vol<.35 stop4": lab.build_weights(d, base="signal", m=30, gate=g2, vol_max=0.35, stop=0.04),
        "H2 signal60 band2 vol<.35 stop4": lab.build_weights(d, base="signal", m=60, gate=g2, vol_max=0.35, stop=0.04),
    }
    print("\n== cost sensitivity ==")
    for name, w in finalists.items():
        add(name, w, costs=(1.0, 5.0, 10.0), verbose=False)
    df2 = pd.DataFrame(rows[-len(finalists):])
    print(df2[["name", "10y_1_c", "10y_1_d", "10y_5_c", "10y_5_d", "10y_10_c", "10y_10_d",
               "5y_1_c", "5y_1_d", "5y_5_c", "5y_5_d", "5y_10_c", "5y_10_d"]]
          .to_string(index=False, float_format=lambda x: f"{x:6.2f}"))
    df2.to_csv(HERE / "finalists.csv", index=False)


if __name__ == "__main__":
    main()
