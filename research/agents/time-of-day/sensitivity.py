"""Consolidated sensitivity tables for the final report."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402

BPY = 252 * 390


def main():
    ts, op, cl = S.load_panel()
    df = pd.DataFrame({"date": ts.date, "minute": ts.hour * 60 + ts.minute})
    dcl = S.daily_close(ts, cl[:, 0])
    dates = pd.DatetimeIndex(sorted(set(ts.date)))

    def show(tag, w):
        o = S.run_all(w, ts, op, cl, 1.0)
        a, b = o["10y"]["stats"], o["5y"]["stats"]
        ok = S.passes(o)["both"]
        print(f"| {tag} | {a['cagr']*100:.2f}% | {a['max_drawdown']*100:.2f}% | "
              f"{b['cagr']*100:.2f}% | {b['max_drawdown']*100:.2f}% | "
              f"{'PASS' if ok else 'fail'} |")

    print("### SMA length (overnight 15:59->10:01, band 2%)")
    print("| SMA | 10y CAGR | 10y DD | 5y CAGR | 5y DD | pass |")
    print("|---|---|---|---|---|---|")
    for n in (100, 125, 150, 165, 200, 250):
        show(f"SMA{n}", S.build_weights(df, S.regime_band(dcl, n, 1, 0.02), 601, "cash"))

    print("\n### band (SMA165, 15:59->10:01)")
    print("| band | 10y CAGR | 10y DD | 5y CAGR | 5y DD | pass |")
    print("|---|---|---|---|---|---|")
    for p in (0.0, 0.01, 0.02, 0.03, 0.05):
        show(f"band {p*100:.0f}%", S.build_weights(df, S.regime_band(dcl, 165, 1, p), 601, "cash"))

    print("\n### exit time (SMA165, band 2%)")
    print("| exit | 10y CAGR | 10y DD | 5y CAGR | 5y DD | pass |")
    print("|---|---|---|---|---|---|")
    for em, tag in ((571, "09:31"), (601, "10:01"), (631, "10:31"), (661, "11:01"),
                    (691, "11:31"), (721, "12:01")):
        show(tag, S.build_weights(df, S.regime_band(dcl, 165, 1, 0.02), em, "cash"))

    print("\n### regime lag (SMA165, band 2%, exit 10:01)")
    print("| lag | 10y CAGR | 10y DD | 5y CAGR | 5y DD | pass |")
    print("|---|---|---|---|---|---|")
    for lag in (0, 1, 2, 3):
        show(f"lag {lag}", S.build_weights(df, S.regime_band(dcl, 165, lag, 0.02), 601, "cash"))

    print("\n### V3 TOM width (SMA165 band 2%, exit 10:01)")
    print("| TOM window | 10y CAGR | 10y DD | 5y CAGR | 5y DD | pass |")
    print("|---|---|---|---|---|---|")
    reg = S.regime_band(dcl, 165, 1, 0.02)
    for nb, ne in ((0, 0), (1, 2), (2, 2), (3, 1), (3, 2), (4, 2), (5, 3), (6, 3), (7, 4)):
        t = S.tom_flags(dates, nb, ne) if (nb or ne) else None
        w = (S.build_weights_tom(df, reg, 601, t) if t is not None
             else S.build_weights(df, reg, 601, "cash"))
        show(f"first {nb} + last {ne}", w)

    print("\n### V2 sub-periods (1bp)")
    w = S.build_weights(df, S.regime_band(dcl, 165, 1, 0.02), 601, "cash")
    import bt
    res = bt.run(ts, op, cl, w, "2017-01-03", band=0.02, slippage_bps=1.0)
    for lo, hi in (("2017-01-03", "2021-12-31"), ("2022-01-03", "2026-10-23")):
        i = bt.start_index(ts, lo)
        j = bt.start_index(ts, hi)
        e = res["equity"][i:j + 1]
        yrs = (res["ts"][j] - res["ts"][i]).total_seconds() / (365.25 * 86400)
        print(f"  {lo}..{hi}: CAGR {((e[-1]/e[0])**(1/yrs)-1)*100:.2f}%  "
              f"DD {-(e/np.maximum.accumulate(e)-1).min()*100:.2f}%")


if __name__ == "__main__":
    main()
