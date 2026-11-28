"""Robustness for `family-autocorrelation-regime` (development window only).

Regenerates `robustness.json`:
  * full 30-cell parameter grid at 1 bp;
  * subperiods for the primary and the passing cells;
  * 300-shift circular-shift placebo (target and AC);
  * 100-draw random-gate placebo;
  * weekly decision clock (weekly AC and daily AC sampled weekly);
  * cash-vs-BIL cost sensitivity;
  * no-gate reversal comparison.

Run:
    $env:BT_THREADS = "1"
    python research/new/family-autocorrelation-regime/robustness.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2] / "research"))

import bt  # noqa: E402
import strategy as st  # noqa: E402


def grid_block(ts, o, c):
    cells = []
    for L in (60, 120, 250):
        for tc in (0.00, 0.03, 0.05):
            for tr in (0.05, 0.10, 0.15):
                cells.append((L, tc, tr, 3))
    for h in (1, 2, 5):
        cells.append((120, 0.03, 0.05, h))
    out = []
    for L, tc, tr, h in cells:
        p = dict(L=L, lag=1, theta_cont=tc, theta_rev=tr, hold=h)
        w = st.build_weights_p(ts, o, c, p)
        s, _, _ = st.stats_block(ts, o, c, w, 1.0)
        s.update(L=L, theta_cont=tc, theta_rev=tr, hold=h,
                 tqqq_exposure=float(w[:, 1].mean()),
                 passes_bar=bool(s["cagr"] > st.BAR["cagr"] and s["max_drawdown"] < st.BAR["max_dd"]))
        out.append(s)
    return out


def subperiods_for(ts, o, c, params):
    w = st.build_weights_p(ts, o, c, params)
    return st.subperiod_block(ts, o, c, w)


def placebo_block(ts, o, c, tgt, rho, qret, n=300, seed=99):
    rng = np.random.default_rng(seed)
    nd = len(tgt)
    true, _, _ = st.stats_block(ts, o, c, st.broadcast(ts, tgt), 1.0)
    true_cagr = true["cagr"]

    def draw(kind):
        vals = []
        for k in rng.integers(30, nd - 30, n):
            k = int(k)
            if kind == "target":
                t = np.roll(tgt, k)
            elif kind == "ac":
                t, _ = st.target_series(np.roll(rho, k), qret, st.PARAMS)
            else:  # random gate: shuffle the AC values, preserving the marginal
                t, _ = st.target_series(rng.permutation(rho), qret, st.PARAMS)
            s, _, _ = st.stats_block(ts, o, c, st.broadcast(ts, t), 1.0)
            vals.append(s["cagr"])
        v = np.asarray(vals)
        return dict(n=int(len(v)), mean=float(v.mean()), median=float(np.median(v)),
                    p5=float(np.percentile(v, 5)), p95=float(np.percentile(v, 95)),
                    true=float(true_cagr), percentile=float((v < true_cagr).mean()),
                    p_one_sided=float((np.sum(v >= true_cagr) + 1) / (len(v) + 1)))

    return {k: draw(k) for k in ("target", "ac", "random")}


def _weekly_state(sess_dates, qc, acw, wret, ct, rt):
    stt = (acw >= ct) | ((acw <= -rt) & (wret < 0))
    tgt = np.zeros(len(sess_dates))
    fridays = stt.index
    for i, friday in enumerate(fridays):
        if not np.isfinite(stt.iloc[i]):
            continue
        start = int(np.searchsorted(sess_dates, friday + pd.Timedelta(days=1)))
        if i + 1 < len(fridays):
            end = int(np.searchsorted(sess_dates, fridays[i + 1] + pd.Timedelta(days=1)))
        else:
            end = len(sess_dates)
        tgt[start:end] = 1.0 if bool(stt.iloc[i]) else 0.0
    return tgt


def weekly_block(ts, o, c, sess_dates, qc, ac_daily):
    sd = pd.to_datetime(sess_dates)
    ser = pd.Series(qc, index=sd)
    wk = ser.resample("W-FRI").last()
    wret = wk.pct_change()
    rows = []
    for source in ("weekly_ac", "daily_ac"):
        for Lw in (20, 26, 39, 52):
            if source == "weekly_ac":
                acw = pd.Series(wret).rolling(Lw).apply(
                    lambda a: np.corrcoef(a[:-1], a[1:])[0, 1], raw=True)
                acw.index = wk.index
            else:
                acw = pd.Series(ac_daily, index=sd).resample("W-FRI").last()
            for ct in (0.00, 0.03, 0.05):
                for rt in (0.05, 0.10, 0.15):
                    tgt = _weekly_state(sd, qc, acw, wret, ct, rt)
                    s, _, _ = st.stats_block(ts, o, c, st.broadcast(ts, tgt), 1.0)
                    rows.append(dict(source=source, Lw=Lw, theta_cont=ct, theta_rev=rt,
                                     cagr=s["cagr"], max_drawdown=s["max_drawdown"],
                                     sharpe=s["sharpe"], fills=s["fills"],
                                     tqqq_exposure=float(tgt.mean()),
                                     passes_bar=bool(s["cagr"] > st.BAR["cagr"] and s["max_drawdown"] < st.BAR["max_dd"])))
    return rows


def cash_block(ts, o, c, tgt):
    out = {}
    for use_bil in (True, False):
        w = st.broadcast(ts, tgt)
        if not use_bil:
            w[:, 2] = 0.0
        row = {}
        for bp in (0.0, 1.0, 5.0, 10.0):
            s, _, _ = st.stats_block(ts, o, c, w, bp) if use_bil else (None, None, None)
            if not use_bil:
                res = st.run_range(ts, o, c, w, bp=bp)
                s = bt.stats(res, st.BARS_PER_YEAR)
                s = dict(cagr=float(s["cagr"]), max_drawdown=float(s["max_drawdown"]),
                         sharpe=float(s["sharpe"]), fills=int(s["fills"]),
                         turnover=float(s["turnover"]), ending_equity=float(s["ending_equity"]))
            row[f"{bp:g}bp"] = s
        out["bil" if use_bil else "cash"] = row
    return out


def main():
    ts, o, c = st.load_panel()
    f = st.daily_features(ts, c)
    rho = st.rolling_ac(f["all_ret"], f["off"], st.PARAMS["L"], st.PARAMS["lag"])
    tgt, info = st.target_series(rho, f["qret"], st.PARAMS)
    sess_dates = f["dates"][f["last"]]

    grid = grid_block(ts, o, c)
    primary = dict(st.PARAMS)
    subs = subperiods_for(ts, o, c, primary)
    passing_subs = {}
    for x in grid:
        if x["passes_bar"]:
            p = dict(L=x["L"], lag=1, theta_cont=x["theta_cont"],
                     theta_rev=x["theta_rev"], hold=x["hold"])
            passing_subs[f"L{x['L']}_c{x['theta_cont']:.2f}_r{x['theta_rev']:.2f}_h{x['hold']}"] = \
                subperiods_for(ts, o, c, p)

    placebo = placebo_block(ts, o, c, tgt, rho, f["qret"], n=300)
    weekly = weekly_block(ts, o, c, sess_dates, f["qc"], rho)
    cash = cash_block(ts, o, c, tgt)

    # no-gate reversal comparison
    rev_ng = f["qret"] < 0
    held_ng = rev_ng.copy()
    for k in range(1, int(st.PARAMS["hold"])):
        held_ng[k:] |= rev_ng[:-k]
    t_ng = np.zeros(len(rho))
    t_ng[1:] = held_ng[:-1]
    ng, _, _ = st.stats_block(ts, o, c, st.broadcast(ts, t_ng), 1.0)
    ng_subs = st.subperiod_block(ts, o, c, st.broadcast(ts, t_ng))

    best_weekly = max(weekly, key=lambda r: r["cagr"])
    out = dict(
        agent="family-autocorrelation-regime",
        window=[st.DEV_START, st.DEV_END],
        grid=grid,
        grid_summary=dict(cells=len(grid), passes=sum(1 for x in grid if x["passes_bar"]),
                          core_cells=sum(1 for x in grid if x["hold"] == 3 and x["L"] == 120),
                          core_passes=sum(1 for x in grid if x["hold"] == 3 and x["L"] == 120 and x["passes_bar"])),
        subperiods_primary=subs,
        subperiods_passing=passing_subs,
        placebo=placebo,
        weekly=weekly,
        weekly_summary=dict(cells=len(weekly), passes=sum(1 for r in weekly if r["passes_bar"]),
                            best=best_weekly),
        cash_vs_bil=cash,
        reversal_no_gate=dict(stats=ng, subperiods=ng_subs),
    )
    with open(HERE / "robustness.json", "w") as fh:
        json.dump(st.clean(out), fh, indent=1)

    print("grid %d cells, %d pass (core %d/%d)" % (
        out["grid_summary"]["cells"], out["grid_summary"]["passes"],
        out["grid_summary"]["core_passes"], out["grid_summary"]["core_cells"]))
    print("placebo p: target %.3f  ac %.3f  random %.3f" % (
        placebo["target"]["p_one_sided"], placebo["ac"]["p_one_sided"],
        placebo["random"]["p_one_sided"]))
    print("weekly %d cells, %d pass; best %.2f%% (Lw=%d %s c%+.2f r-%.2f)" % (
        out["weekly_summary"]["cells"], out["weekly_summary"]["passes"],
        best_weekly["cagr"] * 100, best_weekly["Lw"], best_weekly["source"],
        best_weekly["theta_cont"], best_weekly["theta_rev"]))
    print("wrote", HERE / "robustness.json")


if __name__ == "__main__":
    main()
