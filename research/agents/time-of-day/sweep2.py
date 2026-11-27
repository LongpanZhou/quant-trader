"""Sweep 2 (re-run with corrected TOM semantics)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402


def line(out):
    s10, s5 = out["10y"]["stats"], out["5y"]["stats"]
    p = S.passes(out)
    return (f"10y {s10['cagr']*100:6.2f}%/{s10['max_drawdown']*100:5.2f}% "
            f"sh {s10['sharpe']:4.2f} f{s10['fills']:5d} | "
            f"5y {s5['cagr']*100:6.2f}%/{s5['max_drawdown']*100:5.2f}% "
            f"sh {s5['sharpe']:4.2f} f{s5['fills']:5d} | {p['both']}")


def main():
    ts, op, cl = S.load_panel()
    df = pd.DataFrame({"date": ts.date, "minute": ts.hour * 60 + ts.minute})
    dcl = S.daily_close(ts, cl[:, 0])
    dates = pd.DatetimeIndex(sorted(set(ts.date)))
    reg1 = S.regime(dcl, 165, 1)
    regb = S.regime_band(dcl, 165, 1, 0.02)

    print("=" * 130)
    print("A. TOM width (corrected: TOM day = hold that day's session), 1bp")
    for nb, ne in ((0, 0), (3, 1), (2, 2), (3, 2), (4, 2), (5, 3), (6, 3), (7, 4)):
        tom = S.tom_flags(dates, nb, ne) if (nb or ne) else None
        w = S.build_weights_tom(df, reg1, 601, tom)
        print(f"  TOM {nb}+{ne} (band0): {line(S.run_all(w, ts, op, cl, 1.0))}")
        wb = S.build_weights_tom(df, regb, 601, tom)
        print(f"  TOM {nb}+{ne} (band2): {line(S.run_all(wb, ts, op, cl, 1.0))}")

    print("=" * 130)
    print("B. exit time, SMA length, regime lag (TOM 3+2 band0.02)")
    tom32 = S.tom_flags(dates, 3, 2)
    for em, tag in ((571, "09:31"), (601, "10:01"), (631, "10:31"), (661, "11:01")):
        w = S.build_weights_tom(df, regb, em, tom32)
        print(f"  exit {tag}: {line(S.run_all(w, ts, op, cl, 1.0))}")
    for n in (100, 125, 150, 165, 200, 250):
        r = S.regime_band(dcl, n, 1, 0.02)
        w = S.build_weights_tom(df, r, 601, tom32)
        print(f"  SMA{n:3d}: {line(S.run_all(w, ts, op, cl, 1.0))}")
    for lag in (0, 1, 2):
        r = S.regime_band(dcl, 165, lag, 0.02)
        w = S.build_weights_tom(df, r, 601, tom32)
        print(f"  lag{lag}: {line(S.run_all(w, ts, op, cl, 1.0))}")


if __name__ == "__main__":
    main()
