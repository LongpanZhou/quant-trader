"""Grid 3: crash-filtered family variants + cost sensitivity of the leaders."""
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
    return f"{str(ts[i])[:10]}..{str(ts[j])[:10]}"


def main():
    t0 = time.time()
    ts, o, h, lo, c, v = lab.load_panel()
    d = lab.Days(ts, o, c)
    g0 = d.gate(band=0.0)
    g2 = d.gate(band=0.02)
    ma20 = d.ma(20)
    gm20 = np.r_[False, d.dclose[:-1, 0] > ma20[:-1]]
    rows = []

    def add(name, w, costs=(1.0,)):
        rec = {"name": name}
        for start, tag in ((lab.START10, "10y"), (lab.START5, "5y")):
            for slip in costs:
                r = lab.run_window(ts, o, c, w, start, band=0.02, slippage_bps=slip)
                s = lab.stats(r)
                rec[f"{tag}_{slip:.0f}bp_cagr"] = s["cagr"] * 100
                rec[f"{tag}_{slip:.0f}bp_dd"] = s["max_drawdown"] * 100
                rec[f"{tag}_{slip:.0f}bp_sh"] = s["sharpe"]
                if slip == 1.0:
                    rec[f"{tag}_ddwin"] = dd_window(ts[lab.bt.start_index(ts, start):], r["equity"])
                    rec[f"{tag}_fills"] = s["fills"]
        rows.append(rec)
        print(f"  {name:44s} " + "  ".join(
            f"{t} {rec[f'{t}_1bp_cagr']:6.2f}/{rec[f'{t}_1bp_dd']:5.2f}" for t in ("10y", "5y"))
            + f" [{time.time()-t0:4.0f}s]")

    print("== pure overnight: best crash filter ==")
    add("overnight band2 vol<0.35", lab.build_weights(d, base="overnight", gate=g2, vol_max=0.35))
    add("overnight band2 vol<0.30", lab.build_weights(d, base="overnight", gate=g2, vol_max=0.30))
    add("overnight band2 volpct<0.95",
        lab.build_weights(d, base="overnight", gate=g2, vol_pct_max=0.95))
    add("overnight band2 vol<0.35 & ma20",
        lab.build_weights(d, base="overnight", gate=g2 & gm20, vol_max=0.35))

    print("== first 30m ==")
    add("morning30 band2 vol<0.35", lab.build_weights(d, base="morning", m=30, gate=g2, vol_max=0.35))
    add("morning30 band2 vol<0.35 stop4",
        lab.build_weights(d, base="morning", m=30, gate=g2, vol_max=0.35, stop=0.04))
    add("morning30 band2 vol<0.35 stop4 arm20",
        lab.build_weights(d, base="morning", m=30, gate=g2, vol_max=0.35, stop=0.04, stop_arm_ma20=True))
    add("morning30 band2 vol<0.30 stop4 arm20",
        lab.build_weights(d, base="morning", m=30, gate=g2, vol_max=0.30, stop=0.04, stop_arm_ma20=True))
    add("morning30 band2 volpct<0.95",
        lab.build_weights(d, base="morning", m=30, gate=g2, vol_pct_max=0.95))

    print("== first hour ==")
    add("morning60 band2 vol<0.35", lab.build_weights(d, base="morning", m=60, gate=g2, vol_max=0.35))
    add("morning60 band2 vol<0.35 stop4",
        lab.build_weights(d, base="morning", m=60, gate=g2, vol_max=0.35, stop=0.04))

    print("== overnight + first30 + conditional afternoon (hybrid) ==")
    add("signal30 band2", lab.build_weights(d, base="signal", m=30, gate=g2))
    add("signal30 band2 vol<0.35", lab.build_weights(d, base="signal", m=30, gate=g2, vol_max=0.35))
    add("signal30 band2 vol<0.35 stop4",
        lab.build_weights(d, base="signal", m=30, gate=g2, vol_max=0.35, stop=0.04))
    add("signal30 band2 vol<0.35 stop4 arm20",
        lab.build_weights(d, base="signal", m=30, gate=g2, vol_max=0.35, stop=0.04, stop_arm_ma20=True))
    add("signal60 band2 vol<0.35", lab.build_weights(d, base="signal", m=60, gate=g2, vol_max=0.35))

    df = pd.DataFrame(rows)
    print("\n" + df.to_string(index=False, float_format=lambda x: f"{x:6.2f}"))
    df.to_csv(HERE / "grid3.csv", index=False)


if __name__ == "__main__":
    main()
