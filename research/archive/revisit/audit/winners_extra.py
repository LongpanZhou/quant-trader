"""Extra controls: bar-level time invested, matched-exposure stops, ratio episodes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import winners_lib as W  # noqa: E402
import bt  # noqa: E402


def broadcast_day(day, first, last, n):
    w = np.zeros((n, 3))
    for k, (f, l) in enumerate(zip(first, last)):
        w[f:l + 1] = day[k]
    return w


def stop_weights(size, dist, first, last, opens, closes, cooldown=0):
    """Constant size, one-sided stop, exit rest of session + night."""
    n = len(opens)
    nd = len(first)
    w = np.zeros((n, 3))
    events = 0
    out_left = 0
    for k, (f, l) in enumerate(zip(first, last)):
        if out_left > 0:
            w[f:l + 1, 2] = 1.0
            out_left -= 1
            continue
        s = float(size[k])
        w[f:l + 1, 1] = s
        w[f:l + 1, 2] = 1.0 - s
        d = dist[k]
        if not np.isfinite(d):
            continue
        base = opens[f, 1]
        idx = np.flatnonzero(closes[f:l + 1, 1] < base * (1.0 - d))
        if len(idx) == 0:
            continue
        i = f + int(idx[0])
        w[i, 1] = 0.0
        w[i, 2] = 1.0
        w[i + 1:l + 1, 1] = 0.0
        w[i + 1:l + 1, 2] = 1.0
        events += 1
        out_left = cooldown
    return w, events


def main():
    ts, o, h, l, c = W.load_panel()
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    nd = len(first)
    out = {}

    mod_r, w_r, diag = W.load_ratio_froth(ts, o, c)
    mod_v, w_v, vinfo, atr, _, _ = W.load_vol(ts, o, h, l, c)
    mean_w = float(w_v[:, 1].mean())

    # bar-level time invested
    for name, w in (("ratio_froth", w_r), ("vol_scaled", w_v)):
        out[name] = {
            "bar_frac_tqqq_gt0": float(np.mean(w[:, 1] > 1e-9)),
            "bar_frac_qqq_gt0": float(np.mean(w[:, 0] > 1e-9)),
            "bar_frac_all_cash": float(np.mean(w[:, 2] > 0.999)),
            "bar_frac_tqqq_full": float(np.mean(w[:, 1] > 0.999)),
            "mean_tqqq": float(w[:, 1].mean()),
        }

    # ratio froth episodes
    froth, ext = mod_r.froth_flag(c, last)
    runs = []
    k = 0
    while k < len(froth):
        if froth[k]:
            j = k
            while j + 1 < len(froth) and froth[j + 1]:
                j += 1
            runs.append((k, j))
            k = j + 1
        else:
            k += 1
    lens = [b - a + 1 for a, b in runs]
    out["ratio_froth_episodes"] = {
        "n": len(runs), "days": int(froth.sum()),
        "mean_len": float(np.mean(lens)), "median_len": float(np.median(lens)),
        "max_len": int(max(lens)),
        "first": str(pd.Timestamp(dates[last][runs[0][0]]).date()) if runs else None,
        "last": str(pd.Timestamp(dates[last][runs[-1][1]]).date()) if runs else None,
    }

    # matched-exposure controls
    size_const = np.full(nd, mean_w)
    dist_atr = np.clip(0.70 * atr, 0.025, 0.040)
    dist_fixed = np.full(nd, 0.04)
    variants = {
        "const_mean_no_stop": broadcast_day(
            np.column_stack([np.zeros(nd), size_const, 1 - size_const]), first, last, len(ts)),
    }
    w, ev = stop_weights(size_const, dist_atr, first, last, o, c)
    variants["const_mean_atr_stop"] = w
    out.setdefault("events", {})["const_mean_atr_stop"] = ev
    w, ev = stop_weights(size_const, dist_fixed, first, last, o, c)
    variants["const_mean_fixed4_stop"] = w
    out["events"]["const_mean_fixed4_stop"] = ev
    # 100% TQQQ with fixed 4% stop (same as fixed4_stop_binary, recomputed for table)
    w, ev = stop_weights(np.ones(nd), dist_fixed, first, last, o, c)
    variants["tqqq_fixed4_stop"] = w
    out["events"]["tqqq_fixed4_stop"] = ev
    # 100% TQQQ with ATR stop (same as binary_sizing_atr_stop)
    w, ev = stop_weights(np.ones(nd), dist_atr, first, last, o, c)
    variants["tqqq_atr_stop"] = w
    out["events"]["tqqq_atr_stop"] = ev

    labels = list(variants)
    results = bt.run_many(ts, o, c, [variants[k] for k in labels], W.START,
                          band=0.02, slippage_bps=1.0)
    for k, r in zip(labels, results):
        d = W.daily_equity(r)
        m = W.metrics(d)
        sr = W.daily_returns(d)
        # benchmark returns
        tq = pd.Series(c[last, 1], index=pd.to_datetime(dates[last])).pct_change()
        out[k] = {"daily": m, "exposure": W.exposure(variants[k], ts),
                  "beta_tqqq": W.beta_corr(sr, tq)}
        print(f"{k:26s} CAGR {m['cagr']*100:6.2f}  DD {m['max_drawdown']*100:5.2f}  "
              f"Sharpe {m['sharpe']:4.2f}  TQQQw {out[k]['exposure']['mean_tqqq']:.3f}  "
              f"beta {out[k]['beta_tqqq']['beta']:.2f}")

    W.save_json("winners_extra.json", out)
    print(json.dumps(out["ratio_froth"], indent=1))
    print(json.dumps(out["vol_scaled"], indent=1))
    print(json.dumps(out["ratio_froth_episodes"], indent=1))


if __name__ == "__main__":
    main()
