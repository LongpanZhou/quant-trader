"""relative-value-tqqq: TQQQ/QQQ ratio-momentum + volatility-scaled sleeve.

Pre-registered in HYPOTHESIS.md.  Development window only:
2016-01-04 .. 2023-12-29.  The 2024-2026 holdout is never loaded.

Rule (decided on session t's close, held through session t+1):

    R_t = TQQQ_close_t / QQQ_close_t
    mom_t = log(R_t) - log(R_{t-n})
    v_t   = 20-session realised vol of QQQ daily log returns * sqrt(252)

    w_tqqq = clip((v_hi - v_t) / (v_hi - v_lo), 0, 1)   if mom_t > mom_min
           = 0                                          otherwise
    w_qqq  = 1 - w_tqqq

No moving average of QQQ, no price stop, no ratio froth/discount level.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
BARS_1M = 252 * 390
DEV_START, DEV_END = "2016-01-04", "2023-12-29"
SYMS = ("QQQ", "TQQQ", "BIL")
COL = {"QQQ": 0, "TQQQ": 1, "BIL": 2}

BAR = {"cagr": 0.3672, "max_drawdown": 0.8229, "sharpe": 0.82}


@dataclass(frozen=True)
class Params:
    n: int = 100            # ratio-momentum lookback (sessions)
    mom_min: float = -0.10  # hold TQQQ only if ratio momentum is above this
    v_lo: float = 0.30      # QQQ vol at/below which TQQQ weight is 1
    v_hi: float = 0.40      # QQQ vol at/above which TQQQ weight is 0


# --------------------------------------------------------------------------- #
# panel and daily signal table
# --------------------------------------------------------------------------- #
def load_panel():
    return bt.panel(SYMS, DEV_START, DEV_END, "1min", warmup_days=420)


def _pre_panel_daily(first_day: pd.Timestamp) -> pd.DataFrame:
    """Yahoo adjusted closes strictly before the panel starts (warmup only)."""
    cols = {}
    for sym, name in (("QQQ", "qqq_c"), ("TQQQ", "tqqq_c"), ("BIL", "bil_c")):
        path = ROOT / "data" / "intraday-hf" / f"{sym}-1d-yahoo.parquet"
        d = pd.read_parquet(
            path, columns=["date", "adjclose"],
            filters=[("date", "<", pd.Timestamp(first_day).normalize())],
        )
        idx = pd.to_datetime(d["date"]).dt.normalize()
        cols[name] = pd.Series(d["adjclose"].to_numpy(), index=idx)
    pre = pd.DataFrame(cols).dropna()
    return pre[pre.index < pd.Timestamp(first_day).normalize()]


def daily_table(ts: pd.DatetimeIndex, closes: np.ndarray) -> pd.DataFrame:
    """One row per session: QQQ/TQQQ closes and the two causal signals."""
    _, starts, ends = bt.day_bounds(ts)
    dates = pd.DatetimeIndex(ts[ends]).tz_localize(None).normalize()
    d = pd.DataFrame(
        {"qqq_c": closes[ends, COL["QQQ"]],
         "tqqq_c": closes[ends, COL["TQQQ"]],
         "bil_c": closes[ends, COL["BIL"]]},
        index=dates,
    )
    n_sess = len(d)
    d = pd.concat([_pre_panel_daily(d.index[0]), d])
    d["logr"] = np.log(d["tqqq_c"] / d["qqq_c"])
    d["v20"] = np.log(d["qqq_c"]).diff().rolling(20).std() * np.sqrt(252)
    d["qm100"] = np.log(d["qqq_c"]).diff(100)
    # Realised-variance change over the same 100 sessions (identity diagnostic).
    d["cumvar"] = (np.log(d["qqq_c"]).diff() ** 2).cumsum()
    d["dvar100"] = d["cumvar"] - d["cumvar"].shift(100)
    return d, n_sess


def signal_weights(d: pd.DataFrame, n_sess: int, p: Params,
                   signal: str = "ratio", mode: str = "scale") -> tuple[np.ndarray, pd.DataFrame]:
    """Per-session TQQQ target.  Day k uses the signal from session k-1."""
    # Compute on the full spliced series (2015 warmup included), then slice.
    d = d.copy()
    d["rm"] = d["logr"] - d["logr"].shift(p.n)
    tab = d.iloc[len(d) - n_sess:].copy()
    vol = tab["v20"].to_numpy()
    mom = tab["rm" if signal == "ratio" else "qm100"].to_numpy()
    ok = np.nan_to_num(mom, nan=-9.0) > p.mom_min
    if mode == "scale":
        tw = np.clip((p.v_hi - vol) / (p.v_hi - p.v_lo), 0.0, 1.0)
    elif mode == "binary":
        tw = (vol < p.v_hi).astype(float)
    else:
        tw = np.ones(n_sess)
    tw = np.where(ok, tw, 0.0)
    tw = np.where(np.isfinite(tw), tw, 0.0)
    # No prior panel session for day 0 -> stay in QQQ; day k uses day k-1.
    tw = np.r_[0.0, tw[:-1]]
    return tw, tab


def broadcast(ts: pd.DatetimeIndex, tw: np.ndarray) -> np.ndarray:
    _, starts, ends = bt.day_bounds(ts)
    w = np.zeros((len(ts), 3))
    for k, (a, b) in enumerate(zip(starts, ends)):
        w[a:b + 1, COL["TQQQ"]] = tw[k]
        w[a:b + 1, COL["QQQ"]] = 1.0 - tw[k]
    return w


def build_weights(ts, opens, closes, params: Params | None = None,
                  return_info: bool = False):
    """Required entry point.  Returns (n_bars, 3) QQQ/TQQQ/BIL weights."""
    p = params or Params()
    d, n_sess = daily_table(ts, closes)
    tw, tab = signal_weights(d, n_sess, p)
    w = broadcast(ts, tw)
    if not return_info:
        return w
    info = {
        "params": asdict(p),
        "sessions": int(n_sess),
        "tqqq_sessions": int((tw > 0).sum()),
        "tqqq_session_share": float((tw > 0).mean()),
        "full_tqqq_sessions": int((tw >= 1.0 - 1e-12).sum()),
        "avg_tqqq_weight": float(tw.mean()),
        "avg_qqq_weight": float(1.0 - tw.mean()),
        "avg_gross_leverage": float(1.0 + 2.0 * tw.mean()),
    }
    return w, info, tab


# --------------------------------------------------------------------------- #
# evaluation helpers
# --------------------------------------------------------------------------- #
def window_slice(ts: pd.DatetimeIndex, lo: str, hi: str) -> tuple[int, int]:
    i = bt.start_index(ts, lo)
    hi_next = pd.Timestamp(hi, tz="America/New_York").normalize() + pd.Timedelta(days=1)
    j = int(ts.searchsorted(hi_next, side="left"))
    return i, j


def run_window(w, ts, op, cl, lo, hi, slip=1.0):
    i, j = window_slice(ts, lo, hi)
    res = bt.simulate(ts[i:j], op[i:j], cl[i:j], w[i:j],
                      band=0.02, slippage_bps=slip)
    return res, bt.stats(res, BARS_1M)


def daily_returns(res):
    eq = bt.daily_last(res["equity"], res["ts"])
    return eq.pct_change().dropna()


def bench_daily(ts, close):
    return bt.daily_last(close, ts).pct_change().dropna()


def beta_corr(a: pd.Series, b: pd.Series) -> dict:
    df = pd.concat([a, b], axis=1, join="inner").dropna()
    x = df.iloc[:, 0].to_numpy()
    y = df.iloc[:, 1].to_numpy()
    return {"beta": float(np.cov(x, y, ddof=0)[0, 1] / np.var(y)),
            "corr": float(np.corrcoef(x, y)[0, 1]),
            "n_days": int(len(df))}


def capture(a: pd.Series, b: pd.Series) -> dict:
    df = pd.concat([a, b], axis=1, join="inner").dropna()
    x = df.iloc[:, 0].to_numpy()
    y = df.iloc[:, 1].to_numpy()
    up = y > 0
    down = y < 0
    return {
        "up_capture": float(x[up].mean() / y[up].mean()),
        "down_capture": float(x[down].mean() / y[down].mean()),
        "up_days": int(up.sum()),
        "down_days": int(down.sum()),
    }


def stats_block(res, slip):
    s = bt.stats(res, BARS_1M)
    return {
        "slip_bps": slip,
        "cagr": float(s["cagr"]),
        "max_drawdown": float(s["max_drawdown"]),
        "sharpe": float(s["sharpe"]),
        "sortino": float(s["sortino"]),
        "volatility": float(s["volatility"]),
        "exposure": float(s["exposure"]),
        "fills": int(s["fills"]),
        "turnover": float(s["turnover"]),
        "ending_equity": float(s["ending_equity"]),
        "calmar": float(s["cagr"] / s["max_drawdown"]) if s["max_drawdown"] else None,
    }


def block_shuffle(x: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    """Circular block permutation, preserving local runs and the value histogram."""
    n = len(x)
    nb = int(np.ceil(n / block))
    order = rng.permutation(nb)
    out = np.concatenate([x[(o * block):((o + 1) * block)] for o in order])
    return out[:n]


# --------------------------------------------------------------------------- #
def main() -> None:
    ts, op, cl = load_panel()
    i0, j0 = window_slice(ts, DEV_START, DEV_END)
    tsd, opd, cld = ts[i0:j0], op[i0:j0], cl[i0:j0]
    print(f"panel: {len(ts):,} bars, {len(tsd)} dev bars, {tsd[0]} .. {tsd[-1]}")

    p = Params()
    d, n_sess = daily_table(ts, cl)
    tw, tab = signal_weights(d, n_sess, p)
    w = broadcast(ts, tw)
    info = {
        "params": asdict(p),
        "sessions": int(n_sess),
        "tqqq_sessions": int((tw > 0).sum()),
        "tqqq_session_share": float((tw > 0).mean()),
        "full_tqqq_sessions": int((tw >= 1.0 - 1e-12).sum()),
        "avg_tqqq_weight": float(tw.mean()),
        "avg_qqq_weight": float(1.0 - tw.mean()),
        "avg_gross_leverage": float(1.0 + 2.0 * tw.mean()),
    }
    print("signal:", {k: v for k, v in info.items() if k != "params"})

    res1, s1 = run_window(w, ts, op, cl, DEV_START, DEV_END, 1.0)
    res5, s5 = run_window(w, ts, op, cl, DEV_START, DEV_END, 5.0)
    res10, s10 = run_window(w, ts, op, cl, DEV_START, DEV_END, 10.0)
    print(f"dev 1bp: CAGR {s1['cagr']*100:.2f}%  DD {s1['max_drawdown']*100:.2f}%  "
          f"Sharpe {s1['sharpe']:.2f}  exposure {s1['exposure']*100:.1f}%  "
          f"fills {s1['fills']}")

    # ---- daily return series and benchmarks ----
    dr = daily_returns(res1)
    tq_d = bench_daily(tsd, cld[:, COL["TQQQ"]])
    qq_d = bench_daily(tsd, cld[:, COL["QQQ"]])
    bc_tq = beta_corr(dr, tq_d)
    bc_qq = beta_corr(dr, qq_d)
    cap = capture(dr, tq_d)
    print(f"corr {bc_tq['corr']:.3f}  beta {bc_tq['beta']:.3f}  "
          f"up {cap['up_capture']:.2f}  down {cap['down_capture']:.2f}")

    tq_bench = bt.benchmark(cld[:, COL["TQQQ"]], tsd, BARS_1M)
    qq_bench = bt.benchmark(cld[:, COL["QQQ"]], tsd, BARS_1M)

    # ---- yearly ----
    yearly = {}
    for y in sorted(set(dr.index.year)):
        m = dr.index.year == y
        mt = tq_d.index.year == y
        mq = qq_d.index.year == y
        yearly[int(y)] = {
            "strategy": float((1 + dr[m]).prod() - 1),
            "tqqq": float((1 + tq_d[mt]).prod() - 1),
            "qqq": float((1 + qq_d[mq]).prod() - 1),
        }
    print("yearly:", {k: round(v["strategy"] * 100, 1) for k, v in yearly.items()})

    # ---- static blend at the same average weights ----
    avg_w = w[i0:j0].mean(axis=0)
    const = np.tile(avg_w, (len(tsd), 1))
    blend = bt.simulate(tsd, opd, cld, const, band=0.02, slippage_bps=1.0)
    blend_s = bt.stats(blend, BARS_1M)
    blend_dr = daily_returns(blend)
    blend_bc = beta_corr(blend_dr, tq_d)
    print(f"static blend: CAGR {blend_s['cagr']*100:.2f}%  DD "
          f"{blend_s['max_drawdown']*100:.2f}%  Sharpe {blend_s['sharpe']:.2f}")

    # ---- identity decomposition: how much of ratio momentum is QQQ trend? ----
    dev_tab = tab.copy()
    dev_tab = dev_tab[dev_tab.index <= pd.Timestamp(DEV_END)]
    dec = dev_tab[["rm", "qm100", "dvar100"]].dropna()
    X = np.column_stack([np.ones(len(dec)), dec["qm100"].to_numpy(),
                         dec["dvar100"].to_numpy()])
    yv = dec["rm"].to_numpy()
    coef, *_ = np.linalg.lstsq(X, yv, rcond=None)
    pred = X @ coef
    ss_res = float(((yv - pred) ** 2).sum())
    ss_tot = float(((yv - yv.mean()) ** 2).sum())
    decomposition = {
        "regression": "rm100 = a + b1*qm100 + b2*dvar100",
        "intercept": float(coef[0]),
        "b_qqq_momentum": float(coef[1]),
        "b_variance_change": float(coef[2]),
        "r2": float(1.0 - ss_res / ss_tot),
        "corr_rm100_qm100": float(np.corrcoef(yv, dec["qm100"])[0, 1]),
        "note": ("The identity predicts b1 ~= 2 and b2 ~= -3; the ratio momentum "
                 "is therefore a variance-adjusted QQQ trend, not a "
                 "market-neutral spread."),
    }

    # ---- pre-registered grid ----
    grid_specs = [
        (60, 0.25, 0.35), (60, 0.35, 0.45),
        (80, 0.25, 0.35), (80, 0.35, 0.45),
        (100, 0.25, 0.35), (100, 0.30, 0.40),
        (100, 0.35, 0.45), (120, 0.30, 0.40),
    ]
    grid = []
    for n, vlo, vhi in grid_specs:
        pp = Params(n=n, v_lo=vlo, v_hi=vhi)
        wg, infog, _ = build_weights(ts, op, cl, pp, return_info=True)
        rg, sg = run_window(wg, ts, op, cl, DEV_START, DEV_END, 1.0)
        grid.append({
            "n": n, "v_lo": vlo, "v_hi": vhi,
            "cagr": float(sg["cagr"]), "max_drawdown": float(sg["max_drawdown"]),
            "sharpe": float(sg["sharpe"]),
            "calmar": float(sg["cagr"] / sg["max_drawdown"]),
            "avg_tqqq_weight": infog["avg_tqqq_weight"],
            "fills": int(sg["fills"]),
        })
        print(f"grid n={n:3d} vol={vlo:.2f}-{vhi:.2f}: CAGR {sg['cagr']*100:5.2f}% "
              f"DD {sg['max_drawdown']*100:5.2f}% Sharpe {sg['sharpe']:.2f}")

    # ---- neighbours around the primary (robustness, not part of the grid) ----
    neighbours = []
    for n, vlo, vhi in ((90, 0.30, 0.40), (110, 0.30, 0.40),
                        (100, 0.28, 0.38), (100, 0.32, 0.42)):
        pp = Params(n=n, v_lo=vlo, v_hi=vhi)
        wg, infog, _ = build_weights(ts, op, cl, pp, return_info=True)
        rg, sg = run_window(wg, ts, op, cl, DEV_START, DEV_END, 1.0)
        neighbours.append({
            "n": n, "v_lo": vlo, "v_hi": vhi,
            "cagr": float(sg["cagr"]), "max_drawdown": float(sg["max_drawdown"]),
            "sharpe": float(sg["sharpe"]), "calmar": float(sg["cagr"] / sg["max_drawdown"]),
        })
        print(f"nbr  n={n:3d} vol={vlo:.2f}-{vhi:.2f}: CAGR {sg['cagr']*100:5.2f}% "
              f"DD {sg['max_drawdown']*100:5.2f}% Sharpe {sg['sharpe']:.2f}")

    # ---- ablations: does the ratio signal / vol filter actually add value? ----
    ablations = []
    for tag, sig_name, mode, mom_min in (
        ("no vol filter", "ratio", "none", -0.10),
        ("binary vol filter", "ratio", "binary", -0.10),
        ("mom_min 0.0", "ratio", "scale", 0.0),
        ("QQQ 100d momentum instead of ratio", "qqq", "scale", -0.10),
        ("QQQ momentum, no vol", "qqq", "none", -0.10),
    ):
        pp = Params(mom_min=mom_min)
        twa, _ = signal_weights(d, n_sess, pp, signal=sig_name, mode=mode)
        wa = broadcast(ts, twa)
        ra, sa = run_window(wa, ts, op, cl, DEV_START, DEV_END, 1.0)
        ablations.append({
            "variant": tag, "signal": sig_name, "vol_mode": mode,
            "mom_min": mom_min,
            "cagr": float(sa["cagr"]), "max_drawdown": float(sa["max_drawdown"]),
            "sharpe": float(sa["sharpe"]),
            "calmar": float(sa["cagr"] / sa["max_drawdown"]),
            "avg_tqqq_weight": float(twa.mean()),
        })
        print(f"ablation {tag:38s} CAGR {sa['cagr']*100:5.2f}% "
              f"DD {sa['max_drawdown']*100:5.2f}% Sharpe {sa['sharpe']:.2f}")

    # ---- worst drawdown episode ----
    eq_s = pd.Series(res1["equity"], index=tsd)
    peak_s = eq_s.cummax()
    dd_s = eq_s / peak_s - 1.0
    tr = dd_s.idxmin()
    pk = eq_s.loc[:tr].idxmax()
    after = eq_s.loc[tr:]
    rec = after[after >= eq_s.loc[pk]]
    drawdown_episode = {
        "peak": str(pk), "trough": str(tr), "recovered": str(rec.index[0]) if len(rec) else None,
        "depth": float(dd_s.min()),
        "sessions_peak_to_trough": int(len(np.unique(tsd[(tsd >= pk) & (tsd <= tr)].date))),
    }

    # ---- placebo: block-permuted TQQQ weight path, same distribution/runs ----
    _, starts_all, ends_all = bt.day_bounds(ts)
    dev_mask = (starts_all >= i0) & (ends_all < j0)
    tw_sess = np.array([w[a, COL["TQQQ"]] for a in starts_all[dev_mask]])
    placebos = []
    for seed in range(10):
        rng = np.random.default_rng(1000 + seed)
        sh = block_shuffle(tw_sess, 20, rng)
        wp = broadcast(tsd, sh)
        rp = bt.simulate(tsd, opd, cld, wp, band=0.02, slippage_bps=1.0)
        sp = bt.stats(rp, BARS_1M)
        placebos.append({"seed": seed, "cagr": float(sp["cagr"]),
                         "max_drawdown": float(sp["max_drawdown"]),
                         "sharpe": float(sp["sharpe"])})
    med = {k: float(np.median([x[k] for x in placebos]))
           for k in ("cagr", "max_drawdown", "sharpe")}
    print("placebo median:", {k: round(v, 4) for k, v in med.items()})

    # ---- one extra day of signal delay ----
    _, starts_all, _ = bt.day_bounds(ts)
    tw_full = np.array([w[a, COL["TQQQ"]] for a in starts_all])
    tw_lag = np.r_[0.0, tw_full[:-1]]
    w_lag = broadcast(ts, tw_lag)
    _, s_lag = run_window(w_lag, ts, op, cl, DEV_START, DEV_END, 1.0)

    # ---- cut tests ----
    cuts = {}
    for name, lo, hi in (
        ("2016-2019", "2016-01-04", "2019-12-31"),
        ("2020-2023", "2020-01-02", "2023-12-29"),
        ("2016-2021", "2016-01-04", "2021-12-31"),
        ("2022-2023", "2022-01-03", "2023-12-29"),
    ):
        rc, sc = run_window(w, ts, op, cl, lo, hi, 1.0)
        ic, jc = window_slice(ts, lo, hi)
        bq = bt.benchmark(cl[ic:jc, COL["TQQQ"]], ts[ic:jc], BARS_1M)
        cuts[name] = {
            "strategy": {"cagr": float(sc["cagr"]),
                         "max_drawdown": float(sc["max_drawdown"]),
                         "sharpe": float(sc["sharpe"])},
            "tqqq": {"cagr": float(bq["cagr"]),
                     "max_drawdown": float(bq["max_drawdown"]),
                     "sharpe": float(bq["sharpe"])},
        }
        print(f"cut {name}: CAGR {sc['cagr']*100:5.2f}% vs TQQQ {bq['cagr']*100:5.2f}%  "
              f"DD {sc['max_drawdown']*100:5.1f}% vs {bq['max_drawdown']*100:5.1f}%")

    passed = (s1["cagr"] > BAR["cagr"]) and (s1["max_drawdown"] < BAR["max_drawdown"])
    status = "passed" if passed else ("risk_adjusted" if s1["sharpe"] > BAR["sharpe"]
                                     else "failed")

    out = {
        "agent": "relative-value-tqqq",
        "status": status,
        "status_note": ("dev gates only; in-sample design disclosed in HYPOTHESIS.md; "
                        "holdout not run"),
        "idea": ("The TQQQ/QQQ ratio is a variance-adjusted leverage-cycle meter. "
                 "Hold TQQQ only while its ratio momentum is not broken and scale "
                 "the sleeve down as QQQ realised volatility rises."),
        "hypothesis": ("Ratio momentum > -10% over 100 sessions with QQQ 20-day vol "
                       "below 40% identifies the regime in which 3x compounding pays; "
                       "otherwise hold unlevered QQQ."),
        "universe": list(SYMS),
        "marks": "1m",
        "window": {"start": DEV_START, "end": DEV_END,
                   "sessions": int(len(tw_sess))},
        "params": asdict(p),
        "signal_info": {k: v for k, v in info.items() if k != "params"},
        "dev": {"1bp": stats_block(res1, 1), "5bp": stats_block(res5, 5),
                "10bp": stats_block(res10, 10)},
        "yearly": yearly,
        "attribution": {
            "corr_tqqq_daily": bc_tq["corr"],
            "beta_tqqq_daily": bc_tq["beta"],
            "corr_qqq_daily": bc_qq["corr"],
            "beta_qqq_daily": bc_qq["beta"],
            "capture_vs_tqqq": cap,
            "static_blend_same_avg_weights": {
                "weights": [float(x) for x in avg_w],
                "cagr": float(blend_s["cagr"]),
                "max_drawdown": float(blend_s["max_drawdown"]),
                "sharpe": float(blend_s["sharpe"]),
                "corr_tqqq_daily": blend_bc["corr"],
                "beta_tqqq_daily": blend_bc["beta"],
            },
            "signal_decomposition": decomposition,
            "is_just_tqqq_beta": (
                "No: the static blend at the strategy's average weights earns "
                f"{blend_s['cagr']*100:.1f}% CAGR / {blend_s['max_drawdown']*100:.1f}% "
                f"DD vs {s1['cagr']*100:.1f}% / {s1['max_drawdown']*100:.1f}% for the "
                "timed strategy. The edge is timing TQQQ beta, not a constant beta."),
        },
        "placebo_block_shuffle": {"block_sessions": 20, "runs": placebos,
                                  "median": med},
        "lag_one_extra_session": {
            "cagr": float(s_lag["cagr"]),
            "max_drawdown": float(s_lag["max_drawdown"]),
            "sharpe": float(s_lag["sharpe"]),
        },
        "cuts": cuts,
        "ablations": ablations,
        "drawdown_episode": drawdown_episode,
        "grid": grid,
        "neighbours": neighbours,
        "benchmarks": {
            "tqqq": {"cagr": float(tq_bench["cagr"]),
                     "max_drawdown": float(tq_bench["max_drawdown"]),
                     "sharpe": float(tq_bench["sharpe"]),
                     "volatility": float(tq_bench["volatility"])},
            "qqq": {"cagr": float(qq_bench["cagr"]),
                    "max_drawdown": float(qq_bench["max_drawdown"]),
                    "sharpe": float(qq_bench["sharpe"]),
                    "volatility": float(qq_bench["volatility"])},
            "bar_tqqq": BAR,
        },
        "notes": [
            "Daily design screen on dev informed the mechanism and grid centre; "
            "not a clean out-of-sample test.",
            "Exposure is always 100% (QQQ or TQQQ); average TQQQ weight is reported.",
            "No QQQ moving average, no price stop, no ratio froth/discount level.",
        ],
    }
    (HERE / "result.json").write_text(json.dumps(out, indent=2, default=float))
    print("wrote", HERE / "result.json", "status", status)


if __name__ == "__main__":
    main()
