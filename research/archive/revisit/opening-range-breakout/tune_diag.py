"""Step-2 diagnosis of the gap to TQQQ (development period only, 2016-01-04..2023-12-29).

    python research/revisit/opening-range-breakout/tune_diag.py

Prints exposure, leverage-matched comparisons, per-year table, trade-level
statistics, cost drag and the QQQ overnight/intraday decomposition. Nothing
after DEV_END is loaded.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("orb", HERE / "strategy.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
bt = S.bt
DEV0, DEV1 = S.DEV_START, S.DEV_END


def trades(ts, o, w, col=0):
    """Round trips implied by the weights: signal at i, fill at open[i+1]."""
    on = w[:, col] > 0
    starts = np.flatnonzero(on & ~np.r_[False, on[:-1]])
    ends = np.flatnonzero(on & ~np.r_[on[1:], False])
    out = []
    for a, z in zip(starts, ends):
        if ts[a] < pd.Timestamp(DEV0, tz="America/New_York"):
            continue
        # last "on" row z is executed at open z+1 (still on); the 0 row z+1 fills at open z+2
        pin, pout = o[a + 1, col], o[z + 2, col]
        out.append({"date": ts[a].date(), "year": ts[a].year, "size": w[a, col],
                    "ret": pout / pin - 1.0, "bars": int(z - a + 1)})
    return pd.DataFrame(out)


def daily(res):
    s = pd.Series(res["equity"], index=res["ts"])
    return s.groupby(s.index.date).last()


def cagr(d):
    yrs = (pd.Timestamp(d.index[-1]) - pd.Timestamp(d.index[0])).days / 365.25
    return (d.iloc[-1] / d.iloc[0]) ** (1 / yrs) - 1


def mdd(x):
    x = np.asarray(x)
    return float(-(x / np.maximum.accumulate(x) - 1).min())


def main():
    ts, o, c, q, t, b = S.load_dev()
    w, info = S.build_weights(ts, o, c, q, t)
    i0 = bt.start_index(ts, DEV0)
    wd = w[i0:]
    out = {"events": info}

    # exposure
    out["exposure"] = {
        "minutes_in_qqq": float((wd[:, 0] > 0).mean()),
        "minutes_in_tqqq": float((wd[:, 1] > 0).mean()),
        "minutes_in_bil_only": float((wd[:, 2] >= 1 - 1e-12).mean()),
        "avg_qqq_weight": float(wd[:, 0].mean()),
        "avg_gross_leverage_qqq_equiv": float(wd[:, 0].mean() + 3 * wd[:, 1].mean()),
        "avg_size_when_in": float(wd[wd[:, 0] > 0, 0].mean()),
        "sessions_with_trade_frac": None,
    }

    res = {k: bt.run(ts, o, c, w, DEV0, band=0.02, slippage_bps=k) for k in (0.0, 1.0, 5.0, 10.0)}
    st = {k: bt.stats(r, S.BARS_1M) for k, r in res.items()}
    out["cost"] = {f"{k:g}bp": {"cagr": st[k]["cagr"], "dd": st[k]["max_drawdown"],
                               "sharpe": st[k]["sharpe"], "fills": st[k]["fills"],
                               "turnover_per_yr": st[k]["turnover"] / st[k]["years"]}
                   for k in st}

    tr = trades(ts, o, w, 0)
    nsess = len(set(ts[i0:].date))
    out["exposure"]["sessions_with_trade_frac"] = len(tr) / nsess
    tr["wret"] = tr["ret"] * tr["size"]
    out["trades"] = {
        "n": int(len(tr)), "per_year": len(tr) / 8.0,
        "hit_rate_gross": float((tr["ret"] > 0).mean()),
        "mean_gross_bp": float(tr["ret"].mean() * 1e4),
        "median_gross_bp": float(tr["ret"].median() * 1e4),
        "mean_net_bp_1bp_rt": float(tr["ret"].mean() * 1e4 - 4),     # QQQ+BIL legs both ways
        "profit_factor_gross": float(tr.loc[tr.ret > 0, "ret"].sum() / -tr.loc[tr.ret < 0, "ret"].sum()),
        "mean_bars_held": float(tr["bars"].mean()),
        "t_stat": float(tr["ret"].mean() / tr["ret"].std(ddof=1) * np.sqrt(len(tr))),
    }
    rng = np.random.default_rng(0)
    r = tr["ret"].to_numpy()
    boots = rng.choice(r - r.mean(), size=(10000, len(r))).mean(1)
    out["trades"]["bootstrap_p_mean_gt0"] = float((boots >= r.mean()).mean())
    out["trades_by_year"] = tr.groupby("year").agg(n=("ret", "size"), hit=("ret", lambda x: (x > 0).mean()),
                                                   mean_bp=("ret", lambda x: x.mean() * 1e4)).round(3).to_dict("index")

    # per-year table vs TQQQ, QQQ (1-minute closes)
    dd = daily(res[1.0])
    j = slice(i0, None)
    tsd = ts[j]
    px = pd.DataFrame({"qqq": c[j, 0], "tqqq": c[j, 1], "bil": c[j, 2]}, index=tsd)
    pxd = px.groupby(px.index.date).last()
    yrs = {}
    for y in range(2016, 2024):
        m = [d.year == y for d in dd.index]
        e = dd[m]
        p = pxd[[d.year == y for d in pxd.index]]
        prev_e = dd[[d.year == y - 1 for d in dd.index]]
        prev_p = pxd[[d.year == y - 1 for d in pxd.index]]
        e0 = prev_e.iloc[-1] if len(prev_e) else 100000.0
        p0 = prev_p.iloc[-1] if len(prev_p) else px.iloc[0]
        yrs[y] = {"strategy": e.iloc[-1] / e0 - 1, "tqqq": p["tqqq"].iloc[-1] / p0["tqqq"] - 1,
                  "qqq": p["qqq"].iloc[-1] / p0["qqq"] - 1, "bil": p["bil"].iloc[-1] / p0["bil"] - 1}
    out["per_year"] = yrs

    # leverage-matched static mixes (daily rebalanced, band 0 so the small leg rebalances)
    x = out["exposure"]["avg_qqq_weight"]
    tsD, oD, cD = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1D")
    mixes = {}
    for name, wq, wt in (("QQQ_static_avg_w", x, 0), ("TQQQ_static_avg_w/3", 0, x / 3)):
        W = np.zeros((len(tsD), 3))
        W[:, 0], W[:, 1], W[:, 2] = wq, wt, 1 - wq - wt
        rr = bt.run(tsD, oD, cD, W, DEV0, band=0.0, slippage_bps=1.0)
        s = bt.stats(rr, 252)
        mixes[name] = {"cagr": s["cagr"], "dd": s["max_drawdown"], "sharpe": s["sharpe"]}
    # intraday-matched: hold QQQ at the strategy's average in-trade size from 10:00 to the close every day
    tod = np.asarray(ts.hour * 60 + ts.minute)
    dates = ts.date
    last = np.r_[dates[1:] != dates[:-1], True]
    Wi = np.zeros_like(w)
    Wi[:, 2] = 1.0
    inday = (tod >= 600) & ~last & ~np.r_[last[1:], False]
    Wi[inday, 0] = x / inday[i0:].mean()
    Wi[inday, 2] = 1 - Wi[inday, 0]
    rr = bt.run(ts, o, c, Wi, DEV0, band=0.02, slippage_bps=1.0)
    s = bt.stats(rr, S.BARS_1M)
    mixes["QQQ_intraday_10:00-close_same_avg_exposure"] = {"cagr": s["cagr"], "dd": s["max_drawdown"],
                                                           "sharpe": s["sharpe"], "w": float(Wi[inday, 0][0])}
    out["leverage_matched"] = mixes

    # QQQ overnight vs intraday decomposition (dev): where QQQ's return lives
    first = np.r_[True, dates[1:] != dates[:-1]]
    fo = o[first, 0][1:]
    lc = c[last, 0]
    di = np.asarray(dates[first])
    keep = di[1:] >= pd.Timestamp(DEV0).date()
    on = (fo / lc[:-1] - 1)[keep]
    intr = (lc[1:] / fo - 1)[keep]
    out["qqq_decomp_annual"] = {"overnight": float(np.prod(1 + on) ** (252 / len(on)) - 1),
                                "intraday_open_close": float(np.prod(1 + intr) ** (252 / len(intr)) - 1)}
    tf = o[first, 1][1:]
    tlc = c[last, 1]
    out["tqqq_decomp_annual"] = {
        "overnight": float(np.prod(1 + (tf / tlc[:-1] - 1)[keep]) ** (252 / keep.sum()) - 1),
        "intraday_open_close": float(np.prod(1 + (tlc[1:] / tf - 1)[keep]) ** (252 / keep.sum()) - 1)}

    # baseline correlation and drawdown
    base = S.baseline_165_daily()
    out["corr_vs_165d"] = S.correlate(dd, base)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
