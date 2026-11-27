"""Tune-brief sizing sweep and controls (dev only, 2016-01-04 -> 2023-12-29).

    python research/revisit/event-risk-overlay/tune_sweep.py

Family tried (declared before running): the pre-registered window is kept
fixed; only the vol rule that sizes the window changes.
  step   : halve when QQQ rv20 > thr, thr in {0.20, 0.25, 0.30} (original)
  target : size = min(1, target / rvN), target in {0.15, 0.20, 0.25, 0.30},
           N in {10, 20, 40}
Controls: random-anchor calendars (one random session per month as the
anchor, same offsets, same sizing), and an always-in TQQQ series with the
same vol sizing scaled to the same average TQQQ weight.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
import bt  # noqa: E402
import strategy as S  # noqa: E402

DEV0, DEV1 = "2016-01-04", "2023-12-29"
BY = 252 * 390
SUBS = (("2016-01-04", "2019-12-31"), ("2020-01-02", "2021-12-31"), ("2022-01-03", "2023-12-29"))


def win(ts, lo, hi):
    i = bt.start_index(ts, lo)
    j = int(ts.searchsorted(pd.Timestamp(hi, tz="America/New_York") + pd.Timedelta(days=1)))
    return i, j


def run(ts, o, c, w, lo=DEV0, hi=DEV1, slip=1.0):
    i, j = win(ts, lo, hi)
    return bt.simulate(ts[i:j], o[i:j], c[i:j], w[i:j], band=0.02, slippage_bps=slip)


def daily(r):
    eq = pd.Series(r["equity"], index=r["ts"])
    return eq.groupby(eq.index.date).last().pct_change().dropna()


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1min")
    assert ts[-1].date() <= pd.Timestamp(DEV1).date()
    ref = S.reference_165d_daily_returns(ts, c)
    dates = bt.session_dates(ts)
    first, last = S.day_bounds(dates)
    sess = dates[first]

    caps = {"step_0.20": {"on": True, "n": 20, "thr": 0.20, "size": 0.5},
            "step_0.25 (orig)": dict(S.VOL_CAP) | {"mode": "step"},
            "step_0.30": {"on": True, "n": 20, "thr": 0.30, "size": 0.5},
            "none": {"on": False, "n": 20, "thr": 0.25, "size": 0.5}}
    for n in (10, 20, 40):
        for t in (0.15, 0.20, 0.25, 0.30):
            caps[f"tgt_{t:.2f}_n{n}"] = {"on": True, "mode": "target", "n": n, "target": t}

    rows = {}
    W = {}
    for name, cap in caps.items():
        w, info = S.build_weights(ts, o, c, vol_cap=cap)
        W[name] = w
        out = {}
        for slip in (1.0, 5.0, 10.0):
            r = run(ts, o, c, w, slip=slip)
            s = bt.stats(r, BY)
            out[f"{int(slip)}bp"] = (s["cagr"], s["max_drawdown"], s["sharpe"])
            if slip == 1.0:
                d = daily(r)
                jj = ref.index.intersection(d.index)
                out["corr"] = float(np.corrcoef(ref.loc[jj], d.loc[jj])[0, 1])
                out["mean_tqqq_w"] = float(w[bt.start_index(ts, DEV0):, 1].mean())
        for lo, hi in SUBS:
            s = bt.stats(run(ts, o, c, w, lo, hi), BY)
            out[lo[:4] + "-" + hi[:4]] = (s["cagr"], s["max_drawdown"], s["sharpe"])
        rows[name] = out

    print(f"{'variant':18s} {'1bp cagr/dd/sh':22s} {'5bp':8s} {'10bp':8s} corr  meanW  "
          f"16-19 cagr/dd   20-21 cagr/dd   22-23 cagr/dd")
    for k, v in rows.items():
        a = v["1bp"]
        print(f"{k:18s} {a[0]:6.1%} {a[1]:6.1%} {a[2]:5.2f}  {v['5bp'][0]:6.1%} {v['10bp'][0]:6.1%} "
              f"{v['corr']:.2f} {v['mean_tqqq_w']:.3f}  "
              + "  ".join(f"{v[p][0]:6.1%}/{v[p][1]:5.1%}" for p in ("2016-2019", "2020-2021", "2022-2023")))

    # ---- controls -------------------------------------------------------
    rng = np.random.default_rng(2026)
    ym = np.array([d.year * 12 + d.month for d in sess])
    groups = [np.flatnonzero(ym == m) for m in np.unique(ym)]
    ctrl_caps = ["step_0.25 (orig)", "tgt_0.20_n20", "none"]
    ctrl = {}
    for cname in ctrl_caps:
        st = []
        for _ in range(10):                      # 10 batches x 20 calendars (memory)
            ws = []
            for _ in range(20):
                anchors = np.array([rng.choice(g) for g in groups])
                ws.append(S.build_weights(ts, o, c, vol_cap=caps[cname], anchors=anchors)[0])
            res = bt.run_many(ts, o, c, ws, start=DEV0, band=0.02, slippage_bps=1.0)
            st += [bt.stats(r, BY) for r in res]
            del ws, res
        cg = np.array([s["cagr"] for s in st])
        sh = np.array([s["sharpe"] for s in st])
        dd = np.array([s["max_drawdown"] for s in st])
        obs = rows[cname]["1bp"]
        ctrl[cname] = {"obs_cagr": obs[0], "obs_sharpe": obs[2],
                       "placebo_cagr_median": float(np.median(cg)),
                       "placebo_cagr_p95": float(np.percentile(cg, 95)),
                       "p_cagr": float((cg >= obs[0]).mean()),
                       "p_sharpe": float((sh >= obs[2]).mean()),
                       "placebo_dd_median": float(np.median(dd))}

    # always-in TQQQ, same sizing rule, scaled to the same mean weight
    qc = c[last, 0]
    lr = np.r_[np.nan, np.diff(np.log(qc))]
    for cname in ("tgt_0.20_n20", "step_0.25 (orig)"):
        cap = caps[cname]
        rv = pd.Series(lr).rolling(cap["n"]).std().to_numpy() * np.sqrt(252)
        rvp = np.r_[np.nan, rv[:-1]]
        if cap.get("mode") == "target":
            sc = np.where(np.isfinite(rvp), np.minimum(1, cap["target"] / np.where(rvp > 0, rvp, 1)), 1.0)
        else:
            sc = np.where(np.isfinite(rvp) & (rvp > cap["thr"]), cap["size"], 1.0)
        per_bar = np.empty(len(ts))
        for k in range(len(first)):
            a = 0 if k == 0 else last[k - 1]
            per_bar[a:last[k] + 1] = sc[k]
        i0 = bt.start_index(ts, DEV0)
        kfac = rows[cname]["mean_tqqq_w"] / per_bar[i0:].mean()
        w = np.zeros((len(ts), 3))
        w[:, 1] = np.clip(kfac * per_bar, 0, 1)
        w[:, 2] = 1 - w[:, 1]
        r = run(ts, o, c, w)
        s = bt.stats(r, BY)
        d = daily(r)
        jj = ref.index.intersection(d.index)
        ctrl["always_in_" + cname] = {"k": float(kfac), "cagr": s["cagr"], "max_drawdown": s["max_drawdown"],
                                      "sharpe": s["sharpe"],
                                      "corr": float(np.corrcoef(ref.loc[jj], d.loc[jj])[0, 1])}
    print(json.dumps(ctrl, indent=1))
    (HERE / "tune_sweep.json").open("w", newline="\n", encoding="utf-8").write(
        json.dumps({"rows": rows, "controls": ctrl}, indent=1, default=float))


if __name__ == "__main__":
    main()
