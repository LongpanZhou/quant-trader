"""Twelfth pass: full diagnostics for the chosen centre (13:00 hysteresis)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BPY = 252 * 390
WINNERS = ["ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
           "fomc-opex-window", "family-session-timing", "family-short-reversal",
           "family-rebalance-flow", "family-intraday-microstructure-day",
           "family-ml-microstructure", "overnight-drift-filter"]


def load_all():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=60)
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])
    df = bt.load_1m("QQQ")
    df = df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts)
    vol = np.nan_to_num(df["volume"].to_numpy(dtype=float), nan=0.0)
    return ts, o, c, vol


def prep(ts, o, c, vol):
    dates, first, last = bt.day_bounds(ts)
    n = len(first)
    V = np.zeros((n, 390))
    for k in range(n):
        f, l = int(first[k]), int(last[k])
        m = min(l - f + 1, 390)
        V[k, :m] = vol[f:f + m]
    return dates, np.asarray(first), np.asarray(last), V


def main():
    ts, o, c, vol = load_all()
    dates, first, last, V = prep(ts, o, c, vol)
    n = len(first)
    o = np.asarray(o, float); c = np.asarray(c, float)
    j = 210

    acc = np.full(n, np.nan)
    for k in range(20, n):
        m = min(int(last[k]) - int(first[k]) + 1, 390)
        if j >= m - 1:
            continue
        w0 = j - 29
        hist = [V[kk, w0:j + 1].sum() for kk in range(k - 20, k)]
        med = np.median(hist)
        if med > 0:
            acc[k] = V[k, w0:j + 1].sum() / med

    def build(enter=0.75, exit_=0.85, jj=210, use_bil=True):
        w = np.zeros((len(ts), 3))
        state = 0
        for k in range(n - 1):
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            if jj >= m - 1:
                continue
            if not np.isfinite(acc[k]):
                state = 0
                continue
            if state == 0 and acc[k] < enter:
                state = 1
            elif state == 1 and acc[k] > exit_:
                state = 0
            if state:
                fk, lk = int(first[k]), int(last[k])
                w[fk + jj, 1] = 1.0
                w[fk + jj + 1:lk + 1, 1] = 1.0
                w[lk, 1] = 0.0
            elif use_bil:
                pass  # cash, not BIL, for the headline; BIL variant below
        w[-1] = w[-2]
        return w

    w = build()
    print(f"TQQQ bars {np.mean(w[:,1]>0)*100:.2f}%  max row sum {w.sum(1).max():.3f}")
    for slip in (1.0, 5.0, 10.0):
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=slip)
        s = bt.stats(r, BPY)
        print(f"{slip:.0f}bp CAGR {s['cagr']*100:6.2f}% DD {s['max_drawdown']*100:5.2f}% "
              f"Sharpe {s['sharpe']:.3f} Sortino {s['sortino']:.3f} vol {s['volatility']*100:.2f}% "
              f"expo {s['exposure']*100:.1f}% fills {s['fills']} turnover {s['turnover']:.0f} "
              f"end ${s['ending_equity']:,.0f}")
        if slip == 1.0:
            r1 = r; s1 = s

    # daily metrics
    eq = pd.Series(r1["equity"], index=pd.to_datetime(r1["ts"]))
    daily = eq.groupby(eq.index.normalize()).last()
    dr = daily.pct_change().dropna()
    peak = np.maximum.accumulate(daily.to_numpy())
    print(f"daily-close: CAGR {((daily.iloc[-1]/daily.iloc[0])**(252/len(daily))-1)*100:.2f}% "
          f"DD {(-(daily.to_numpy()/peak-1).min())*100:.2f}% "
          f"Sharpe {dr.mean()/dr.std(ddof=0)*np.sqrt(252):.3f}")

    # fills log / holding period
    rlog = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=1.0, fill_log=True)
    log = rlog["fills_log"]
    print(f"fill log {len(log)} fills")
    buys = [x for x in log if x["side"] == "buy"]
    sells = [x for x in log if x["side"] == "sell"]
    print(f"buys {len(buys)} sells {len(sells)}")
    # pair sequentially
    holds = []
    bi = 0
    for s in sells:
        if bi < len(buys) and buys[bi]["ts"] <= s["ts"]:
            holds.append((s["ts"] - buys[bi]["ts"]).total_seconds() / 3600.0)
            bi += 1
    if holds:
        print(f"avg hold {np.mean(holds):.2f}h median {np.median(holds):.2f}h "
              f"min {np.min(holds):.2f} max {np.max(holds):.2f}")

    # subperiods
    print("\nsubperiods:")
    for lo, hi in (("2016-01-04", "2019-12-31"), ("2020-01-02", "2021-12-31"),
                   ("2022-01-03", "2023-12-29")):
        m = (r1["ts"] >= pd.Timestamp(lo, tz="America/New_York")) & (
            r1["ts"] < pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1))
        x = r1["equity"][m]; tt = r1["ts"][m]
        years = (tt[-1] - tt[0]).total_seconds() / (365.25 * 86400)
        pk = np.maximum.accumulate(x)
        print(f"  {lo[:7]}-{hi[:7]} CAGR {((x[-1]/x[0])**(1/years)-1)*100:6.2f}% "
              f"DD {(-(x/pk-1).min())*100:5.1f}%")

    # yearly
    i0 = bt.start_index(ts, DEV_START)
    yr = bt.yearly(r1["ts"], r1["equity"], c[i0:, 1])
    print("yearly:", {k: round(v["strategy"]*100, 1) for k, v in yr.items()})

    # DD window
    peak_arr = np.maximum.accumulate(r1["equity"])
    dd = r1["equity"] / peak_arr - 1.0
    jmin = int(np.argmin(dd))
    imax = int(np.argmax(r1["equity"][:jmin + 1]))
    print(f"max DD peak {str(r1['ts'][imax])[:10]} trough {str(r1['ts'][jmin])[:10]} "
          f"{(-dd[jmin])*100:.2f}%")

    # correlations
    print("\ncorrelations:")
    dr.index = pd.DatetimeIndex(dr.index).tz_localize(None).normalize()
    for win in WINNERS:
        p = ROOT / "research" / "new" / "curves" / f"{win}.json"
        if not p.exists():
            print(f"  {win}: missing")
            continue
        d = json.loads(p.read_text())
        wr = pd.Series(d["values"], index=pd.to_datetime(d["dates"]))
        wr.index = pd.DatetimeIndex(wr.index).tz_localize(None).normalize()
        wr = wr.pct_change().dropna()
        jj = dr.index.intersection(wr.index)
        print(f"  {win:38s} corr {dr.loc[jj].corr(wr.loc[jj]):+.3f}  n={len(jj)}")


if __name__ == "__main__":
    main()
