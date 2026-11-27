"""Tune-brief diagnostics for drawdown-stop-overlay (development window only).

    python research/revisit/drawdown-stop-overlay/diagnose.py [before|after]

`before` imports _before_tune/strategy.py, `after` (default) the current
strategy.py.  Prints JSON to stdout; nothing after 2023-12-29 is loaded.
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
which = sys.argv[1] if len(sys.argv) > 1 else "after"
path = HERE / ("_before_tune/strategy.py" if which == "before" else "strategy.py")
spec = importlib.util.spec_from_file_location("s_" + which, path)
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
bt, to_minutes = S.bt, S.to_minutes
DEV0, DEV1, BARS = S.DEV0, S.DEV1, S.BARS_1M


def daily_ret(run):
    df = pd.DataFrame({"ts": run["ts"], "eq": run["equity"]})
    e = df.groupby(df.ts.dt.date)["eq"].last()
    e.index = pd.to_datetime(e.index)
    return e


def yearly_cagr(e: pd.Series):
    out = {}
    for y in range(2016, 2024):
        s = e[e.index.year == y]
        prev = e[e.index.year < y]
        start = prev.iloc[-1] if len(prev) else s.iloc[0]
        out[y] = float(s.iloc[-1] / start - 1)
    return out


def main():
    ts1, o1, c1 = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1min")
    tsd, od, cd = bt.panel(("QQQ", "TQQQ", "BIL"), DEV0, DEV1, "1D")
    g = S.load_daily_qqq_ohlc(tsd)
    params = S.VARIANTS["primary"]
    w_d, info = S.build_daily_weights(g, **params)
    w_m = to_minutes(tsd, w_d, ts1, "1D")
    out = {"which": which, "params": params}

    # --- exits by reason (re-derive from the state machine output) -------
    tgt = w_d[:, 1] > 0
    out["signal_days"] = info["signal_days"]
    out["entries"] = len(info["entries"])
    out["reasons"] = info.get("exit_reasons")

    # --- exposure ---------------------------------------------------------
    f_tq = float(w_m[:, 1].mean())
    out["exposure"] = {"tqqq_minutes": float((w_m[:, 1] > 0).mean()),
                       "avg_tqqq_weight": f_tq, "qqq": 0.0, "short": 0.0,
                       "bil_minutes": float((w_m[:, 2] > 0).mean()),
                       "avg_gross_leverage": 3 * f_tq}

    # --- runs ---------------------------------------------------------------
    static = np.zeros_like(w_m)
    static[:, 1] = f_tq
    static[:, 2] = 1 - f_tq
    wb = to_minutes(tsd, S.build_baseline(tsd, cd), ts1, "1D")
    runs = bt.run_many(ts1, o1, c1, [w_m, static, wb], DEV0, band=0.02, slippage_bps=1.0)
    r5, r10 = bt.run_many(ts1, o1, c1, [w_m, w_m], DEV0, band=0.02, slippage_bps=5.0)[0], \
        bt.run_many(ts1, o1, c1, [w_m], DEV0, band=0.02, slippage_bps=10.0)[0]
    st = {k: bt.stats(r, BARS) for k, r in zip(("strat", "static_mix", "base165"), runs)}
    st["strat_5bp"], st["strat_10bp"] = bt.stats(r5, BARS), bt.stats(r10, BARS)
    out["stats"] = {k: {m: float(v[m]) for m in ("cagr", "max_drawdown", "sharpe", "fills", "turnover")}
                    for k, v in st.items()}
    yrs = st["strat"]["years"]
    out["trades_per_year"] = st["strat"]["fills"] / yrs
    out["turnover_per_year"] = st["strat"]["turnover"] / yrs

    e = daily_ret(runs[0])
    eb = daily_ret(runs[2])
    out["corr_vs_165d"] = float(e.pct_change().dropna().corr(eb.pct_change().dropna()))

    # --- per-year ----------------------------------------------------------
    days = pd.DatetimeIndex(tsd).tz_localize(None).normalize()
    tq = pd.Series(cd[:, 1], index=days)
    tqo_all = od[:, 1]
    qq = pd.Series(cd[:, 0], index=days)
    es = daily_ret(runs[1])
    out["per_year"] = {y: {"strat": a, "static_mix": b, "tqqq": c_, "qqq": d_}
                       for (y, a), b, c_, d_ in zip(yearly_cagr(e).items(), yearly_cagr(es).values(),
                                                    yearly_cagr(tq).values(), yearly_cagr(qq).values())}
    for lo, hi in ((2016, 2019), (2020, 2021), (2022, 2023)):
        m = (e.index.year >= lo) & (e.index.year <= hi)
        s = e[m]
        prev = e[e.index.year < lo]
        start = prev.iloc[-1] if len(prev) else s.iloc[0]
        n = (s.index[-1] - (prev.index[-1] if len(prev) else s.index[0])).days / 365.25
        out.setdefault("subperiods", {})[f"{lo}-{hi}"] = float((s.iloc[-1] / start) ** (1 / n) - 1)

    # --- where the gap comes from (close-to-close attribution) -------------
    # open-to-open TQQQ log return for session d -> d+1, held iff target[d-1]
    # (target set at close d-1 fills at open d and is held until open d+1)
    tq_r = np.r_[np.log(tqo_all[1:] / tqo_all[:-1]), 0.0]
    held = np.r_[False, tgt[:-1]]
    out["gap"] = {
        "tqqq_logret_total": float(tq_r.sum()),
        "tqqq_logret_on_held_days": float(tq_r[held].sum()),
        "tqqq_logret_on_flat_days": float(tq_r[~held].sum()),
        "held_days": int(held.sum()),
        "tqqq_up_days_missed_gt3pct": int(((tq_r > np.log(1.03)) & ~held).sum()),
        "tqqq_up_days_total_gt3pct": int((tq_r > np.log(1.03)).sum()),
        "strat_logret_total": float(np.log(e.iloc[-1] / e.iloc[0])),
    }

    # --- event study: TQQQ next-open -> close[d+k] -------------------------
    sig, _ = S.signal_and_exit_arrays(g, params["lookback"], params["hold"],
                                      params["stop"], params["range_pos"])
    tqo = od[:, 1]
    tqc = cd[:, 1]
    n = len(tqc)
    rng = np.random.default_rng(7)
    ev = {}
    for k in (1, 3, 5, 10):
        ok = np.arange(n) + k < n
        fwd = np.full(n, np.nan)
        idx = np.arange(n)[ok]
        fwd[idx] = tqc[idx + k] / tqo[idx + 1] - 1
        valid = np.isfinite(fwd)
        si = np.flatnonzero(sig & valid)
        pool = fwd[valid]
        obs = float(fwd[si].mean())
        boots = np.array([pool[rng.integers(0, len(pool), len(si))].mean() for _ in range(5000)])
        ev[f"{k}d"] = {"n": int(len(si)), "mean": obs, "uncond": float(pool.mean()),
                       "hit_rate": float((fwd[si] > 0).mean()),
                       "uncond_hit": float((pool > 0).mean()),
                       "p_boot": float((boots >= obs).mean())}
    out["event_study"] = ev

    # --- trade-level hit rate --------------------------------------------
    trade_r = []
    ent = np.flatnonzero(np.diff(np.r_[0, tgt.astype(int)]) == 1)  # signal days
    ext = np.flatnonzero(np.diff(np.r_[tgt.astype(int), 0]) == -1)  # last held-target day
    for a, b in zip(ent, ext):
        # target set at close a fills at open a+1; the last 1 is at close b,
        # so the 0 set at close b+1 fills at open b+2
        if b + 2 < n:
            trade_r.append(tqo[b + 2] / tqo[a + 1] - 1)
    trade_r = np.array(trade_r)
    out["trades"] = {"n": int(len(trade_r)), "mean": float(trade_r.mean()),
                     "median": float(np.median(trade_r)), "hit_rate": float((trade_r > 0).mean()),
                     "worst": float(trade_r.min()), "best": float(trade_r.max()),
                     "avg_hold_days": float(tgt.sum() / max(len(trade_r), 1))}

    # --- random-entry placebo: same number of entries, same exit machine --
    if hasattr(S, "build_daily_weights_from_signal"):
        wl, seeds = [], 200
        for s_ in range(seeds):
            r_ = np.random.default_rng(1000 + s_)
            fake = np.zeros(n, bool)
            fake[r_.choice(np.arange(25, n - 1), size=int(sig.sum()), replace=False)] = True
            wd, _ = S.build_daily_weights_from_signal(g, fake, **{k: v for k, v in params.items()
                                                                if k not in ("lookback", "range_pos")})
            wl.append(to_minutes(tsd, wd, ts1, "1D"))
        cag = []
        for i in range(0, seeds, 25):
            cag += [bt.stats(r, BARS)["cagr"] for r in
                    bt.run_many(ts1, o1, c1, wl[i:i + 25], DEV0, band=0.02, slippage_bps=1.0)]
        cag = np.array(cag)
        out["random_entry_placebo"] = {"seeds": seeds, "median_cagr": float(np.median(cag)),
                                       "p95": float(np.percentile(cag, 95)),
                                       "frac_ge_strat": float((cag >= st["strat"]["cagr"]).mean())}
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
