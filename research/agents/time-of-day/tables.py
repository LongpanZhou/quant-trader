"""Produce the final numbers for report.md (markdown tables)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402

import bt  # noqa: E402

BPY = 252 * 390
B = {"10y": (0.3928, 0.8168), "5y": (0.1347, 0.8168)}
DB = {"10y": (0.4531, 0.5871), "5y": (0.3461, 0.3686)}


def row(name, w, ts, op, cl, slip):
    out = []
    for tag, lo, hi in S.WINDOWS:
        res, s, b = S.evaluate(w, ts, op, cl, lo, slip)
        eq = pd.Series(res["equity"], index=res["ts"])
        dr = eq.groupby(eq.index.date).last().pct_change().dropna()
        out.append((s, b, dr))
    return out


def main():
    ts, op, cl = S.load_panel()
    df = pd.DataFrame({"date": ts.date, "minute": ts.hour * 60 + ts.minute})
    dcl = S.daily_close(ts, cl[:, 0])
    dates = pd.DatetimeIndex(sorted(set(ts.date)))
    reg0 = S.regime_band(dcl, 165, 1, 0.0)
    reg2 = S.regime_band(dcl, 165, 1, 0.02)
    tom31 = S.tom_flags(dates, 3, 1)

    V = {
        "V1 min overnight 09:31": S.build_weights(df, reg2, 571, "cash"),
        "V2 overnight+first30 10:01": S.build_weights(df, reg2, 601, "cash"),
        "V3 V2+TOM(3+1)": S.build_weights_tom(df, reg2, 601, tom31),
        "V4 24h reference band2": S.build_weights_24h(ts, reg2, "cash"),
        "V1b overnight 09:31 band0": S.build_weights(df, reg0, 571, "cash"),
        "V2b overnight 10:01 band0": S.build_weights(df, reg0, 601, "cash"),
    }
    print("| variant | cost | 10y CAGR | 10y DD | 10y Sharpe(d) | 5y CAGR | 5y DD | "
          "5y Sharpe(d) | fills 10y | turnover 10y | pass |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for name, w in V.items():
        for slip in (0.0, 1.0, 2.0, 3.0, 5.0):
            r = row(name, w, ts, op, cl, slip)
            (s10, b10, d10), (s5, b5, d5) = r
            ok = (s10["cagr"] > B["10y"][0] and s10["max_drawdown"] < B["10y"][1]
                  and s5["cagr"] > B["5y"][0] and s5["max_drawdown"] < B["5y"][1])
            print(f"| {name} | {slip:.0f}bp | {s10['cagr']*100:.2f}% | "
                  f"{s10['max_drawdown']*100:.2f}% | {d10.mean()/d10.std()*np.sqrt(252):.2f} | "
                  f"{s5['cagr']*100:.2f}% | {s5['max_drawdown']*100:.2f}% | "
                  f"{d5.mean()/d5.std()*np.sqrt(252):.2f} | {s10['fills']} | "
                  f"{s10['turnover']:,.0f}x | {'PASS' if ok else 'fail'} |")

    print("\n### extra detail at 1bp")
    for name, w in V.items():
        r = row(name, w, ts, op, cl, 1.0)
        for (tag, (s, b, dr)) in zip(("10y", "5y"), r):
            print(f"{name:28s} {tag}: CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%"
                  f"  sh_min {s['sharpe']:4.2f}  sh_day {dr.mean()/dr.std()*np.sqrt(252):4.2f}"
                  f"  sortino {s['sortino']:4.2f}  vol {s['volatility']*100:5.2f}%"
                  f"  expo_bars {s['exposure']*100:5.1f}%  end ${s['ending_equity']:,.0f}"
                  f"  | tqqq {b['cagr']*100:5.2f}%/{b['max_drawdown']*100:5.2f}%")

    print("\n### yearly V2 vs V3 vs tqqq (1bp)")
    y = {}
    for name in ("V2 overnight+first30 10:01", "V3 V2+TOM(3+1)", "V4 24h reference band2"):
        res = bt.run(ts, op, cl, V[name], "2017-01-03", band=0.02, slippage_bps=1.0)
        y[name] = bt.yearly(res["ts"], res["equity"],
                            cl[bt.start_index(ts, "2017-01-03"):, 1])
    ks = list(y["V2 overnight+first30 10:01"].keys())
    print("| year | V2 | V3 | V4 | TQQQ | rocks |")
    print("|---|---|---|---|---|---|")
    for k in ks:
        v2 = y["V2 overnight+first30 10:01"][k]["strategy"]
        v3 = y["V3 V2+TOM(3+1)"][k]["strategy"]
        v4 = y["V4 24h reference band2"][k]["strategy"]
        bt_ = y["V2 overnight+first30 10:01"][k]["benchmark"]
        print(f"| {k} | {v2*100:+.1f}% | {v3*100:+.1f}% | {v4*100:+.1f}% | {bt_*100:+.1f}% | "
              f"{'W' if v2 > bt_ else 'L'} |")


if __name__ == "__main__":
    main()
