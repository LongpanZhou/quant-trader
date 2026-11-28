"""Tune 2026-11-27: stepwise bug fixes, controls, neighbourhood, sub-periods.

Dev window only (2016-01-04 .. 2023-12-29). Writes tune_results.json.
    python research/revisit/drawdown-regime/tune.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402
bt = S.bt

SUBS = {"2016-19": ("2016-01-04", "2019-12-31"), "2020-21": ("2020-01-01", "2021-12-31"),
        "2022-23": ("2022-01-01", "2023-12-29")}


def load_before():
    spec = importlib.util.spec_from_file_location("ddr_before", HERE / "_before_tune" / "strategy.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ROOT = S.ROOT  # the copy sits one folder deeper
    return m


def metrics(r, rb_daily=None):
    s = bt.stats(r, S.BPY)
    out = {k: float(s[k]) for k in ("cagr", "max_drawdown", "sharpe", "fills")}
    eq = pd.Series(r["equity"], index=r["ts"])
    for name, (a, b) in SUBS.items():
        e = eq[(eq.index >= pd.Timestamp(a, tz="America/New_York")) &
               (eq.index < pd.Timestamp(b, tz="America/New_York") + pd.Timedelta(days=1))]
        yrs = (e.index[-1] - e.index[0]).total_seconds() / (365.25 * 86400)
        out[name] = {"cagr": float((e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1),
                     "dd": float(-(e / e.cummax() - 1).min())}
    if rb_daily is not None:
        d = S._daily_returns(r)
        out["corr165"] = float(pd.concat([d, rb_daily], axis=1, join="inner").dropna().corr().iloc[0, 1])
    return out


def main():
    ts, o, c = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min", warmup_days=500)
    dates, first, last = S._sessions(ts)
    rb = bt.run(ts, o, c, S.baseline_weights(ts, c), S.DEV_START, 0.02, 1.0)
    rbd = S._daily_returns(rb)
    res = {}
    n_variants = 0

    def old_timing(T, col=1):
        n = len(ts)
        day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
        w = np.zeros((n, 3)); w[:, col] = T[day_id]; w[:, 2] = 1 - T[day_id]
        return w

    # ---- stepwise fixes
    B = load_before()
    w0, i0 = B.build_weights(ts, o, c)
    _, i1 = S.build_weights(ts, o, c, mode="same_day")
    w2, _ = S.build_weights(ts, o, c, mode="same_day")
    w3, i3 = S.build_weights(ts, o, c)
    steps = {"0 before (lead shift(2) fix)": w0,
             "1 + daily close for dprev": old_timing(i1["targets"]),
             "2 + fill at session open": w2,
             "3 + persistent deep-drawdown arm (spec rule 1-2)": w3}
    for bp in (1.0, 5.0, 10.0):
        rs = bt.run_many(ts, o, c, list(steps.values()), S.DEV_START, 0.02, bp)
        for name, r in zip(steps, rs):
            res.setdefault("steps", {}).setdefault(name, {})[f"{bp:.0f}bp"] = metrics(r, rbd)
    res["episodes_before"] = i0["episodes"]
    res["episodes_final"] = i3["episodes"]

    # ---- controls
    ctrl = {}
    for mode in ("breakout_only", "deep_only", "fixed_hold", "qqq"):
        w, inf = S.build_weights(ts, o, c, mode=mode)
        ctrl[mode] = (w, inf["n_episodes"])
    T = i3["targets"]
    rng = np.random.default_rng(7)
    shifts = rng.integers(60, len(T) - 60, size=40)
    plac = [S.weights_from_targets(np.roll(T, int(s)), first, last, 1) for s in shifts]
    expo = float(T.mean())
    mix = np.zeros_like(w3); mix[:, 1] = expo; mix[:, 2] = 1 - expo
    names = list(ctrl) + ["matched_static_mix"]
    rs = bt.run_many(ts, o, c, [v[0] for v in ctrl.values()] + [mix], S.DEV_START, 0.02, 1.0)
    res["controls"] = {n: dict(metrics(r, rbd), episodes=(ctrl[n][1] if n in ctrl else None))
                       for n, r in zip(names, rs)}
    res["controls"]["matched_static_mix"]["tqqq_weight"] = expo
    rp = bt.run_many(ts, o, c, plac, S.DEV_START, 0.02, 1.0)
    pc = np.array([bt.stats(r, S.BPY)["cagr"] for r in rp])
    ps = np.array([bt.stats(r, S.BPY)["sharpe"] for r in rp])
    fin = res["steps"]["3 + persistent deep-drawdown arm (spec rule 1-2)"]["1bp"]
    res["placebo_circular_shift"] = {"n": len(pc), "median_cagr": float(np.median(pc)),
                                     "p90_cagr": float(np.quantile(pc, 0.9)),
                                     "p_cagr_ge_strategy": float((pc >= fin["cagr"]).mean()),
                                     "p_sharpe_ge_strategy": float((ps >= fin["sharpe"]).mean())}
    n_variants += 4 + 4 + 1

    # ---- leave-one-episode-out
    looo = []
    for e in i3["episodes"]:
        Tm = T.copy(); Tm[e["entry_i"]:e.get("exit_i", len(T))] = 0
        looo.append(S.weights_from_targets(Tm, first, last, 1))
    rs = bt.run_many(ts, o, c, looo, S.DEV_START, 0.02, 1.0)
    res["leave_one_episode_out"] = {e["entry_date"]: float(bt.stats(r, S.BPY)["cagr"])
                                    for e, r in zip(i3["episodes"], rs)}

    # ---- episode bootstrap vs random entries of the same lengths
    rets = np.array([e["ret"] for e in i3["episodes"]])
    tqo = o[first, 1]
    ks = np.flatnonzero(dates >= pd.Timestamp(S.DEV_START).date())
    sims = []
    for _ in range(5000):
        r = [tqo[min(k + e["days"], len(tqo) - 1)] / tqo[k] - 1
             for e, k in zip(i3["episodes"], rng.choice(ks[:-60], size=len(rets)))]
        sims.append(np.mean(r))
    res["episode_test"] = {"n": int(len(rets)), "hit": float((rets > 0).mean()),
                           "mean_ret": float(rets.mean()),
                           "p_random_mean_ge": float((np.array(sims) >= rets.mean()).mean())}

    # ---- +-1 step neighbourhood (one parameter at a time)
    nb = {}
    for key, vals in S.NEIGHBOURS.items():
        ws = [S.build_weights(ts, o, c, params={key: v})[0] for v in vals]
        rs = bt.run_many(ts, o, c, ws, S.DEV_START, 0.02, 1.0)
        nb[key] = {str(v): metrics(r, rbd) for v, r in zip(vals, rs)}
        n_variants += len(vals) - 1
    res["neighbourhood"] = nb
    res["variants_tried"] = n_variants

    out = HERE / "tune_results.json"
    with open(out, "w", newline="\n", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=float)
    # compact print
    for k, v in res["steps"].items():
        print(k, {b: (round(x["cagr"] * 100, 2), round(x["max_drawdown"] * 100, 2), round(x["sharpe"], 2),
                      x["fills"], round(x["corr165"], 2)) for b, x in v.items()})
    for k, v in res["controls"].items():
        print("ctrl", k, round(v["cagr"] * 100, 2), round(v["max_drawdown"] * 100, 2), round(v["sharpe"], 2),
              v["episodes"], {s: round(v[s]["cagr"] * 100, 1) for s in SUBS})
    print("placebo", res["placebo_circular_shift"])
    print("looo", res["leave_one_episode_out"])
    print("episodes", res["episode_test"])
    for e in res["episodes_final"]:
        print("  ", e["entry_date"], e.get("exit_date"), e.get("exit_reason"), e["days"], round(e["ret"], 3),
              round(e["trough"], 3))
    for key, d in nb.items():
        print("nb", key, {v: (round(x["cagr"] * 100, 2), round(x["max_drawdown"] * 100, 1), round(x["sharpe"], 2))
                          for v, x in d.items()})
    print("sub final", {s: fin[s] for s in SUBS})
    print("wrote", out, "variants", n_variants)


if __name__ == "__main__":
    main()
