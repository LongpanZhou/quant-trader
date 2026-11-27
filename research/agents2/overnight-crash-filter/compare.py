"""Compare finalists: yearly returns, rolling 3y, DD windows."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402
import check_sim as cs  # noqa: E402

pd.set_option("display.width", 260)


def main():
    ts, o, h, lo, c, v = lab.load_panel()
    d = lab.Days(ts, o, c)
    g2 = d.gate(band=0.02)
    g0 = d.gate(band=0.0)
    i10 = lab.bt.start_index(ts, lab.START10)
    i5 = lab.bt.start_index(ts, lab.START5)

    variants = {
        "winner": cs.winner_weights(ts, o, c),
        "P1_overnight_vol": lab.build_weights(d, base="overnight", gate=g2, vol_max=0.35),
        "P2_morning30_volpct": lab.build_weights(d, base="morning", m=30, gate=g2, vol_pct_max=0.95),
        "H1_signal30_stop": lab.build_weights(d, base="signal", m=30, gate=g2, vol_max=0.35, stop=0.04),
        "H2_signal60_stop": lab.build_weights(d, base="signal", m=60, gate=g2, vol_max=0.35, stop=0.04),
        "E2_ref": lab.build_weights(d, base="signal", m=30, gate=g2),
    }

    print("=== yearly returns, 1bp ===")
    tab = {}
    for name, w in variants.items():
        r = lab.run_window(ts, o, c, w, lab.START10, band=0.02, slippage_bps=1.0)
        y = lab.yearly(ts[i10:], r["equity"], c[i10:, 1])
        tab[name] = {k: vv["strategy"] * 100 for k, vv in y.items()}
    tab["TQQQ"] = {k: vv["benchmark"] * 100 for k, vv in y.items()}
    df = pd.DataFrame(tab)
    print(df.to_string(float_format=lambda x: f"{x:7.1f}"))

    print("\n=== rolling 3y (quarterly starts) ===")
    for name, w in variants.items():
        for start, tag in ((lab.START10, "10y"), (lab.START5, "5y")):
            r = lab.run_window(ts, o, c, w, start, band=0.02, slippage_bps=1.0)
            i = lab.bt.start_index(ts, start)
            roll = lab.rolling3(ts[i:], r["equity"], c[i:, 1])
            n = len(roll)
            win_b = sum(1 for x in roll if x["cagr"] > x["bench_cagr"] and x["dd"] < x["bench_dd"])
            win_c = sum(1 for x in roll if x["cagr"] > x["bench_cagr"])
            dd_better = sum(1 for x in roll if x["dd"] < x["bench_dd"])
            print(f"  {name:22s} {tag}  n={n:2d}  beat B&H cagr {win_c:2d}/{n}  "
                  f"beat B&H both {win_b:2d}/{n}  lower DD {dd_better:2d}/{n}  "
                  f"min cagr {min(x['cagr'] for x in roll)*100:6.1f}%  "
                  f"max dd {max(x['dd'] for x in roll)*100:5.1f}%")

    print("\n=== DD windows and annualised vol, 1bp ===")
    for name, w in variants.items():
        for start, tag in ((lab.START10, "10y"), (lab.START5, "5y")):
            r = lab.run_window(ts, o, c, w, start, band=0.02, slippage_bps=1.0)
            s = lab.stats(r)
            i = lab.bt.start_index(ts, start)
            eq = r["equity"]
            peak = np.maximum.accumulate(eq)
            dd = eq / peak - 1
            j = int(np.argmin(dd)); p = int(np.argmax(eq[:j+1]))
            print(f"  {name:22s} {tag}  CAGR {s['cagr']*100:6.2f}  DD {s['max_drawdown']*100:5.2f} "
                  f"({str(ts[i+p])[:10]}..{str(ts[i+j])[:10]})  vol {s['volatility']*100:5.1f}  "
                  f"Sh {s['sharpe']:4.2f}  fills {s['fills']}")


if __name__ == "__main__":
    main()
