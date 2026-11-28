"""Robustness / placebo tests for the volume-clock family.

Writes robustness.json.  Development window only.

Tests
-----
1. Circular-shift placebo: shift the per-session acceleration series by a
   random number of sessions, keep the same state machine and thresholds.
2. Random-night placebo: hold TQQQ overnight on the same number of randomly
   chosen sessions (594), no signal.
3. Random-time placebo: draw a random decision offset in 10:30-15:00 for every
   session, compute the same 30-minute acceleration at that offset, and run the
   same state machine.
4. Stale signal: use the prior session's acceleration.
5. Block bootstrap of daily returns.
6. Ex-2020 and ex-top-10-night return attribution.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    $env:BT_THREADS = "1"
    python research/new/family-volume-clock/robustness.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as st  # noqa: E402

DEV_START, DEV_END = st.DEV_START, st.DEV_END
BPY = st.BPY
CT, CB = st.CT, st.CB


def ev(ts, o, c, w, slip=1.0):
    r, s = st.run_w(ts, o, c, w, slip=slip)
    return s, r


def main():
    ts, o, c, vol = st.load_panel()
    dates, first, last = st.bt.day_bounds(ts)
    n = len(first)
    accel = st.volume_acceleration(ts, vol, st.DEC_MIN, st.WIN_MIN, st.LOOK)
    w, diag = st.build_weights(ts, o, c, accel=accel, return_diag=True)
    s_real, r_real = ev(ts, o, c, w, 1.0)
    real = {"cagr": s_real["cagr"], "sharpe": s_real["sharpe"],
            "dd": s_real["max_drawdown"], "fills": s_real["fills"]}
    print("real", {k: round(float(v), 4) for k, v in real.items()})

    rng = np.random.default_rng(20261127)
    out = {"real": real, "centre": {"dec_min": st.DEC_MIN, "enter": st.ENTER,
                                     "exit": st.EXIT, "win": st.WIN_MIN,
                                     "look": st.LOOK}}

    # ---------------- 1. circular shift ----------------
    print("circular-shift placebo ...")
    cagrs, shs, dds = [], [], []
    for L in rng.integers(1, 500, 200):
        ash = np.r_[np.full(int(L), np.nan), accel[:-int(L)]]
        wsh, _ = st.build_weights(ts, o, c, accel=ash, return_diag=True)
        s, _ = ev(ts, o, c, wsh, 1.0)
        cagrs.append(s["cagr"]); shs.append(s["sharpe"]); dds.append(s["max_drawdown"])
    cagrs = np.array(cagrs); shs = np.array(shs); dds = np.array(dds)
    out["circular_shift"] = {
        "n_draws": 200, "real_cagr": real["cagr"], "real_sharpe": real["sharpe"],
        "real_dd": real["dd"],
        "mean_cagr": float(cagrs.mean()), "p95_cagr": float(np.percentile(cagrs, 95)),
        "max_cagr": float(cagrs.max()), "p_cagr": float(np.mean(cagrs >= real["cagr"])),
        "mean_sharpe": float(shs.mean()), "p95_sharpe": float(np.percentile(shs, 95)),
        "max_sharpe": float(shs.max()), "p_sharpe": float(np.mean(shs >= real["sharpe"])),
        "mean_dd": float(dds.mean()), "p05_dd": float(np.percentile(dds, 5)),
    }
    print("  ", {k: round(float(v), 4) for k, v in out["circular_shift"].items()})

    # ---------------- 2. random nights ----------------
    print("random-night placebo ...")
    n_entries = int(diag["traded"])
    cagrs2, shs2, dds2 = [], [], []
    for _ in range(200):
        pick = rng.choice(n, size=n_entries, replace=False)
        mask = np.zeros(n, dtype=bool); mask[pick] = True
        wr, _ = st.weights_from_mask(ts, mask, st.DEC_MIN)
        s, _ = ev(ts, o, c, wr, 1.0)
        cagrs2.append(s["cagr"]); shs2.append(s["sharpe"]); dds2.append(s["max_drawdown"])
    cagrs2 = np.array(cagrs2); shs2 = np.array(shs2); dds2 = np.array(dds2)
    out["random_nights"] = {
        "n_draws": 200, "n_nights": n_entries,
        "mean_cagr": float(cagrs2.mean()), "p95_cagr": float(np.percentile(cagrs2, 95)),
        "max_cagr": float(cagrs2.max()), "p_cagr": float(np.mean(cagrs2 >= real["cagr"])),
        "mean_sharpe": float(shs2.mean()), "p95_sharpe": float(np.percentile(shs2, 95)),
        "max_sharpe": float(shs2.max()), "p_sharpe": float(np.mean(shs2 >= real["sharpe"])),
        "mean_dd": float(dds2.mean()), "p05_dd": float(np.percentile(dds2, 5)),
    }
    print("  ", {k: round(float(v), 4) for k, v in out["random_nights"].items()})

    # ---------------- 3. random decision time ----------------
    print("random-time placebo ...")
    V = np.zeros((n, 390))
    for k in range(n):
        f, l = int(first[k]), int(last[k])
        m = min(l - f + 1, 390)
        V[k, :m] = vol[f:f + m]
    CUM = np.cumsum(V, axis=1)

    def accel_at_random_times(jdraw):
        a = np.full(n, np.nan)
        for k in range(st.LOOK, n):
            j = int(jdraw[k])
            m = min(int(last[k]) - int(first[k]) + 1, 390)
            if j < 30 or j >= m - 1:
                continue
            cur = CUM[k, j] - CUM[k, j - 30]
            hist = CUM[k - st.LOOK:k, j] - CUM[k - st.LOOK:k, j - 30]
            med = float(np.median(hist))
            if med > 0:
                a[k] = cur / med
        return a

    cagrs3, shs3, dds3, ents3 = [], [], [], []
    for _ in range(100):
        jdraw = rng.integers(60, 331, n)   # 10:30 .. 15:00
        a = accel_at_random_times(jdraw)
        w3, d3 = st.build_weights(ts, o, c, accel=a, return_diag=True)
        s, _ = ev(ts, o, c, w3, 1.0)
        cagrs3.append(s["cagr"]); shs3.append(s["sharpe"]); dds3.append(s["max_drawdown"])
        ents3.append(d3["traded"])
    cagrs3 = np.array(cagrs3); shs3 = np.array(shs3); dds3 = np.array(dds3)
    out["random_time"] = {
        "n_draws": 100, "offset_range": [60, 330],
        "mean_entries": float(np.mean(ents3)),
        "mean_cagr": float(cagrs3.mean()), "p95_cagr": float(np.percentile(cagrs3, 95)),
        "max_cagr": float(cagrs3.max()), "p_cagr": float(np.mean(cagrs3 >= real["cagr"])),
        "mean_sharpe": float(shs3.mean()), "p95_sharpe": float(np.percentile(shs3, 95)),
        "max_sharpe": float(shs3.max()), "p_sharpe": float(np.mean(shs3 >= real["sharpe"])),
        "mean_dd": float(dds3.mean()), "p05_dd": float(np.percentile(dds3, 5)),
    }
    print("  ", {k: (round(float(v), 4) if not isinstance(v, list) else v)
                  for k, v in out["random_time"].items()})

    # ---------------- 4. stale signal ----------------
    print("stale signal ...")
    astale = np.r_[np.nan, accel[:-1]]
    wst, _ = st.build_weights(ts, o, c, accel=astale, return_diag=True)
    sst, _ = ev(ts, o, c, wst, 1.0)
    out["stale_signal"] = {k: float(sst[k]) for k in
                           ("cagr", "max_drawdown", "sharpe", "fills", "turnover")}
    out["stale_signal"]["retained_cagr_fraction"] = float(sst["cagr"] / real["cagr"]) if real["cagr"] else 0.0
    print("  ", {k: round(float(v), 4) for k, v in out["stale_signal"].items()})

    # ---------------- 5. block bootstrap ----------------
    print("block bootstrap ...")
    dr = st.daily_returns(r_real).to_numpy()
    block = 10
    n_blocks = int(np.ceil(len(dr) / block))
    boot_cagr, boot_sh, boot_dd = [], [], []
    for _ in range(1000):
        starts = rng.integers(0, len(dr) - block, n_blocks)
        sample = np.concatenate([dr[s:s + block] for s in starts])[:len(dr)]
        eq = np.cumprod(1.0 + sample)
        years = len(sample) / 252.0
        peak = np.maximum.accumulate(eq)
        boot_cagr.append(eq[-1] ** (1 / years) - 1)
        boot_sh.append(sample.mean() / sample.std(ddof=0) * np.sqrt(252))
        boot_dd.append(-(eq / peak - 1).min())
    out["block_bootstrap"] = {
        "n_draws": 1000, "block_days": block,
        "cagr_p05": float(np.percentile(boot_cagr, 5)),
        "cagr_p50": float(np.percentile(boot_cagr, 50)),
        "cagr_p95": float(np.percentile(boot_cagr, 95)),
        "sharpe_p05": float(np.percentile(boot_sh, 5)),
        "sharpe_p50": float(np.percentile(boot_sh, 50)),
        "sharpe_p95": float(np.percentile(boot_sh, 95)),
        "dd_p50": float(np.percentile(boot_dd, 50)),
        "dd_p95": float(np.percentile(boot_dd, 95)),
    }
    print("  ", {k: round(float(v), 4) for k, v in out["block_bootstrap"].items()})

    # ---------------- 6. ex-2020 and ex-top nights ----------------
    print("ex-2020 / ex-top nights ...")
    eq = st.daily_curve(r_real)
    r_all = eq.pct_change().dropna()
    def curve_stats(r):
        eqx = np.cumprod(1.0 + r.to_numpy())
        years = len(r) / 252.0
        peak = np.maximum.accumulate(eqx)
        return {"cagr": float(eqx[-1] ** (1 / years) - 1),
                "max_drawdown": float(-(eqx / peak - 1).min()),
                "sharpe": float(r.mean() / r.std(ddof=0) * np.sqrt(252))}
    ex2020 = r_all[r_all.index.year != 2020]
    ex2021 = r_all[r_all.index.year != 2021]
    out["ex_year"] = {"ex_2020": curve_stats(ex2020), "ex_2021": curve_stats(ex2021)}

    # top / worst entry nights by strategy daily P&L contribution
    # identify the 10 best single-day strategy returns and remove them
    top10 = r_all.nlargest(10)
    r_ex_top = r_all.drop(top10.index)
    out["ex_top10_days"] = {
        "removed_days": [str(d.date()) for d in top10.index],
        "removed_returns": [float(v) for v in top10.to_numpy()],
        **curve_stats(r_ex_top),
    }
    print("  ex2020", {k: round(float(v), 4) for k, v in out["ex_year"]["ex_2020"].items()})
    print("  ex-top10", {k: round(float(v), 4) for k, v in out["ex_top10_days"].items()
                         if k not in ("removed_days", "removed_returns")})

    (HERE / "robustness.json").write_text(json.dumps(out, indent=2, default=float),
                                          encoding="utf-8")
    print("wrote", HERE / "robustness.json")


if __name__ == "__main__":
    main()
