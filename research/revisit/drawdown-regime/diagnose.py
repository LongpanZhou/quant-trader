"""Tune diagnostics for drawdown-regime (dev 2016-01-04 .. 2023-12-29 only).

    python research/revisit/drawdown-regime/diagnose.py [module]

`module` defaults to `strategy` (current); `_before_tune.strategy` style paths
are loaded by file path with --file <path>.
"""
from __future__ import annotations

import importlib.util
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


def load(path):
    spec = importlib.util.spec_from_file_location("ddr_" + Path(path).parent.name.replace("-", "_"), path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def daily(r):
    s = pd.Series(r["equity"], index=r["ts"])
    return s.groupby(s.index.date).last()


def cagr(e):
    yrs = (pd.Timestamp(e.index[-1]) - pd.Timestamp(e.index[0])).days / 365.25
    return (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1


def main():
    path = sys.argv[sys.argv.index("--file") + 1] if "--file" in sys.argv else HERE / "strategy.py"
    mod = load(path)
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=500)
    w, info = mod.build_weights(ts, o, c)
    i0 = bt.start_index(ts, DEV_START)
    out = {"file": str(path)}

    # exposure
    wd = w[i0:]
    out["exposure"] = {"QQQ": float((wd[:, 0] > 0).mean()), "TQQQ": float((wd[:, 1] > 0).mean()),
                       "BIL": float((wd[:, 2] > 0).mean()), "short": 0.0,
                       "avg_gross_lev": float((wd[:, 0] + 3 * wd[:, 1]).mean())}
    out["n_episodes"] = info["n_episodes"]
    out["episodes"] = [{k: e.get(k) for k in ("entry_date", "exit_date", "exit_reason", "days", "ret", "dd")}
                       for e in info["episodes"]]

    res = {bp: bt.run(ts, o, c, w, DEV_START, 0.02, bp) for bp in (1.0, 5.0, 10.0)}
    out["dev"] = {f"{bp:.0f}bp": {k: bt.stats(r, BPY)[k] for k in ("cagr", "max_drawdown", "sharpe", "fills", "turnover")}
                  for bp, r in res.items()}

    # benchmarks and leverage-matched mix
    def const(wq, wt):
        x = np.zeros_like(w); x[:, 0] = wq; x[:, 1] = wt; x[:, 2] = 1 - wq - wt
        return x
    expo = float(wd[:, 1].mean() + wd[:, 0].mean() / 3)
    rb = bt.run_many(ts, o, c, [const(0, 1), const(1, 0), const(0, expo)], DEV_START, 0.02, 1.0)
    names = ["TQQQ", "QQQ", f"TQQQ {expo:.1%}/BIL"]
    out["bench"] = {n: {k: bt.stats(r, BPY)[k] for k in ("cagr", "max_drawdown", "sharpe")} for n, r in zip(names, rb)}

    # per year
    eq = daily(res[1.0]); bq = [daily(r) for r in rb]
    yrs = pd.Index([d.year for d in eq.index])
    tab = {}
    for y in range(2016, 2024):
        m = yrs == y
        prev = eq[yrs < y]
        def yr(s):
            s0 = s[yrs < y].iloc[-1] if (yrs < y).any() else s[m].iloc[0]
            return float(s[m].iloc[-1] / s0 - 1)
        tab[y] = {"strat": yr(eq), "TQQQ": yr(bq[0]), "QQQ": yr(bq[1]), "matched": yr(bq[2])}
    out["per_year"] = tab

    # where the gap comes from: TQQQ log return on days in vs out
    tq = np.log(bq[0]).diff().dropna()
    held = pd.Series(w[:, 1] + w[:, 0] / 3, index=ts).groupby(ts.date).mean().reindex(tq.index).fillna(0)
    out["gap"] = {"tqqq_logret_out_of_market": float(tq[held < 0.5].sum()),
                  "tqqq_logret_in_market": float(tq[held >= 0.5].sum()),
                  "strat_logret_in_market": float(np.log(eq).diff().reindex(tq.index)[held >= 0.5].sum()),
                  "days_in": int((held >= 0.5).sum()), "days_out": int((held < 0.5).sum()),
                  "top20_tqqq_days_missed": int((held[tq.nlargest(20).index] < 0.5).sum()),
                  "cost_drag_5bp_pp": float(out["dev"]["1bp"]["cagr"] - out["dev"]["5bp"]["cagr"]),
                  "cost_drag_10bp_pp": float(out["dev"]["1bp"]["cagr"] - out["dev"]["10bp"]["cagr"]),
                  "trades_per_year": out["dev"]["1bp"]["fills"] / 8.0}

    # signal anatomy on the daily file (state known at each session open)
    dd_d, hi_d, lo_d = mod._daily_state(*mod._qqq_daily(DEV_END), mod.PARAMS)[:3]
    dd_ = pd.Series(dd_d, index=pd.to_datetime(mod._qqq_daily(DEV_END)[0]))
    m = (dd_.index >= DEV_START)
    out["anatomy"] = {"sessions_dd_le_20": int((dd_[m] <= -0.20).sum()),
                      "years_with_dd_le_20": sorted({int(d.year) for d in dd_[m][dd_[m] <= -0.20].index})}

    # episode bootstrap: mean episode return vs random 1-session entries with same holding days
    rets = np.array([e["ret"] for e in info["episodes"]])
    if len(rets):
        rng = np.random.default_rng(0)
        dates, first, last = mod._sessions(ts)
        ks = np.flatnonzero(dates >= pd.Timestamp(DEV_START).date())
        tqo = o[first, 1]
        days = [e["days"] for e in info["episodes"]]
        sims = []
        for _ in range(5000):
            r = []
            for d in days:
                k = rng.choice(ks[ks + d < len(first)])
                r.append(tqo[k + d] / tqo[k] - 1)
            sims.append(np.mean(r))
        out["episodes_stats"] = {"n": len(rets), "hit": float((rets > 0).mean()), "mean": float(rets.mean()),
                                 "p_random_entry_ge": float((np.array(sims) >= rets.mean()).mean())}
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
