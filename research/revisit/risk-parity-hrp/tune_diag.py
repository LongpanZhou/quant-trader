"""Tune step 2 diagnostics (dev only, 2016-01-04 -> 2023-12-29).

    python research/revisit/risk-parity-hrp/tune_diag.py [module]

Loads `strategy.py` (or `_before_tune/strategy.py` with arg `before`) and prints
exposure, leverage-matched static mix, per-year table, gap decomposition,
cost drag, event study and correlation decomposition.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
which = sys.argv[1] if len(sys.argv) > 1 else "current"
path = HERE / ("_before_tune/strategy.py" if which == "before" else "strategy.py")
spec = importlib.util.spec_from_file_location("strat", path)
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
bt = S.bt
BARS = S.BARS


def dret(r):
    return S.daily_returns(r["ts"], r["equity"])


def main():
    ts, o, c = S.load_panel()
    assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
    sa = S.session_arrays(ts, o, c)
    w, info = S.build_weights(ts, o, c)
    out = {"info": info}

    # exposure
    out["exposure"] = dict(
        frac_min_qqq=float((w[:, 0] > 1e-9).mean()),
        frac_min_tqqq=float((w[:, 1] > 1e-9).mean()),
        frac_min_bil=float((w[:, 2] > 1e-9).mean()),
        mean_w_qqq=float(w[:, 0].mean()), mean_w_tqqq=float(w[:, 1].mean()),
        mean_w_bil=float(w[:, 2].mean()),
        mean_gross_lev=float((w[:, 0] + 3 * w[:, 1]).mean()),
    )
    lev = out["exposure"]["mean_gross_lev"]

    runs = {}
    for slip in (1.0, 5.0, 10.0):
        s, r = S.run_one(ts, o, c, w, slip)
        runs[slip] = (s, r)
    s1, r1 = runs[1.0]
    out["dev"] = {f"{k:.0f}bp": dict(cagr=v[0]["cagr"], dd=v[0]["max_drawdown"],
                                     sharpe=v[0]["sharpe"], fills=v[0]["fills"],
                                     turnover=v[0]["turnover"]) for k, v in runs.items()}
    yrs = s1["years"]
    out["trades_per_year"] = s1["fills"] / yrs
    out["turnover_per_year"] = s1["turnover"] / yrs

    # leverage-matched static mixes, rebalanced daily (target constant every bar,
    # band 0 so the engine rebalances each bar it drifts: use daily targets instead)
    def static(tq, qq):
        tgt = np.tile([qq, tq, 1 - tq - qq], (sa["d"], 1))
        ww = S.expand_to_minutes(sa, tgt)
        # daily rebalance: force a trade at each session's first bar via band 0
        st, rr = S.run_one(ts, o, c, ww, 1.0, band=0.0)
        return st, rr
    lm = {}
    for name, tq, qq in (("tqqq_at_avg_lev", lev / 3, 0.0),
                         ("same_avg_qqq_tqqq", out["exposure"]["mean_w_tqqq"],
                          out["exposure"]["mean_w_qqq"])):
        st, rr = static(tq, qq)
        lm[name] = dict(tqqq=tq, qqq=qq, cagr=st["cagr"], dd=st["max_drawdown"],
                        sharpe=st["sharpe"])
    out["leverage_matched"] = lm

    # baseline + corr
    corr, rb = S.corr_vs_base(ts, o, c, w, 1.0)
    out["corr"] = corr

    # per-year
    eq = pd.Series(r1["equity"], index=r1["ts"])
    qq = pd.Series(c[:, 0], index=ts)
    tq = pd.Series(c[:, 1], index=ts)
    yr = {}
    for y in range(2016, 2024):
        m = eq.index.year == y
        yr[y] = dict(strat=float(eq[m].iloc[-1] / eq[m].iloc[0] - 1),
                     tqqq=float(tq[m].iloc[-1] / tq[m].iloc[0] - 1),
                     qqq=float(qq[m].iloc[-1] / qq[m].iloc[0] - 1))
    out["per_year"] = yr

    # gap decomposition on daily returns (sum of log returns)
    rs = dret(r1)
    dq = sa["dcl"][:, 0]
    dt = sa["dcl"][:, 1]
    rt = dt[1:] / dt[:-1] - 1
    n = min(len(rs), len(rt))
    rs, rt = rs[-n:], rt[-n:]
    up = rt > 0
    out["gap"] = dict(
        strat_log_up_days=float(np.log1p(rs[up]).sum()),
        tqqq_log_up_days=float(np.log1p(rt[up]).sum()),
        strat_log_down_days=float(np.log1p(rs[~up]).sum()),
        tqqq_log_down_days=float(np.log1p(rt[~up]).sum()),
        n_up=int(up.sum()), n_down=int((~up).sum()),
        cost_drag_1bp_vs_0=None,
    )
    s0, _ = S.run_one(ts, o, c, w, 0.0)
    out["gap"]["cagr_0bp"] = s0["cagr"]
    # beta of strategy daily returns on TQQQ daily return, by base state
    wb = S.baseline_weights(sa)
    on = wb[sa["last"], 1] > 0.5   # base weight carried into the *next* session
    on_next = np.r_[False, on[:-1]][-n:]  # base position held in session k
    def beta(mask):
        x, y = rt[mask], rs[mask]
        return float(np.cov(x, y)[0, 1] / np.var(x, ddof=1)) if mask.sum() > 5 else None
    out["beta_vs_tqqq"] = dict(base_on=beta(on_next), base_off=beta(~on_next),
                               frac_base_on=float(on_next.mean()))
    # variance share of strategy daily returns on base-on days
    out["var_share_base_on"] = float((rs[on_next] ** 2).sum() / (rs ** 2).sum())

    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
