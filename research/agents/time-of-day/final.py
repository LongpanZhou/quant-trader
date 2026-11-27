"""Final grid + result.json for the time-of-day agent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402

import bt  # noqa: E402

BPY = 252 * 390


def slice_stats(ts, eq, cash, lo, hi, bench):
    i = int(ts.searchsorted(pd.Timestamp(lo, tz="America/New_York")))
    j = int(ts.searchsorted(pd.Timestamp(hi, tz="America/New_York"))) + 1
    e = eq[i:j]
    c = cash[i:j]
    t = ts[i:j]
    b = bench[i:j]
    r = np.diff(e) / e[:-1]
    yrs = (t[-1] - t[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(e)
    peakb = np.maximum.accumulate(b)
    dn = np.minimum(r, 0)
    return {
        "cagr": float((e[-1] / e[0]) ** (1 / yrs) - 1),
        "max_drawdown": float(-(e / peak - 1).min()),
        "sharpe": float(np.mean(r) / np.std(r) * np.sqrt(BPY)) if np.std(r) > 0 else 0.0,
        "sortino": float(np.mean(r) / np.sqrt(np.mean(dn ** 2)) * np.sqrt(BPY))
        if np.mean(dn ** 2) > 0 else 0.0,
        "volatility": float(np.std(r) * np.sqrt(BPY)),
        "exposure": float(np.mean((e - c) / e)),
        "bench_cagr": float((b[-1] / b[0]) ** (1 / yrs) - 1),
        "bench_max_drawdown": float(-(b / peakb - 1).min()),
        "daily_sharpe": _daily_sharpe(t, e),
        "years": float(yrs),
    }


def _daily_sharpe(t, e):
    s = pd.Series(e, index=t)
    d = s.groupby(s.index.date).last().pct_change().dropna()
    return float(d.mean() / d.std() * np.sqrt(252)) if len(d) > 2 and d.std() > 0 else 0.0


def main():
    ts, op, cl = S.load_panel()
    df = pd.DataFrame({"date": ts.date, "minute": ts.hour * 60 + ts.minute})
    dcl = S.daily_close(ts, cl[:, 0])
    dates = pd.DatetimeIndex(sorted(set(ts.date)))
    bench_all = cl[:, 1]

    regs = {f"b{int(p*100)}": S.regime_band(dcl, 165, 1, p)
            for p in (0.0, 0.01, 0.02, 0.03, 0.05)}
    toms = {"none": None,
            "tom31": S.tom_flags(dates, 3, 1),
            "tom32": S.tom_flags(dates, 3, 2),
            "tom53": S.tom_flags(dates, 5, 3)}

    specs = []
    for bkey in ("b0", "b1", "b2", "b3", "b5"):
        for em, etag in ((571, "0931"), (601, "1001")):
            specs.append((f"ON_{etag}_{bkey}", regs[bkey], em, None))
    specs += [
        ("ON_1031_b2", regs["b2"], 631, None),
        ("ON_1001_b2_TOM31", regs["b2"], 601, toms["tom31"]),
        ("ON_1001_b2_TOM32", regs["b2"], 601, toms["tom32"]),
        ("ON_1001_b2_TOM53", regs["b2"], 601, toms["tom53"]),
        ("ON_0931_b2_TOM31", regs["b2"], 571, toms["tom31"]),
    ]

    rows = {}
    for name, reg, em, tom in specs:
        w = (S.build_weights_tom(df, reg, em, tom) if tom is not None
             else S.build_weights(df, reg, em, "cash"))
        rec = {"params": {"sma": 165, "band": float(name.split("_")[-1][1:]) / 100
                          if name.split("_")[-1][0] == "b" else None,
                          "exit_min": em, "tom": name.split("TOM")[1] if "TOM" in name else None}}
        for slip in (1.0, 5.0):
            res = bt.run(ts, op, cl, w, "2017-01-03", band=0.02, slippage_bps=slip)
            eq, cash = res["equity"], res["cash"]
            s10 = bt.stats(res, BPY)
            for tag, lo, hi in S.WINDOWS:
                st = slice_stats(res["ts"], eq, cash, lo, hi,
                                 bench_all[bt.start_index(ts, lo):][:len(eq)])
                st["fills"] = s10["fills"] if tag == "10y" else None
                st["turnover"] = s10["turnover"] if tag == "10y" else None
                st["pass"] = bool(st["cagr"] > S.BENCH[tag]["cagr"]
                                  and st["max_drawdown"] < S.BENCH[tag]["max_drawdown"])
                rec[f"{tag}_{int(slip)}bp"] = st
            if slip == 1.0:
                rec["fills_10y"] = s10["fills"]
                rec["turnover_10y"] = s10["turnover"]
                rec["ending_equity_10y"] = s10["ending_equity"]
        rows[name] = rec

    # print table
    print(f"{'variant':22s} {'10y CAGR':>9s} {'DD':>7s} {'dSh':>5s} {'5y CAGR':>9s} "
          f"{'DD':>7s} {'dSh':>5s} {'fills':>6s} {'pass':>5s}")
    for name, rec in rows.items():
        a, b = rec["10y_1bp"], rec["5y_1bp"]
        print(f"{name:22s} {a['cagr']*100:8.2f}% {a['max_drawdown']*100:6.2f}% "
              f"{a['daily_sharpe']:5.2f} {b['cagr']*100:8.2f}% {b['max_drawdown']*100:6.2f}% "
              f"{b['daily_sharpe']:5.2f} {rec['fills_10y']:6d} "
              f"{'PASS' if a['pass'] and b['pass'] else 'fail':>5s}")

    print("\n5bp:")
    for name, rec in rows.items():
        a, b = rec["10y_5bp"], rec["5y_5bp"]
        print(f"{name:22s} {a['cagr']*100:8.2f}% {a['max_drawdown']*100:6.2f}% | "
              f"{b['cagr']*100:8.2f}% {b['max_drawdown']*100:6.2f}% | "
              f"{'PASS' if a['pass'] and b['pass'] else 'fail'}")

    # yearly for the headline variants
    yearly = {}
    for name in ("ON_1001_b2", "ON_0931_b2", "ON_1001_b2_TOM31", "ON_0931_b2_TOM31",
                 "ON_0931_b2_TOM53"):
        tom = toms[name.split("TOM")[1].replace("31", "tom31").replace("53", "tom53")] \
            if "TOM31" in name else (toms["tom53"] if "TOM53" in name else None)
        em = 571 if "_0931" in name else 601
        w = (S.build_weights_tom(df, regs["b2"], em, tom) if tom is not None
             else S.build_weights(df, regs["b2"], em, "cash"))
        res = bt.run(ts, op, cl, w, "2017-01-03", band=0.02, slippage_bps=1.0)
        yearly[name] = bt.yearly(res["ts"], res["equity"],
                                 cl[bt.start_index(ts, "2017-01-03"):, 1])
    print("\nYearly (1bp):")
    years = list(yearly["ON_1001_b2"].keys())
    hdr = "  ".join(f"{n.replace('ON_', ''):>15s}" for n in yearly)
    print(f"{'year':>6s}  {hdr}  {'tqqq':>9s}")
    for y in years:
        line = "  ".join(f"{yearly[n][y]['strategy']*100:14.1f}%" for n in yearly)
        print(f"{y:>6d}  {line}  {yearly['ON_1001_b2'][y]['benchmark']*100:8.1f}%")

    # walk-forward: rank the (exit, band) grid on 2017-2021, report 2022-2026
    print("\nWalk-forward: pick best on 2017-2021, show 2022-2026")
    wf = []
    for name, rec in rows.items():
        if "TOM" in name or name == "ON_1031_b2":
            continue
        w = (S.build_weights(df, regs[name.split("_")[-1]], 571 if "_0931" in name else 601,
                             "cash"))
        res = bt.run(ts, op, cl, w, "2017-01-03", band=0.02, slippage_bps=1.0)
        a = slice_stats(res["ts"], res["equity"], res["cash"], "2017-01-03", "2021-12-31",
                        bench_all[bt.start_index(ts, "2017-01-03"):][:len(res["equity"])])
        b = slice_stats(res["ts"], res["equity"], res["cash"], "2022-01-03", "2026-10-23",
                        bench_all[bt.start_index(ts, "2017-01-03"):][:len(res["equity"])])
        wf.append({"variant": name, "is_cagr": a["cagr"], "oos_cagr": b["cagr"],
                   "is_dd": a["max_drawdown"], "oos_dd": b["max_drawdown"]})
    wf = sorted(wf, key=lambda r: -r["is_cagr"])
    for r in wf:
        print(f"  {r['variant']:14s} 2017-21 {r['is_cagr']*100:6.2f}%/DD {r['is_dd']*100:5.1f}%"
              f"   -> 2022-26 {r['oos_cagr']*100:6.2f}%/DD {r['oos_dd']*100:5.1f}%")
    rk = pd.Series([r["is_cagr"] for r in wf]).rank()
    rk2 = pd.Series([r["oos_cagr"] for r in wf]).rank()
    print(f"  rank correlation IS vs OOS: {rk.corr(rk2):.2f}")

    out = {"meta": {"agent": "time-of-day",
                    "data": "local 1m QQQ/TQQQ/BIL adjusted, regular session, next-open fills",
                    "benchmark": S.BENCH, "daily_baseline": S.DAILY_BASELINE,
                    "note": "daily_sharpe is sampled once per day and is the "
                            "comparable figure; minute-bar Sharpe is inflated by "
                            "flat stretches"},
           "variants": rows,
           "walk_forward": wf,
           "yearly": {k: {str(y): {"strategy": v["strategy"], "tqqq": v["benchmark"]}
                          for y, v in d.items()} for k, d in yearly.items()}}
    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("\nwrote result.json")


if __name__ == "__main__":
    main()
