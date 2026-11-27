"""Pull the report tables out of result.json plus a few extra diagnostics."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

pd.set_option("display.width", 240)


def main():
    d = json.load(open(HERE / "result.json"))
    R = d["primary"]["metrics"]
    V = d["variants"]

    print("=== headline (costs) ===")
    rows = []
    for name, src in (("R_primary", R), ("R0_thr0_band0", V["R0_thr0_band0"]),
                      ("P2_morning30", V["P2_morning30"]), ("P1_overnight", V["P1_overnight"]),
                      ("winner", V["winner_ref"]), ("ctrl_regime_only", V["ctrl_regime_only"])):
        for tag in ("10y", "5y"):
            r = {"name": name, "window": tag}
            for k in ("0bp", "1bp", "5bp", "10bp"):
                c = src[tag]["costs"][k]
                r[f"cagr_{k}"] = c["cagr"] * 100
                r[f"dd_{k}"] = c["max_drawdown"] * 100
            r["sharpe_1bp"] = src[tag]["costs"]["1bp"]["sharpe"]
            r["fills_1bp"] = src[tag]["costs"]["1bp"]["fills"]
            rows.append(r)
    df = pd.DataFrame(rows)
    print(df.to_string(index=False, float_format=lambda x: f"{x:6.2f}"))

    print("\n=== yearly, primary vs winner vs TQQQ (1bp) ===")
    yp = R["10y"]["costs"]["1bp"]["yearly"]
    yw = V["winner_ref"]["10y"]["costs"]["1bp"]["yearly"]
    rows = []
    for y in sorted(yp):
        rows.append({"year": y, "R": yp[y]["strategy"] * 100, "winner": yw[y]["strategy"] * 100,
                     "TQQQ": yp[y]["benchmark"] * 100})
    print(pd.DataFrame(rows).to_string(index=False, float_format=lambda x: f"{x:7.2f}"))

    print("\n=== 5y yearly ===")
    yp = R["5y"]["costs"]["1bp"]["yearly"]
    yw = V["winner_ref"]["5y"]["costs"]["1bp"]["yearly"]
    rows = [{"year": y, "R": yp[y]["strategy"] * 100, "winner": yw[y]["strategy"] * 100,
             "TQQQ": yp[y]["benchmark"] * 100} for y in sorted(yp)]
    print(pd.DataFrame(rows).to_string(index=False, float_format=lambda x: f"{x:7.2f}"))

    print("\n=== rolling 3y summary ===")
    for name, src in (("R_primary", R), ("winner", V["winner_ref"]), ("P2", V["P2_morning30"]),
                      ("P1", V["P1_overnight"])):
        for tag in ("10y", "5y"):
            rr = src[tag]["costs"]["1bp"]["rolling3y"]
            n = len(rr)
            print(f"  {name:10s} {tag}: n={n:2d}  cagr {min(x['cagr'] for x in rr)*100:6.1f}"
                  f"..{max(x['cagr'] for x in rr)*100:6.1f}  maxdd {max(x['dd'] for x in rr)*100:5.1f}  "
                  f"beatB&Hcagr {sum(x['cagr']>x['bench_cagr'] for x in rr):2d}/{n}  "
                  f"lowerDD {sum(x['dd']<x['bench_dd'] for x in rr):2d}/{n}")

    h = d["rolling3y_primary_vs_winner"]
    print(f"  primary vs winner: cagr wins {sum(x['primary_beats_winner_cagr'] for x in h)}/{len(h)}, "
          f"dd wins {sum(x['primary_lower_dd'] for x in h)}/{len(h)}, "
          f"both {sum(x['primary_beats_winner_cagr'] and x['primary_lower_dd'] for x in h)}/{len(h)}")
    print("  worst windows for primary vs winner:")
    for x in sorted(h, key=lambda z: z["primary_cagr"] - z["winner_cagr"])[:5]:
        print(f"    {x['start']}  R {x['primary_cagr']*100:6.1f}%/{x['primary_dd']*100:5.1f}%  "
              f"W {x['winner_cagr']*100:6.1f}%/{x['winner_dd']*100:5.1f}%")

    print("\n=== sub-periods (1bp) ===")
    ts, o, hh, lo, c, v = lab.load_panel()
    dd = lab.Days(ts, o, c)
    g2 = dd.gate(band=0.02)
    import check_sim as cs
    wR = lab.build_weights(dd, base="signal", m=60, gate=g2, vol_max=0.35, stop=0.04, signal_thr=-0.005)
    wW = cs.winner_weights(ts, o, c)
    for a, b in (("2017-01-03", "2019-12-31"), ("2020-01-01", "2022-12-31"),
                 ("2023-01-01", "2026-10-23"), ("2017-01-03", "2021-10-22"),
                 ("2021-10-25", "2026-10-23")):
        out = []
        for nm, w in (("R", wR), ("W", wW)):
            r = lab.run_window(ts, o, c, w, a, band=0.02, slippage_bps=1.0)
            # cut at b
            j = np.searchsorted(ts, pd.Timestamp(b, tz="America/New_York"), side="right")
            ii = lab.bt.start_index(ts, a)
            eq = r["equity"][: max(j - ii, 2)]
            yrs = (ts[ii + len(eq) - 1] - ts[ii]).total_seconds() / (365.25 * 86400)
            cagr = (eq[-1] / eq[0]) ** (1 / yrs) - 1
            peak = np.maximum.accumulate(eq)
            out.append(f"{nm} {cagr*100:6.1f}%/{(-(eq/peak-1).min())*100:5.1f}%")
        print(f"  {a}..{b}: " + "   ".join(out))

    print("\n=== gross vs net (10y / 5y) ===")
    for nm, src in (("R", R), ("P2", V["P2_morning30"]), ("P1", V["P1_overnight"])):
        print(f"  {nm}: " + "  ".join(
            f"{tag} 0bp {src[tag]['costs']['0bp']['cagr']*100:6.2f} 1bp {src[tag]['costs']['1bp']['cagr']*100:6.2f} "
            f"5bp {src[tag]['costs']['5bp']['cagr']*100:6.2f} 10bp {src[tag]['costs']['10bp']['cagr']*100:6.2f}"
            for tag in ("10y", "5y")))


if __name__ == "__main__":
    main()
