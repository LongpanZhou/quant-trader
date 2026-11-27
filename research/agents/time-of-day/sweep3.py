"""Sweep 3: TOM overlay robustness, 5bp sensitivity, band/SMA grid, months."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402
from sweep2 import tom_flags, build_weights_tom, regime_band  # noqa: E402

import bt  # noqa: E402


def run(w, ts, op, cl, slip):
    out = S.run_all(w, ts, op, cl, slip)
    p = S.passes(out)
    s10, s5 = out["10y"]["stats"], out["5y"]["stats"]
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

    print("=" * 130)
    print("A. TOM width, 1bp vs 5bp (SMA165 lag1, exit 10:01, cash)")
    for nb, ne in ((0, 0), (3, 2), (4, 2), (5, 3), (6, 3), (7, 4)):
        tom = tom_flags(dates, nb, ne) if (nb or ne) else None
        w = build_weights_tom(df, reg1, 601, tom)
        print(f"  TOM {nb}+{ne}: 1bp {run(w, ts, op, cl, 1.0)}")
        print(f"  TOM {nb}+{ne}: 5bp {run(w, ts, op, cl, 5.0)}")

    print("=" * 130)
    print("B. TOM(5,3) + hysteresis band on the SMA")
    for b in (0.0, 0.01, 0.02, 0.03, 0.05):
        reg = regime_band(dcl, 165, 1, b)
        w = build_weights_tom(df, reg, 601, tom_flags(dates, 5, 3))
        print(f"  band {b:.2f}: 1bp {run(w, ts, op, cl, 1.0)}")
        print(f"  band {b:.2f}: 5bp {run(w, ts, op, cl, 5.0)}")

    print("=" * 130)
    print("C. TOM(5,3) + band0.02, SMA length")
    for n in (100, 125, 150, 165, 200, 250):
        reg = regime_band(dcl, n, 1, 0.02)
        w = build_weights_tom(df, reg, 601, tom_flags(dates, 5, 3))
        print(f"  SMA{n:3d}: 1bp {run(w, ts, op, cl, 1.0)}")

    print("=" * 130)
    print("D. regime lag 0 vs 1 for the TOM(5,3)+band0.02 variant")
    for lag in (0, 1, 2):
        reg = regime_band(dcl, 165, lag, 0.02)
        w = build_weights_tom(df, reg, 601, tom_flags(dates, 5, 3))
        print(f"  lag{lag}: 1bp {run(w, ts, op, cl, 1.0)}")

    print("=" * 130)
    print("E. month / season filters stacked on TOM(5,3)+band0.02")
    reg = regime_band(dcl, 165, 1, 0.02)
    months = pd.DatetimeIndex(sorted(set(ts.date))).month
    for avoid in ((), (9,), (8, 9), (9, 10)):
        m = np.isin(pd.DatetimeIndex(ts.date).month, avoid)
        live = ~m
        w = S.build_weights(df, reg, 601, "cash", live_filter=live)
        # note: this drops TOM-24h too; approximate check only
        print(f"  avoid {avoid}: 1bp {run(w, ts, op, cl, 1.0)}")


if __name__ == "__main__":
    main()
