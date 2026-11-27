"""Step-3 overfitting controls (development period only).

    python research/revisit/opening-range-breakout/tune_sweep.py

1. Pre-registered one-step neighbourhood (report.md section 10) plus the TQQQ
   execution sensitivity, at 0/1/5 bp, with sub-periods 2016-19 / 2020-21 /
   2022-23 and per-trade gross mean.
2. Random-entry placebo: one entry per session at a random bar 10:00-14:00 on
   the same fraction of sessions, same average size, held to the clock EOD exit.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("orb", HERE / "strategy.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
import tune_diag as D  # noqa: E402

bt = S.bt
SUB = {"2016-19": (2016, 2019), "2020-21": (2020, 2021), "2022-23": (2022, 2023)}

VARIANTS = {
    "primary": {},
    "or15": {"or_min": 15}, "or45": {"or_min": 45},
    "brk0": {"break_buffer_bps": 0.0}, "brk10": {"break_buffer_bps": 10.0},
    "rcl0": {"reclaim_buffer_bps": 0.0}, "rcl10": {"reclaim_buffer_bps": 10.0},
    "win15": {"reclaim_window": 15}, "win60": {"reclaim_window": 60},
    "tgt_mid": {"target": "mid"}, "tgt_eod": {"target": "eod"},
    "rr0.75": {"min_reward_r": 0.75}, "rr1.25": {"min_reward_r": 1.25},
    "risk0.25": {"risk_per_trade": 0.0025}, "risk1.0": {"risk_per_trade": 0.01},
    "tqqq": {"asset": "TQQQ"},
}


def sub_cagr(d):
    out = {}
    for k, (a, b) in SUB.items():
        x = d[[a <= t.year <= b for t in d.index]]
        prev = d[[t.year == a - 1 for t in d.index]]
        e0 = prev.iloc[-1] if len(prev) else 100000.0
        yrs = b - a + 1
        out[k] = (x.iloc[-1] / e0) ** (1 / yrs) - 1
    return out


def evaluate(ts, o, c, ws, col_of):
    rows = {}
    for slip in (0.0, 1.0, 5.0):
        res = bt.run_many(ts, o, c, list(ws.values()), S.DEV_START, band=0.02, slippage_bps=slip)
        for (name, w), r in zip(ws.items(), res):
            st = bt.stats(r, S.BARS_1M)
            row = rows.setdefault(name, {})
            row[f"cagr_{slip:g}bp"] = st["cagr"]
            if slip == 1.0:
                row["dd_1bp"] = st["max_drawdown"]
                row["sharpe_1bp"] = st["sharpe"]
                d = D.daily(r)
                row.update({f"sub_{k}_1bp": v for k, v in sub_cagr(d).items()})
                row["_daily"] = d
    for name, w in ws.items():
        tr = D.trades(ts, o, w, col_of[name])
        rows[name]["n"] = len(tr)
        rows[name]["mean_gross_bp"] = float(tr["ret"].mean() * 1e4) if len(tr) else 0.0
        rows[name]["t"] = (float(tr["ret"].mean() / tr["ret"].std() * np.sqrt(len(tr)))
                           if len(tr) > 2 else 0.0)
    return rows


def placebo(ts, o, c, w_real, draws=200, seed=1):
    """Random entry bar 10:00-14:00 on randomly chosen sessions, same count and size."""
    rng = np.random.default_rng(seed)
    i0 = bt.start_index(ts, S.DEV_START)
    tod = np.asarray(ts.hour * 60 + ts.minute)
    dates, starts, ends = S.sessions(ts)
    half = np.isin(dates, list(bt.HALF_DAYS))
    on = w_real[:, 0] > 0
    n_trades = int((on & ~np.r_[False, on[:-1]])[i0:].sum())
    size = float(w_real[on, 0][ts[on] >= pd.Timestamp(S.DEV_START, tz="America/New_York")].mean())
    sess = [(s, e) for s, e in zip(starts, ends) if s >= i0]
    hold = int(np.median(D.trades(ts, o, w_real, 0)["bars"]))
    out = {"real_hold_median_bars": hold, "eod": [], "matched_hold": []}
    for mode in ("eod", "matched_hold"):
        for k in range(0, draws, 8):
            batch = []
            for _ in range(min(8, draws - k)):
                w = np.zeros_like(w_real)
                w[:, 2] = 1.0
                for j in rng.choice(len(sess), n_trades, replace=False):
                    s, e = sess[j]
                    last = 13 * 60 if half[s] else 15 * 60 + 59
                    cand = np.flatnonzero((tod[s:e] >= 600) & (tod[s:e] < 840)) + s
                    a = rng.choice(cand)
                    z = np.searchsorted(tod[s:e], last - 1) + s       # clock EOD exit row
                    if mode == "matched_hold":
                        z = min(z, a + hold)
                    w[a:z, 0] = size
                    w[a:z, 2] = 1 - size
                batch.append(w)
            for r in bt.run_many(ts, o, c, batch, S.DEV_START, band=0.02, slippage_bps=1.0):
                out[mode].append(bt.stats(r, S.BARS_1M)["cagr"])
    return out


def main():
    ts, o, c, q, t, b = S.load_dev()
    base = S.baseline_165_daily()
    ws, col_of = {}, {}
    rows = {}
    names = list(VARIANTS)
    for k in range(0, len(names), 4):
        chunk = {}
        for nm in names[k:k + 4]:
            chunk[nm] = S.build_weights(ts, o, c, q, t, VARIANTS[nm])[0]
            col_of[nm] = 1 if VARIANTS[nm].get("asset") == "TQQQ" else 0
        rows.update(evaluate(ts, o, c, chunk, col_of))
        if "primary" in chunk:
            ws["primary"] = chunk["primary"]
    for nm, r in rows.items():
        r["corr_165d"] = S.correlate(r.pop("_daily"), base)
    df = pd.DataFrame(rows).T
    pd.set_option("display.width", 250)
    pct = [c_ for c_ in df.columns if c_.startswith(("cagr", "dd", "sub"))]
    show = df.copy()
    show[pct] = (show[pct].astype(float) * 100).round(2)
    for c_ in ("sharpe_1bp", "mean_gross_bp", "t", "corr_165d"):
        show[c_] = show[c_].astype(float).round(2)
    print(show.to_string())
    (HERE / "_tune_sweep.json").write_text(show.to_json(orient="index", indent=1), encoding="utf-8")

    pl = placebo(ts, o, c, ws["primary"])
    real = rows["primary"]["cagr_1bp"]
    summ = {}
    for mode in ("eod", "matched_hold"):
        a = np.array(pl[mode])
        summ[mode] = {"n": len(a), "mean": float(a.mean()), "p5": float(np.percentile(a, 5)),
                      "p50": float(np.median(a)), "p95": float(np.percentile(a, 95)),
                      "real_percentile": float((a < real).mean())}
    summ["real_cagr_1bp"] = real
    summ["real_hold_median_bars"] = pl["real_hold_median_bars"]
    print(json.dumps(summ, indent=1))
    with open(HERE / "_tune_placebo.json", "w", newline="\n", encoding="utf-8") as f:
        json.dump(summ, f, indent=1)


if __name__ == "__main__":
    main()
