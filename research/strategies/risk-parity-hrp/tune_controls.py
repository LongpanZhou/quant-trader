"""Tune controls (dev only): original controls(), A4 neighbourhood, cut test.

    python research/strategies/risk-parity-hrp/tune_controls.py
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
spec = importlib.util.spec_from_file_location("strat0", HERE / "_before_tune" / "strategy.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def main():
    ts, o, c = S.load_panel()
    w, _ = S.build_weights(ts, o, c)
    out = {}
    S.controls(ts, o, c, w, None, out)
    ctrl = out["controls"]

    # block bootstrap on the event study (20-day blocks, 10,000 draws)
    sa = S.session_arrays(ts, o, c)
    st = S.daily_state(sa, S.P)
    sl = np.r_[np.nan, sa["dcl"][1:, 0] / sa["dcl"][:-1, 0] - 1] * st["wQ"] + \
        np.r_[np.nan, sa["dcl"][1:, 1] / sa["dcl"][:-1, 1] - 1] * st["wT"]
    sl = np.nan_to_num(sl)
    eq = np.cumprod(1 + sl)
    fwd = np.full(sa["d"], np.nan)
    fwd[:-20] = eq[20:] / eq[:-20] - 1      # from close of k (state known at k-1 close... see note)
    evm = (st["slope"] > 0.5) & (st["persist"] < 0.3) & np.isfinite(fwd)
    starts = np.flatnonzero(np.diff(np.r_[False, evm].astype(int)) == 1)
    obs = float(np.nanmean(fwd[starts])) if len(starts) else np.nan
    rng = np.random.default_rng(7)
    valid = np.flatnonzero(np.isfinite(fwd) & np.isfinite(st["slope"]))
    sims = np.array([np.nanmean(fwd[rng.choice(valid, len(starts))]) for _ in range(10000)])
    ctrl["episode_bootstrap"] = dict(n_episodes=int(len(starts)), mean_fwd20=obs,
                                     uncond=float(np.nanmean(fwd[valid])),
                                     p=float((sims >= obs).mean()))

    # A4 neighbourhood (brake off, cap off, damper off)
    rb = S.run_one(ts, o, c, S.baseline_weights(sa), 0.0, band=0.0)[1]
    rbase = S.daily_returns(rb["ts"], rb["equity"])
    neigh = []
    for key, vals in (("tilt_strength", (0.15, 0.20, 0.25)), ("slope_scale", (0.30, 0.35, 0.40)),
                      ("base_budget", (0.30, 0.35, 0.40)), ("short_win", (10, 20, 30))):
        for v in vals:
            p = dict(S.P, vol_cap=99.0, persist_damp=0.0)
            p[key] = v
            ww, _ = S.build_weights(ts, o, c, p, brake=False)
            s, r = S.run_one(ts, o, c, ww, 1.0)
            rs = S.daily_returns(r["ts"], r["equity"])
            neigh.append(dict(param=key, value=v, cagr=s["cagr"], dd=s["max_drawdown"],
                              sharpe=s["sharpe"], corr=float(np.corrcoef(rs, rbase)[0, 1])))
    ctrl["A4_neighbourhood"] = neigh

    # cut test on the shipped build_weights (panel truncated at each cut)
    cuts = {}
    for cut in ("2020-03-12 11:07", "2022-09-13 10:41"):
        k = int(ts.searchsorted(pd.Timestamp(cut, tz="America/New_York")))
        wc, _ = S.build_weights(ts[:k], o[:k], c[:k])
        cuts[cut] = dict(bars=k, max_abs_diff_before_cut_minus2=float(np.abs(wc[:k - 2] - w[:k - 2]).max()))
    ctrl["cut_test"] = cuts
    print(json.dumps(ctrl, indent=1, default=float))


if __name__ == "__main__":
    main()
