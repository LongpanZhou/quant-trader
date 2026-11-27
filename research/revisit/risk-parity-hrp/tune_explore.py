"""Tune step 2/3 exploration: which component sets the correlation and the return?

Dev only. Every variant here is counted in DIAGNOSIS.md.

    python research/revisit/risk-parity-hrp/tune_explore.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
spec = importlib.util.spec_from_file_location("strat0", HERE / "_before_tune" / "strategy.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
bt = S.bt


def main():
    ts, o, c = S.load_panel()
    sa = S.session_arrays(ts, o, c)
    st = S.daily_state(sa, S.P)
    wb = S.baseline_weights(sa)
    rb = S.run_one(ts, o, c, wb, 0.0, band=0.0)[1]
    rbase = S.daily_returns(rb["ts"], rb["equity"])
    on = wb[sa["last"], 1] > 0.5
    on_next = np.r_[False, on[:-1]][1:]
    dt = sa["dcl"][:, 1]
    rt = dt[1:] / dt[:-1] - 1

    def ev(name, w):
        s, r = S.run_one(ts, o, c, w, 1.0)
        rs = S.daily_returns(r["ts"], r["equity"])
        corr = np.corrcoef(rs, rbase)[0, 1]
        b_on = np.cov(rt[on_next], rs[on_next])[0, 1] / np.var(rt[on_next], ddof=1)
        b_off = np.cov(rt[~on_next], rs[~on_next])[0, 1] / np.var(rt[~on_next], ddof=1)
        sub = [S.slice_stats(r["ts"], r["equity"], a, b)["cagr"] for a, b in
               ((S.DEV_START, "2019-12-31"), ("2020-01-01", "2021-12-31"), ("2022-01-01", S.DEV_END))]
        print(f"{name:<38} CAGR {s['cagr']*100:6.2f} DD {s['max_drawdown']*100:5.1f} "
              f"Sh {s['sharpe']:4.2f} corr {corr:5.2f} beta on/off {b_on:4.2f}/{b_off:4.2f} "
              f"sub {sub[0]*100:5.1f}/{sub[1]*100:5.1f}/{sub[2]*100:5.1f}")
        return corr

    def var(name, brake=True, tilt_override=None, **kw):
        p = dict(S.P)
        p.update(kw)
        w, _ = S.build_weights(ts, o, c, p, brake=brake, tilt_override=tilt_override)
        return ev(name, w)

    ti = st["tilt"]
    var("V0 primary")
    var("A1 brake off", brake=False)
    var("A2 vol cap off", vol_cap=99.0)
    var("A3 brake+cap off", brake=False, vol_cap=99.0)
    var("A4 brake+cap+damper off", brake=False, vol_cap=99.0, persist_damp=0.0)
    var("A5 constant budget (no tilt, no cap/brake)", brake=False, vol_cap=99.0,
        tilt_override=np.where(np.isfinite(ti), 0.0, np.nan))
    var("A6 sign-flipped, no cap/brake", brake=False, vol_cap=99.0, tilt_override=-ti)
    var("A7 A3 tilt 0.30", brake=False, vol_cap=99.0, tilt_strength=0.30, b_max=0.70)

    # how often is the cap binding / what does the tilt look like by base state
    b0 = S.P["base_budget"] + S.P["tilt_strength"] * ti
    capb = S.P["vol_cap"] / st["sleeve_vol"]
    ok = np.isfinite(b0) & np.isfinite(capb)
    print("cap binding frac", float((capb[ok] < b0[ok]).mean()))
    onk = np.r_[False, on[:-1]]
    print("mean tilt base-on", float(np.nanmean(ti[onk])), "base-off", float(np.nanmean(ti[~onk])))
    print("mean final budget base-on/off (primary)")
    w, _ = S.build_weights(ts, o, c)
    bud = 1 - w[sa["first"], 2]
    print(float(bud[onk].mean()), float(bud[~onk].mean()))


if __name__ == "__main__":
    main()
