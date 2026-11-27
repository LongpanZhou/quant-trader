"""Detail for the recommended variant: ON 15:59->09:31, SMA165 band2, TOM(3+1)."""
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


def detail(w, ts, op, cl, slip):
    print(f"\n--- slippage {slip} bp ---")
    for tag, lo, hi in S.WINDOWS:
        res, s, b = S.evaluate(w, ts, op, cl, lo, slip)
        eq = pd.Series(res["equity"], index=res["ts"])
        deq = eq.groupby(eq.index.date).last()
        dr = deq.pct_change().dropna()
        peak = np.maximum.accumulate(eq.to_numpy())
        k = int(np.argmin(eq.to_numpy() / peak - 1))
        pk = int(np.argmax(eq.to_numpy()[:k + 1]))
        print(f"[{tag}] CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"sharpe(min) {s['sharpe']:4.2f}  sharpe(daily) {dr.mean()/dr.std()*np.sqrt(252):4.2f}  "
              f"sortino {s['sortino']:4.2f}  vol {s['volatility']*100:5.2f}%")
        print(f"      fills {s['fills']}  turnover {s['turnover']:,.0f}x  "
              f"exposure(bars) {s['exposure']*100:5.1f}%  end ${s['ending_equity']:,.0f}")
        print(f"      maxDD {res['ts'][pk].date()} -> {res['ts'][k].date()}")
        print(f"      bench CAGR {b['cagr']*100:6.2f}%  DD {b['max_drawdown']*100:5.2f}%")


def main():
    ts, op, cl = S.load_panel()
    df = pd.DataFrame({"date": ts.date, "minute": ts.hour * 60 + ts.minute})
    dcl = S.daily_close(ts, cl[:, 0])
    dates = pd.DatetimeIndex(sorted(set(ts.date)))

    reg = S.regime_band(dcl, 165, 1, 0.02)
    tom31 = S.tom_flags(dates, 3, 1)
    w = S.build_weights_tom(df, reg, 571, tom31)
    print("recommended: overnight 15:59->09:31, SMA165 band 2%, TOM last1+first3")
    for slip in (0.0, 1.0, 2.0, 3.0, 5.0):
        detail(w, ts, op, cl, slip)

    print("\nregime state stats")
    on = reg.reindex(dates).to_numpy()
    print(f"  on {on.sum()}/{len(on)} days ({on.mean()*100:.1f}%), "
          f"switches {int((np.diff(on.astype(int)) != 0).sum())}")
    # time in market: overnight blocks + TOM sessions
    overnight_days = int(on.sum())
    tom_days = sum(1 for d in dates if tom31.get(d.date(), False))
    per_day_hours = 16.5
    print(f"  overnight days {overnight_days}, TOM days {tom_days} "
          f"(+6.5h each) -> approx {overnight_days*per_day_hours/24:.0f} equivalent "
          f"full days of {len(dates)} ({overnight_days*per_day_hours/24/len(dates)*100:.0f}% of calendar time)")

    print("\nband sweep (exit 09:31, TOM 3+1)")
    for p in (0.0, 0.01, 0.02, 0.03, 0.05):
        r = S.regime_band(dcl, 165, 1, p)
        ww = S.build_weights_tom(df, r, 571, tom31)
        o = S.run_all(ww, ts, op, cl, 1.0)
        print(f"  band {p:.2f}: 10y {o['10y']['stats']['cagr']*100:6.2f}%/"
              f"{o['10y']['stats']['max_drawdown']*100:5.2f}% | 5y "
              f"{o['5y']['stats']['cagr']*100:6.2f}%/"
              f"{o['5y']['stats']['max_drawdown']*100:5.2f}% | "
              f"{S.passes(o)['both']}")

    print("\nTOM width sweep (exit 09:31, band 2%)")
    for nb, ne in ((0, 0), (1, 2), (2, 2), (3, 1), (3, 2), (4, 2), (5, 3), (6, 3), (7, 4)):
        t = S.tom_flags(dates, nb, ne) if (nb or ne) else None
        ww = (S.build_weights_tom(df, reg, 571, t) if t is not None
              else S.build_weights(df, reg, 571, "cash"))
        o = S.run_all(ww, ts, op, cl, 1.0)
        print(f"  {nb}+{ne}: 10y {o['10y']['stats']['cagr']*100:6.2f}%/"
              f"{o['10y']['stats']['max_drawdown']*100:5.2f}% | 5y "
              f"{o['5y']['stats']['cagr']*100:6.2f}%/"
              f"{o['5y']['stats']['max_drawdown']*100:5.2f}% | "
              f"{S.passes(o)['both']}")

    print("\nSMA length sweep (exit 09:31, band 2%, TOM 3+1)")
    for n in (100, 125, 150, 165, 200, 250):
        r = S.regime_band(dcl, n, 1, 0.02)
        ww = S.build_weights_tom(df, r, 571, tom31)
        o = S.run_all(ww, ts, op, cl, 1.0)
        print(f"  SMA{n:3d}: 10y {o['10y']['stats']['cagr']*100:6.2f}%/"
              f"{o['10y']['stats']['max_drawdown']*100:5.2f}% | 5y "
              f"{o['5y']['stats']['cagr']*100:6.2f}%/"
              f"{o['5y']['stats']['max_drawdown']*100:5.2f}% | {S.passes(o)['both']}")

    # BIL instead of cash
    print("\nBIL vs cash while out")
    wb = S.build_weights_tom(df, reg, 571, tom31, day_asset="bil")
    o = S.run_all(wb, ts, op, cl, 1.0)
    print(f"  BIL: 10y {o['10y']['stats']['cagr']*100:6.2f}%/"
          f"{o['10y']['stats']['max_drawdown']*100:5.2f}% | 5y "
          f"{o['5y']['stats']['cagr']*100:6.2f}%/"
          f"{o['5y']['stats']['max_drawdown']*100:5.2f}% | {S.passes(o)['both']}")


if __name__ == "__main__":
    main()
