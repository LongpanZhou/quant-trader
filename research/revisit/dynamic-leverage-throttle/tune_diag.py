"""Tune step 2: diagnose the gap to TQQQ (development period only).

    python research/revisit/dynamic-leverage-throttle/tune_diag.py [module]

`module` defaults to `strategy` (the current file); pass `_before_tune.strategy`
style paths via the DLT_STRAT env var to diagnose another copy.
Writes tune_diag.json. Never touches data after 2023-12-29.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402


def load_mod(path):
    spec = importlib.util.spec_from_file_location("dlt_" + path.stem + str(abs(hash(str(path)))), path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def daily_eq(ts, eq, dates):
    return pd.Series(eq, index=dates).groupby(level=0).last()


def main():
    path = Path(os.environ.get("DLT_STRAT", HERE / "strategy.py"))
    S = load_mod(path)
    ts, op, cl = S.load_dev_panel()
    assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
    w, info = S.build_weights(ts, op, cl)
    base = S.baseline_165d_weights(ts, cl)
    i0 = bt.start_index(ts, S.DEV_START)
    dates_all = S.session_dates(ts)
    dates = dates_all[i0:]
    wd = w[i0:]
    out = {"strategy_file": str(path)}

    # exposure ------------------------------------------------------------
    out["exposure"] = {
        "frac_minutes_tqqq": float((wd[:, 1] > 0).mean()),
        "frac_minutes_qqq": float((wd[:, 0] > 0).mean()),
        "frac_minutes_bil": float((wd[:, 2] > 0).mean()),
        "frac_minutes_synthetic_short": 0.0,
        "mean_w_tqqq": float(wd[:, 1].mean()),
        "mean_w_tqqq_when_held": float(wd[wd[:, 1] > 0, 1].mean()) if (wd[:, 1] > 0).any() else 0.0,
        "avg_gross_leverage": float(3 * wd[:, 1].mean() + wd[:, 0].mean()),
        "entries": int(info.get("entry_count", 0)),
    }
    a = out["exposure"]["mean_w_tqqq"]

    # main runs -----------------------------------------------------------
    static = np.zeros_like(w)
    static[:, 1] = a
    static[:, 2] = 1 - a
    static2 = np.zeros_like(w)  # same exposure via TQQQ, daily rebalance w/o band
    runs = {}
    for slip in (1.0, 5.0, 10.0):
        r = bt.run(ts, op, cl, w, S.DEV_START, band=0.02, slippage_bps=slip)
        s = bt.stats(r, S.BARS)
        runs[slip] = r
        out[f"dev_{int(slip)}bp"] = {k: float(s[k]) for k in
                                     ("cagr", "max_drawdown", "sharpe", "fills", "turnover")}
    r1 = runs[1.0]
    rb = bt.run(ts, op, cl, base, S.DEV_START, band=0.02, slippage_bps=1.0)
    sd = daily_eq(ts, r1["equity"], dates).pct_change().dropna()
    bd = daily_eq(ts, rb["equity"], dates).pct_change().dropna()
    out["corr_vs_165d"] = float(np.corrcoef(sd, bd.loc[sd.index])[0, 1])

    # leverage-matched static mix: analytic daily rebalance at weight a
    last = S.day_bounds(dates_all)[1]
    dts = dates_all[last]
    keep = dts >= pd.Timestamp(S.DEV_START).date()
    tq = cl[last, 1]
    bl = cl[last, 2]
    qq = cl[last, 0]
    rt = tq[1:] / tq[:-1] - 1
    rbil = bl[1:] / bl[:-1] - 1
    rq = qq[1:] / qq[:-1] - 1
    kk = keep[1:] & keep[:-1]
    mix = (a * rt + (1 - a) * rbil)[kk]
    yrs = r1["ts"][-1] - r1["ts"][0]
    yrs = yrs.total_seconds() / (365.25 * 86400)
    mix_cagr = float(np.prod(1 + mix) ** (1 / yrs) - 1)
    mix_eq = np.cumprod(1 + mix)
    out["leverage_matched_static"] = {
        "w_tqqq": a, "cagr": mix_cagr,
        "max_drawdown_daily": float(-(mix_eq / np.maximum.accumulate(mix_eq) - 1).min()),
        "sharpe_daily": float(mix.mean() / mix.std() * np.sqrt(252)),
    }
    rs = bt.run(ts, op, cl, static, S.DEV_START, band=0.0, slippage_bps=1.0)
    ss = bt.stats(rs, S.BARS)
    out["leverage_matched_static"]["bt_cagr_band0"] = float(ss["cagr"])
    out["leverage_matched_static"]["bt_dd_band0"] = float(ss["max_drawdown"])

    # per-year ------------------------------------------------------------
    eqd = daily_eq(ts, r1["equity"], dates)
    yr = {}
    d_idx = pd.to_datetime(pd.Index(eqd.index))
    tq_d = pd.Series(tq[keep], index=pd.to_datetime(dts[keep]))
    qq_d = pd.Series(qq[keep], index=pd.to_datetime(dts[keep]))
    eqs = pd.Series(eqd.to_numpy(), index=d_idx)
    for y in range(2016, 2024):
        def yret(s):
            prevv = s[s.index.year < y]
            cur = s[s.index.year == y]
            p0 = prevv.iloc[-1] if len(prevv) else cur.iloc[0]
            return float(cur.iloc[-1] / p0 - 1)
        yr[y] = {"strategy": yret(eqs), "tqqq": yret(tq_d), "qqq": yret(qq_d)}
    out["yearly"] = yr

    # where the gap comes from -------------------------------------------
    # daily TQQQ weight at the open of each dev session (target for that day)
    first = S.day_bounds(dates_all)[0]
    wday = w[first, 1]  # target written at the session's first bar
    in_mkt = wday[1:][kk] > 0
    rt_k = rt[kk]
    sr = sd.to_numpy()
    out["gap"] = {
        "sessions": int(kk.sum()),
        "sessions_in_market": int(in_mkt.sum()),
        "tqqq_log_return_total": float(np.log1p(rt_k).sum()),
        "tqqq_log_return_while_out": float(np.log1p(rt_k[~in_mkt]).sum()),
        "tqqq_log_return_while_in": float(np.log1p(rt_k[in_mkt]).sum()),
        "tqqq_up_days": int((rt_k > 0).sum()),
        "tqqq_up_days_missed": int(((rt_k > 0) & ~in_mkt).sum()),
        "tqqq_best20_days_missed": int((~in_mkt[np.argsort(rt_k)[-20:]]).sum()),
        "strategy_log_return_total": float(np.log1p(sr).sum()),
        "cost_drag_cagr_5bp": out["dev_1bp"]["cagr"] - out["dev_5bp"]["cagr"],
        "cost_drag_cagr_10bp": out["dev_1bp"]["cagr"] - out["dev_10bp"]["cagr"],
        "fills_per_year": out["dev_1bp"]["fills"] / yrs,
        "turnover_per_year": out["dev_1bp"]["turnover"] / yrs,
    }

    # events: hit rate + bootstrap ----------------------------------------
    eq = r1["equity"]
    lastd = S.day_bounds(dates)[1]
    firstd = S.day_bounds(dates)[0]
    # episode = from the fill bar (first bar of entry session +1) to exit fill
    sess0 = int(np.searchsorted(np.r_[first], i0))  # session index of dev start
    ep = []
    ep_tq = []
    for en, ex in zip(info["entries"], info["exits"]):
        s_in = en["session"] - sess0
        s_out = ex["session"] - sess0
        if s_in < 0 or s_in >= len(firstd):
            continue
        b_in = firstd[s_in]
        b_out = firstd[s_out] + 1 if s_out < len(firstd) else len(eq) - 1
        b_out = min(b_out, len(eq) - 1)
        ep.append(float(eq[b_out] / eq[b_in] - 1))
        tqc = cl[i0:, 1]
        ep_tq.append(float(tqc[b_out] / tqc[b_in] - 1))
    ep = np.array(ep)
    rng = np.random.default_rng(7)
    boot = rng.choice(ep, size=(20000, len(ep)), replace=True).mean(1) if len(ep) else np.array([0])
    out["events"] = {
        "n": int(len(ep)), "episode_returns": ep.tolist(),
        "episode_tqqq_returns": ep_tq,
        "hit_rate": float((ep > 0).mean()) if len(ep) else None,
        "mean": float(ep.mean()) if len(ep) else None,
        "bootstrap_p_mean_le_0": float((boot <= 0).mean()),
        "entries": info["entries"], "exits": info["exits"],
    }
    (HERE / os.environ.get("DLT_OUT", "tune_diag.json")).write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("events",)}, indent=1, default=str))
    print("events", json.dumps({k: v for k, v in out["events"].items()
                                if k not in ("entries", "exits")}, default=str))


if __name__ == "__main__":
    main()
