"""Tune-brief diagnostics (dev only, 2016-01-04 -> 2023-12-29).

    python research/revisit/event-risk-overlay/tune_diag.py [strategy_module]

Prints exposure, leverage-matched static mix, per-year table, gap
decomposition, costs, event count / hit rate / bootstrap for the expiry
session. Never loads data after 2023-12-29.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import bt  # noqa: E402

S = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "strategy")
DEV0, DEV1 = "2016-01-04", "2023-12-29"
BY = 252 * 390


def daily_eq(r):
    eq = pd.Series(r["equity"], index=r["ts"])
    return eq.groupby(eq.index.date).last()


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1min")
    assert ts[-1].date() <= pd.Timestamp(DEV1).date()
    w, info = S.build_weights(ts, o, c)
    assert np.isfinite(w).all() and (w >= -1e-12).all() and (w.sum(1) <= 1 + 1e-9).all()
    dates = bt.session_dates(ts)
    first, last = S.day_bounds(dates)
    out = {"info": info}

    res = {}
    for slip in (1.0, 5.0, 10.0):
        r = bt.run(ts, o, c, w, start=DEV0, band=0.02, slippage_bps=slip)
        res[slip] = (r, bt.stats(r, BY))
    r1, s1 = res[1.0]
    yrs = s1["years"]

    # exposure from realised holdings: (equity - cash) share is total; split by weights
    out["exposure"] = {
        "frac_minutes_tqqq": float((w[:, 1] > 0).mean()),
        "frac_minutes_qqq": float((w[:, 0] > 0).mean()),
        "frac_minutes_bil_only": float(((w[:, 0] == 0) & (w[:, 1] == 0)).mean()),
        "frac_minutes_short": 0.0,
        "mean_tqqq_weight": float(w[:, 1].mean()),
        "avg_gross_leverage": float(3 * w[:, 1].mean() + w[:, 0].mean()),
    }

    # leverage-matched static mix
    f = float(w[:, 1].mean())
    ws = np.zeros_like(w)
    ws[:, 1] = f
    ws[:, 2] = 1 - f
    rs = bt.run(ts, o, c, ws, start=DEV0, band=0.02, slippage_bps=1.0)
    ss = bt.stats(rs, BY)
    # also daily-rebalanced explicitly: reset weight each session open (band 0 at last bar)
    out["static_mix"] = {"tqqq_frac": f, "cagr": ss["cagr"], "max_drawdown": ss["max_drawdown"],
                         "sharpe": ss["sharpe"], "fills": ss["fills"]}

    # per-year
    i0 = bt.start_index(ts, DEV0)
    deq = daily_eq(r1)
    qq = pd.Series(c[last, 0], index=pd.to_datetime(dates[first]))
    tq = pd.Series(c[last, 1], index=pd.to_datetime(dates[first]))
    # buy-and-hold from first open
    qq0, tq0 = o[i0, 0], o[i0, 1]
    def yr(series, start_val):
        ye = series.groupby(series.index.year).last()
        prev = ye.shift(1)
        prev.iloc[0] = start_val
        return ye / prev - 1
    ystrat = yr(pd.Series(deq.values, index=pd.to_datetime(deq.index)), 100_000.0)
    out["per_year"] = {int(y): {"strategy": float(ystrat[y]), "tqqq": float(yr(tq, tq0)[y]),
                                "qqq": float(yr(qq, qq0)[y]),
                                "static_mix": float(yr(pd.Series(daily_eq(rs).values,
                                                    index=pd.to_datetime(daily_eq(rs).index)),
                                                    100_000.0)[y])}
                       for y in ystrat.index}

    # where TQQQ's dev return lives: overnight vs intraday, by session type
    held = np.r_[0.0, w[:-1, 1]]                 # weight held during bar j
    sess_dates_ = dates[first]
    opex_ = set(S.opex_dates(2016, 2023))
    is_x_ = np.array([d in opex_ for d in sess_dates_])
    on = np.r_[0.0, np.log(o[first[1:], 1] / c[last[:-1], 1])]      # overnight into k
    intra = np.log(c[last, 1] / o[first, 1])
    w_on = np.r_[0.0, w[first[1:] - 2, 1]]       # weight carried across that gap
    w_in = w[first, 1]                           # target held during session k
    win_ = w_in > 0
    cats = {"window": win_, "expiry": is_x_, "other": ~win_ & ~is_x_}
    out["where_tqqq_returns_live_log"] = {
        nm: {"sessions": int(m.sum()),
             "tqqq_overnight": float(on[m].sum()), "tqqq_intraday": float(intra[m].sum()),
             "captured_overnight": float((w_on * on)[m].sum()),
             "captured_intraday": float((w_in * intra)[m].sum())}
        for nm, m in cats.items()}
    out["where_tqqq_returns_live_log"]["strategy_total_log"] = float(
        np.log(r1["equity"][-1] / r1["equity"][0]))
    # session-level: TQQQ up-days missed
    t_c2c = np.r_[np.nan, c[last, 1][1:] / c[last, 1][:-1] - 1]
    sess_held = np.array([held[first[k]:last[k] + 1].max() > 0 for k in range(len(first))])
    big_up = t_c2c > 0.05
    big_dn = t_c2c < -0.05
    out["sessions"] = {
        "n": int(len(first)), "held": int(sess_held.sum()),
        "big_up_days(>5%)": int(np.nansum(big_up)), "big_up_held": int((big_up & sess_held).sum()),
        "big_down_days(<-5%)": int(np.nansum(big_dn)), "big_down_held": int((big_dn & sess_held).sum()),
        "sum_c2c_held": float(np.nansum(np.log1p(t_c2c) * sess_held)),
        "sum_c2c_unheld": float(np.nansum(np.log1p(t_c2c) * ~sess_held)),
    }

    out["costs"] = {f"{int(k)}bp": {"cagr": v[1]["cagr"], "max_drawdown": v[1]["max_drawdown"],
                                    "sharpe": v[1]["sharpe"], "fills_per_yr": v[1]["fills"] / yrs,
                                    "turnover_per_yr": v[1]["turnover"] / yrs} for k, v in res.items()}

    # expiry-session event study: TQQQ open->close on expiry vs other Fridays
    sess_dates = dates[first]
    opex = set(S.opex_dates(2016, 2023))
    is_x = np.array([d in opex for d in sess_dates])
    is_fri = np.array([d.weekday() == 4 for d in sess_dates])
    o2c = c[last, 1] / o[first, 1] - 1
    x = o2c[is_x]
    y = o2c[is_fri & ~is_x]
    rng = np.random.default_rng(3)
    diff = x.mean() - y.mean()
    pool = np.r_[x, y]
    perm = np.array([(lambda p: p[:len(x)].mean() - p[len(x):].mean())(rng.permutation(pool))
                     for _ in range(10000)])
    boot = np.array([rng.choice(x, len(x)).mean() for _ in range(10000)])
    out["expiry_event"] = {
        "n_events": int(is_x.sum()), "mean_o2c_bp": float(x.mean() * 1e4),
        "other_fri_mean_bp": float(y.mean() * 1e4), "diff_bp": float(diff * 1e4),
        "hit_rate_negative": float((x < 0).mean()),
        "perm_p_one_sided(expiry<otherFri)": float((perm <= diff).mean()),
        "bootstrap_p(mean>=0)": float((boot >= 0).mean()),
    }
    # window blocks: hit rate of the 192 blocks (TQQQ return over each held block)
    blocks = []
    k = 0
    hold = np.array([held[first[j]:last[j] + 1].max() > 0 for j in range(len(first))])
    eqv = r1["equity"]
    # strategy equity per held block
    tsi = ts[i0:]
    dd = daily_eq(r1)
    dser = pd.Series(dd.values, index=pd.to_datetime(dd.index))
    dret = dser.pct_change().fillna(dser.iloc[0] / 100_000 - 1)
    hser = pd.Series(hold, index=pd.to_datetime(sess_dates)).reindex(dret.index).fillna(False)
    grp = (hser != hser.shift()).cumsum()
    for g, sub in dret.groupby(grp):
        if hser[sub.index[0]]:
            blocks.append(float(np.prod(1 + sub.values) - 1))
    blocks = np.array(blocks)
    out["blocks"] = {"n": int(len(blocks)), "hit_rate": float((blocks > 0).mean()),
                     "mean": float(blocks.mean()), "median": float(np.median(blocks)),
                     "worst": float(blocks.min()), "best": float(blocks.max())}
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
