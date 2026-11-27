"""Tuning diagnostics for ratio-pairs (dev 2016-01-04 .. 2023-12-29 ONLY).

python research/revisit/ratio-pairs/tune.py diag|variants|placebo
Never evaluates any bar after 2023-12-29: the panel itself ends there.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402

bt = S.bt
DEV0, DEV1 = S.DEV_START, S.DEV_END
SUBS = {"2016-19": ("2016-01-04", "2019-12-31"), "2020-21": ("2020-01-02", "2021-12-31"),
        "2022-23": ("2022-01-03", "2023-12-29")}
OUT = {}

ts, op, cl = S.load(S.DEV_END)
assert ts[-1] <= pd.Timestamp("2023-12-29 16:00", tz="America/New_York")
starts, ends = S.session_bounds(ts)


def baseline_warm():
    """165-day QQQ SMA baseline, warmed with 2015 Yahoo closes (measurement only)."""
    q = pd.Series(cl[ends, 0], index=pd.DatetimeIndex(ts[ends]).tz_localize(None).normalize())
    pre = S._pre_panel_daily(q.index[0])["qqq_c"]
    full = pd.concat([pre, q])
    sma = full.rolling(165).mean()
    reg = (full.shift(1) > sma.shift(1)).fillna(False).to_numpy()[len(pre):]
    day = np.zeros((len(starts), 3))
    day[reg, 1] = 1.0
    day[~reg, 2] = 1.0
    return S.broadcast(ts, starts, ends, day)


BASE_OLD = S.baseline_weights(ts, cl)
BASE_WARM = baseline_warm()


def dret(w, lo=DEV0, hi=DEV1, slip=1.0):
    res, s = S.run_window(w, ts, op, cl, lo, hi, slip)
    return S.daily_returns(res), s, res


_bd = {}


def corr(w, base="warm"):
    if base not in _bd:
        _bd[base] = dret(BASE_WARM if base == "warm" else BASE_OLD)[0]
    return float(dret(w)[0].corr(_bd[base]))


def summ(w, slips=(1.0,)):
    out = {}
    for sl in slips:
        _, s, _ = dret(w, slip=sl)
        out[f"{sl:.0f}bp"] = {k: round(float(s[k]), 4) for k in ("cagr", "max_drawdown", "sharpe", "fills")}
    return out


def subp(w):
    return {k: {m: round(float(v), 4) for m, v in dret(w, a, b)[1].items() if m in ("cagr", "max_drawdown", "sharpe")}
            for k, (a, b) in SUBS.items()}


def build(p=S.Params()):
    return S.build_weights(ts, op, cl, p)


def const(q=0.0, t=0.0):
    w = np.zeros((len(ts), 3))
    w[:, 0], w[:, 1], w[:, 2] = q, t, 1 - q - t
    return w


def fmt(x):
    return f"{x*100:6.2f}%"


# --------------------------------------------------------------------------- #
def diag():
    i, j = S.slice_idx(ts, DEV0, DEV1)
    print("dev slice", ts[i], "..", ts[j - 1])
    old_p = replace(S.Params(), daily_warmup=False)
    # --- Step 1: effect of each fix ---------------------------------------
    w_old, info_old = build(old_p)
    w_new, info_new = build()
    # the old slice (drops 12-29)
    jo = int(ts.searchsorted(pd.Timestamp(DEV1, tz="America/New_York"), side="right"))
    r_old = bt.simulate(ts[i:jo], op[i:jo], cl[i:jo], w_old[i:jo], band=0.02, slippage_bps=1.0)
    s_old = bt.stats(r_old, S.BARS_1M)
    print("fix0 original (no warmup, drops 12-29):", fmt(s_old["cagr"]), fmt(s_old["max_drawdown"]), round(s_old["sharpe"], 3))
    s1 = dret(w_old)[1]
    print("fix1 +window incl 12-29            :", fmt(s1["cagr"]), fmt(s1["max_drawdown"]), round(s1["sharpe"], 3))
    s2 = dret(w_new)[1]
    print("fix2 +daily warm-up                :", fmt(s2["cagr"]), fmt(s2["max_drawdown"]), round(s2["sharpe"], 3))
    print("info old", {k: v for k, v in info_old.items() if k != "params"})
    print("info new", {k: v for k, v in info_new.items() if k != "params"})
    diffdays = np.flatnonzero(np.any(w_old[starts] != w_new[starts], axis=1))
    print("sessions whose target changed with warm-up:", len(diffdays),
          "last", ts[starts[diffdays[-1]]].date() if len(diffdays) else None)
    print("corr old-baseline / warm-baseline: fix0w", round(corr(w_old, 'old'), 3), round(corr(w_old), 3),
          " fixed", round(corr(w_new, 'old'), 3), round(corr(w_new), 3))
    OUT["fixes"] = {"orig": [s_old["cagr"], s_old["max_drawdown"], s_old["sharpe"]],
                    "window": [s1["cagr"], s1["max_drawdown"], s1["sharpe"]],
                    "warmup": [s2["cagr"], s2["max_drawdown"], s2["sharpe"]]}

    # sanity: rows sum, finite, the state assignment equals spec
    d = S.ratio_table(ts, cl, starts, ends, S.Params())
    assert len(d) == len(starts)
    assert np.isfinite(w_new).all() and (w_new >= 0).all() and (w_new.sum(1) <= 1 + 1e-12).all()
    # recompute states independently from the spec
    p = S.Params()
    x = np.log(d.tqqq_c / d.qqq_c)
    print("first-dev ext/stress/turn finite:", np.isfinite(d[["ext", "stress", "turn"]].iloc[0].to_numpy()).all())
    # --- Step 2 ------------------------------------------------------------
    w = w_new
    W = w[i:j]
    gross = W[:, 0] + 3 * W[:, 1]
    expo = {"min_TQQQ>0": float((W[:, 1] > 0).mean()), "min_QQQ>0": float((W[:, 0] > 0).mean()),
            "min_BIL_only": float((W[:, 2] >= 0.999).mean()), "min_BIL>0": float((W[:, 2] > 0).mean()),
            "avg_TQQQ_w": float(W[:, 1].mean()), "avg_QQQ_w": float(W[:, 0].mean()),
            "avg_BIL_w": float(W[:, 2].mean()), "avg_gross_lev": float(gross.mean()), "synthetic_short": 0.0}
    print("exposure", {k: round(v, 4) for k, v in expo.items()})
    OUT["exposure"] = expo
    g = expo["avg_gross_lev"]
    mixes = {"strategy": w, "TQQQ@avg_lev (%.3f TQQQ/rest BIL)" % (g / 3): const(t=g / 3),
             "QQQ@avg_lev (%.3f QQQ/rest BIL)" % g: const(q=g), "QQQ 100%": const(q=1.0),
             "QQQ90/BIL10": const(q=0.9), "TQQQ 100%": const(t=1.0)}
    mm = {}
    for k, ww in mixes.items():
        s = dret(ww)[1]
        mm[k] = {"cagr": s["cagr"], "dd": s["max_drawdown"], "sharpe": s["sharpe"], "corr": corr(ww)}
        print(f"  {k:38s} CAGR {fmt(s['cagr'])} DD {fmt(s['max_drawdown'])} Sh {s['sharpe']:.2f} corr {mm[k]['corr']:.2f}")
    OUT["matched"] = mm
    # per-year
    sd = dret(w)[0]
    qd = dret(const(q=1.0))[0]
    td = dret(const(t=1.0))[0]
    bd = dret(BASE_WARM)[0]
    yr = {}
    for y in range(2016, 2024):
        f = lambda r: float((1 + r[r.index.map(lambda t: t.year) == y]).prod() - 1)
        yr[y] = {"strat": f(sd), "tqqq": f(td), "qqq": f(qd), "base165": f(bd)}
        print(y, {k: fmt(v) for k, v in yr[y].items()})
    OUT["years"] = yr
    # state decomposition: daily returns by state
    tgt, _ = S.day_targets(d, S.Params())
    state = np.where(tgt[:, 2] >= 0.999, "cash", np.where(tgt[:, 1] > 0, "deep", "core"))
    days = pd.to_datetime([t.date() for t in ts[ends]])
    st = pd.Series(state, index=days)
    # risk_off split froth vs stress
    ext_p = d["ext"].shift(1).to_numpy()
    st[(state == "cash") & (np.nan_to_num(ext_p, nan=-9) > p.froth)] = "cash_froth"
    st[(state == "cash") & ~(np.nan_to_num(ext_p, nan=-9) > p.froth)] = "cash_stress"
    st.iloc[0] = "first"
    df = pd.DataFrame({"s": sd, "q": qd, "t": td}).dropna()
    # daily_returns drops the first day; align
    df["state"] = st.reindex(df.index).to_numpy()
    lg = np.log1p(df[["s", "q", "t"]])
    dec = lg.groupby(df["state"]).agg(["sum", "count"])
    print("log-return sum by state (strategy / QQQ / TQQQ):")
    print(dec)
    OUT["state_decomp"] = {k: {c: float(lg[df.state == k][c].sum()) for c in "sqt"} | {"n": int((df.state == k).sum())}
                           for k in df.state.unique()}
    up = df.q > 0.01
    print("QQQ up >1% days:", int(up.sum()), "of which in cash:", int((up & df.state.str.startswith("cash")).sum()),
          " missed QQQ log-ret on cash days total:", round(float(lg.q[df.state.str.startswith("cash")].sum()), 4))
    # costs
    c = summ(w, (1.0, 5.0, 10.0))
    yrs = 7.99
    print("costs", c, "fills/yr", round(c["1bp"]["fills"] / yrs, 1))
    _, s1b, r1 = dret(w, slip=1.0)
    print("turnover x/yr", round(r1["turnover"] / yrs, 2))
    _, s0, _ = dret(w, slip=0.0)
    OUT["costs"] = c | {"0bp": s0["cagr"], "turnover_per_yr": r1["turnover"] / yrs}
    # events: episodes of each state
    ev = episodes(st, df)
    OUT["events"] = ev
    json.dump(OUT, open(HERE / "tune_diag.json", "w", newline="\n", encoding="utf-8"), indent=1, default=float)


def episodes(st, df):
    """Episodes = maximal runs of one state. Hit = state beat the QQQ90 core."""
    out = {}
    s = st.reindex(df.index)
    run_id = (s != s.shift()).cumsum()
    lg = np.log1p(df[["s", "q", "t"]])
    core = np.log1p(0.9 * df.q + 0.1 * 0.0)  # BIL ~0 per day; conservative
    rng = np.random.default_rng(7)
    for name in ("cash_froth", "cash_stress", "deep"):
        ids = run_id[s == name].unique()
        edges = []
        for r in ids:
            m = run_id == r
            edges.append(float(lg.s[m].sum() - core[m].sum()))
        edges = np.array(edges)
        if not len(edges):
            continue
        lens = np.array([int((run_id == r).sum()) for r in ids])
        # placebo: same lengths, random start, strategy state replaced -> edge vs core
        n = len(df)
        stat = edges.mean()
        sims = []
        sret = {"cash_froth": np.zeros(n), "cash_stress": np.zeros(n),
                "deep": np.log1p(0.3 * df.q.to_numpy() + 0.4 * df.t.to_numpy())}[name]
        cr = core.to_numpy()
        for _ in range(5000):
            e = []
            for L in lens:
                a = rng.integers(0, n - L)
                e.append(sret[a:a + L].sum() - cr[a:a + L].sum())
            sims.append(np.mean(e))
        p = float((np.array(sims) >= stat).mean())
        out[name] = {"episodes": int(len(ids)), "sessions": int(lens.sum()), "hit_rate": float((edges > 0).mean()),
                     "mean_edge_log": float(stat), "sum_edge_log": float(edges.sum()), "placebo_p": p}
        print(name, {k: round(v, 4) for k, v in out[name].items()})
    return out


# --------------------------------------------------------------------------- #
GRID = {
    "ext_ma": (150, 200, 250), "froth": (0.17, 0.20, 0.23), "deep": (-0.27, -0.30, -0.33),
    "stress_hi": (1.50, 1.75, 2.00), "turn_look": (10, 20, 30), "tqqq_deep": (0.30, 0.40, 0.50),
}


def variants():
    res = {}
    base = S.Params()

    def row(name, p=None, w=None):
        if w is None:
            w, _ = build(p)
        s = summ(w, (1.0, 5.0, 10.0))
        sp = subp(w)
        cc = corr(w)
        res[name] = {"dev": s, "sub": sp, "corr": cc}
        print(f"{name:34s} {fmt(s['1bp']['cagr'])} DD {fmt(s['1bp']['max_drawdown'])} Sh {s['1bp']['sharpe']:.2f} "
              f"corr {cc:.2f} | " + " ".join(f"{k} {fmt(v['cagr'])}/{v['sharpe']:.2f}" for k, v in sp.items()))
        return w

    row("fixed base (pre-registered)", base)
    print("-- +-1 step neighbourhood of the fixed pre-registered rule")
    for k, vals in GRID.items():
        for v in vals:
            if v == getattr(base, k):
                continue
            kw = {k: v}
            if k == "tqqq_deep":
                kw["qqq_deep"] = 0.30
            row(f"  {k}={v}", replace(base, **kw))
    row("  core 100/0", replace(base, qqq_core=1.0, cash_core=0.0))
    row("  core 80/20", replace(base, qqq_core=0.8, cash_core=0.2))
    print("-- pre-registered ablations (promised in report.md, never reported)")
    row("  ablate: no stress rule", replace(base, stress_hi=1e9))
    row("  ablate: no TQQQ sleeve", replace(base, tqqq_deep=0.0, qqq_deep=0.9))
    wq, _ = build(replace(base, froth=1e9, stress_hi=1e9, tqqq_deep=0.0, qqq_deep=0.9))
    row("  ablate: always QQQ90/BIL10", w=wq)
    print("-- improvement candidates (each justified by the leverage-cycle idea)")
    # A: in the deep-and-turning state the hypothesis says leverage is cheap: full 3x-sized sleeve
    for t in (0.4, 0.6, 0.8):
        row(f"A deep sleeve TQQQ {t:.1f}/QQQ{1-t:.1f}", replace(base, tqqq_deep=t, qqq_deep=1 - t))
    # B: core leveraged: the idea says 3x drag is NOT paid in the middle -> negative prior; test anyway
    for t in (0.1, 0.2):
        p = replace(base, qqq_core=0.9 - t * 3 if 0.9 - 3 * t >= 0 else 0, cash_core=0.1)
        w, _ = build(base)
        # rebuild core rows with TQQQ t, QQQ 0.9-t
        w2 = w.copy()
        core = (np.abs(w[:, 0] - 0.9) < 1e-12) & (w[:, 1] == 0)
        w2[core] = (0.9 - t, t, 0.1)
        row(f"B core QQQ{0.9-t:.1f}+TQQQ{t:.1f}", w=w2)
    OUT["variants"] = res
    json.dump(res, open(HERE / "tune_variants.json", "w", newline="\n", encoding="utf-8"), indent=1, default=float)


def placebo():
    """Random BIL days with the same per-year count as the real risk-off state."""
    w, _ = build()
    d = S.ratio_table(ts, cl, starts, ends, S.Params())
    tgt, _ = S.day_targets(d, S.Params())
    real = dret(w)[1]
    yrs = np.array([t.year for t in ts[starts]])
    cash = tgt[:, 2] >= 0.999
    deep = tgt[:, 1] > 0
    rng = np.random.default_rng(11)
    ws = []
    for _ in range(300):
        t2 = np.tile((0.9, 0.0, 0.1), (len(tgt), 1))
        for y in np.unique(yrs):
            idx = np.flatnonzero((yrs == y) & ~deep)
            # keep run structure: random circular shift of that year's cash mask
            m = cash[idx]
            m = np.roll(m, rng.integers(0, len(m)))
            t2[idx[m]] = (0, 0, 1)
        t2[deep] = tgt[deep]
        t2[0] = (0, 0, 1)
        ws.append(S.broadcast(ts, starts, ends, t2))
    i, j = S.slice_idx(ts, DEV0, DEV1)
    out = []
    for k in range(0, len(ws), 20):
        rs = bt.simulate_many(ts[i:j], op[i:j], cl[i:j], [x[i:j] for x in ws[k:k + 20]], band=0.02, slippage_bps=1.0, threads=1)
        out += [bt.stats(r, S.BARS_1M) for r in rs]
    cg = np.array([s["cagr"] for s in out])
    sh = np.array([s["sharpe"] for s in out])
    dd = np.array([s["max_drawdown"] for s in out])
    print(f"real CAGR {fmt(real['cagr'])} Sh {real['sharpe']:.2f} DD {fmt(real['max_drawdown'])}")
    print(f"placebo (300, circular-shifted cash days per year) CAGR median {fmt(np.median(cg))} "
          f"share>=real {np.mean(cg >= real['cagr']):.3f}; Sharpe median {np.median(sh):.2f} share>=real {np.mean(sh >= real['sharpe']):.3f}; "
          f"DD median {fmt(np.median(dd))} share<=real {np.mean(dd <= real['max_drawdown']):.3f}")
    json.dump({"cagr": cg.tolist(), "sharpe": sh.tolist(), "dd": dd.tolist(), "real": real},
              open(HERE / "tune_placebo.json", "w", newline="\n", encoding="utf-8"), default=float)


if __name__ == "__main__":
    {"diag": diag, "variants": variants, "placebo": placebo}[sys.argv[1]]()
