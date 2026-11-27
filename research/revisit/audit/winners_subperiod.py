"""Subperiod, holdout, cost and crash-day behaviour of the two winners."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import winners_lib as W  # noqa: E402
import bt  # noqa: E402

PERIODS = {
    "2016-2019": ("2016-01-04", "2019-12-31"),
    "2020": ("2020-01-01", "2020-12-31"),
    "2021-2023": ("2021-01-01", "2023-12-29"),
    "2024-2026": ("2024-01-02", "2026-10-23"),
    "dev_2016_2023": ("2016-01-04", "2023-12-29"),
    "holdout_2024_2026": ("2024-01-02", "2026-10-23"),
}


def top_drawdowns(daily, n=5):
    v = daily.to_numpy()
    idx = daily.index
    peak_i = 0
    trough_i = 0
    out = []
    in_dd = False
    for i in range(1, len(v)):
        if v[i] > v[peak_i]:
            if in_dd:
                out.append((peak_i, trough_i, v[trough_i] / v[peak_i] - 1.0))
                in_dd = False
            peak_i = i
            trough_i = i
        else:
            if not in_dd or v[i] < v[trough_i]:
                trough_i = i
            in_dd = True
    if in_dd:
        out.append((peak_i, trough_i, v[trough_i] / v[peak_i] - 1.0))
    out.sort(key=lambda x: x[2])
    return [{"peak": str(idx[a].date()), "trough": str(idx[b].date()),
             "dd": float(x), "recovery": None}
            for a, b, x in out[:n]]


def metrics_excluding_year(daily, year):
    s = daily[daily.index.year != year]
    # chain the two sides across the excluded year: use total multiple ratio
    total = daily.iloc[-1] / daily.iloc[0]
    y = daily[daily.index.year == year]
    if len(y) < 2:
        return W.metrics(s)
    yret = y.iloc[-1] / y.iloc[0]
    years = (daily.index[-1] - daily.index[0]).days / 365.25 - 1.0
    m = total / yret
    v = s.to_numpy()
    peak = np.maximum.accumulate(v)
    rets = np.diff(v) / v[:-1]
    return {
        "cagr": float(m ** (1.0 / years) - 1.0),
        "max_drawdown": float(-(v / peak - 1.0).min()),
        "sharpe": float(rets.mean() / rets.std(ddof=1) * np.sqrt(252)),
        "volatility": float(rets.std(ddof=1) * np.sqrt(252)),
        "years": float(years),
    }


def main():
    ts, o, h, l, c = W.load_panel()
    dates = bt.session_dates(ts)
    _, last = bt.day_bounds_from_dates(dates)
    sd = dates[last]
    idx = pd.to_datetime(sd)

    mod_r, w_r, _ = W.load_ratio_froth(ts, o, c)
    mod_v, w_v, _, _, _, _ = W.load_vol(ts, o, h, l, c)

    out = {"periods": {}, "costs": {}, "drawdowns": {}, "crash_days": {}}
    daily = {}
    for name, w in (("ratio_froth", w_r), ("vol_scaled", w_v)):
        r = bt.run(ts, o, c, w, W.START, band=0.02, slippage_bps=1.0)
        d = W.daily_equity(r)
        daily[name] = d
        ps = {}
        for p, (a, b) in PERIODS.items():
            ps[p] = W.subperiod(d, a, b)
        ps["ex_2020"] = metrics_excluding_year(d, 2020)
        ps["ex_best_year"] = None
        # best calendar year by return
        yr = W.yearly_returns_eoy(d)
        best = max(yr, key=yr.get)
        ps["best_year"] = best
        ps["ex_best_year"] = metrics_excluding_year(d, best)
        out["periods"][name] = ps
        out["drawdowns"][name] = top_drawdowns(d)

        cs = {}
        for slip in (0.0, 1.0, 2.0, 5.0, 10.0):
            rr = bt.run(ts, o, c, w, W.START, band=0.02, slippage_bps=slip)
            dd = W.daily_equity(rr)
            m = W.metrics(dd)
            cs[f"{slip:.0f}bp"] = {"cagr": m["cagr"], "dd": m["max_drawdown"],
                                  "sharpe": m["sharpe"]}
        out["costs"][name] = cs

    # benchmarks
    for name, col in (("tqqq", 1), ("qqq", 0), ("bil", 2)):
        d = pd.Series(c[last, col], index=idx)
        ps = {p: W.subperiod(d, a, b) for p, (a, b) in PERIODS.items()}
        ps["ex_2020"] = metrics_excluding_year(d, 2020)
        out["periods"][name] = ps
        out["drawdowns"][name] = top_drawdowns(d)
        daily[name] = d

    # crash-day behaviour: TQQQ worst days, strategy returns on those days
    tq = daily["tqqq"].pct_change()
    for name in ("ratio_froth", "vol_scaled", "qqq"):
        sr = daily[name].pct_change()
        j = pd.concat([sr.rename("s"), tq.rename("t")], axis=1).dropna()
        worst = j.nsmallest(25, "t")
        best = j.nlargest(25, "t")
        out["crash_days"][name] = {
            "worst25_tqqq_mean_tqqq": float(worst["t"].mean()),
            "worst25_mean_strategy": float(worst["s"].mean()),
            "worst25_capture": float(worst["s"].mean() / worst["t"].mean()),
            "best25_tqqq_mean_tqqq": float(best["t"].mean()),
            "best25_mean_strategy": float(best["s"].mean()),
            "best25_capture": float(best["s"].mean() / best["t"].mean()),
            "n_tqqq_lt_-10": int((j["t"] < -0.10).sum()),
            "mean_when_tqqq_lt_-10": float(j.loc[j["t"] < -0.10, "s"].mean()),
            "mean_tqqq_when_lt_-10": float(j.loc[j["t"] < -0.10, "t"].mean()),
        }

    W.save_json("winners_subperiod.json", out)

    print("periods")
    for name in ("ratio_froth", "vol_scaled", "tqqq", "qqq"):
        print(name)
        for p in PERIODS:
            m = out["periods"][name][p]
            print(f"  {p:20s} CAGR {m['cagr']*100:7.2f}%  DD {m['max_drawdown']*100:6.2f}%  "
                  f"Sharpe {m['sharpe']:4.2f}")
        m = out["periods"][name]["ex_2020"]
        print(f"  {'ex_2020':20s} CAGR {m['cagr']*100:7.2f}%  DD {m['max_drawdown']*100:6.2f}%  "
              f"Sharpe {m['sharpe']:4.2f}")
    print("costs", json.dumps(out["costs"], indent=1))
    print("crash", json.dumps(out["crash_days"], indent=1))
    print("dd", json.dumps(out["drawdowns"], indent=1))


if __name__ == "__main__":
    main()
