"""Component attribution for the two winners, full 2016-2026 window.

Every variant is built from the frozen rules and simulated with the same
engine settings (next-open fills, 2% band, 1 bp).  No parameter is tuned.
"""
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


def ratio_variants(ts, o, c):
    mod, w_full, diag = W.load_ratio_froth(ts, o, c)
    dates = bt.session_dates(ts)
    first, last = bt.day_bounds_from_dates(dates)
    nd = len(first)

    variants = {
        "full": w_full,
        "no_overlay_gate_stop": mod.build_weights(ts, o, c, use_overlay=False)[0],
        "no_stop_gate_overlay": mod.build_weights(ts, o, c, use_stop=False)[0],
        "gate_only": mod.build_weights(ts, o, c, use_overlay=False, use_stop=False)[0],
    }

    # ratio overlay alone: TQQQ by default, QQQ when prior close is frothy
    froth, ext = mod.froth_flag(c, last)
    day = np.zeros((nd, 3))
    day[~froth, 1] = 1.0
    day[froth, 0] = 1.0
    variants["overlay_only_qqq"] = broadcast_day(day, first, last, len(ts))
    day_b = np.zeros((nd, 3))
    day_b[~froth, 1] = 1.0
    day_b[froth, 2] = 1.0
    variants["overlay_only_bil"] = broadcast_day(day_b, first, last, len(ts))

    # 4% intraday stop alone: TQQQ by default, BIL after a 4% break, no gate
    qqq_close, tqqq_close = c[:, 0], c[:, 1]
    dc = qqq_close[last]
    ma20 = pd.Series(dc).rolling(mod.MA_FAST).mean().to_numpy()
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    hold = np.zeros(len(ts), bool)
    armed_days = 0
    for k, (f, l) in enumerate(zip(first, last)):
        if k == 0 or not (ma20_prev[k] == ma20_prev[k]):
            continue
        armed = bool(qqq_close[f] < ma20_prev[k] * (1 + mod.ARM_BUF))
        if not armed:
            continue
        armed_days += 1
        base = o[f, 1]
        state = True
        for i in range(f, l + 1):
            if state and tqqq_close[i] < base * (1 - mod.STOP):
                state = False
            hold[i] = state
    w_stop = np.zeros((len(ts), 3))
    w_stop[hold, 1] = 1.0
    w_stop[~hold, 2] = 1.0
    variants["stop_only"] = w_stop
    variants["tqqq"] = np.tile(np.array([0.0, 1.0, 0.0]), (len(ts), 1))

    info = {
        "gate_only": mod.build_weights(ts, o, c, use_overlay=False, use_stop=False)[1],
        "full": diag,
        "froth_days": int(froth.sum()),
        "sessions": int(nd),
        "froth_share": float(froth.mean()),
        "stop_armed_days": int(armed_days),
        "stop_armed_share": float(armed_days / (nd - 1)),
        "ext_last": float(ext[-1]) if np.isfinite(ext[-1]) else None,
    }
    return variants, info, froth, ext, first, last


def vol_variants(ts, o, h, l, c):
    mod, w_full, info, atr, first, last = W.load_vol(ts, o, h, l, c)
    nd = len(first)
    size = np.clip(mod.TARGET_ATR / np.where(np.isfinite(atr), atr, mod.TARGET_ATR),
                   mod.SIZE_FLOOR, 1.0)
    day = np.zeros((nd, 3))
    day[:, 1] = size
    day[:, 2] = 1.0 - size
    w_sizing = broadcast_day(day, first, last, len(ts))

    variants = {
        "full": w_full,
        "sizing_only_no_stop": w_sizing,
        "binary_sizing_atr_stop": mod.build_weights(
            ts, o, c, first, last, atr, use_sizing=False)[0],
        "fixed4_stop_sizing": mod.build_weights(
            ts, o, c, first, last, atr, atr_mult=0.0,
            dist_floor=0.04, dist_cap=0.04)[0],
        "fixed4_stop_binary": mod.build_weights(
            ts, o, c, first, last, atr, use_sizing=False, atr_mult=0.0,
            dist_floor=0.04, dist_cap=0.04)[0],
    }
    mean_w = float(w_full[:, 1].mean())
    const = np.tile(np.array([0.0, mean_w, 1.0 - mean_w]), (len(ts), 1))
    variants["const_same_mean_exposure"] = const
    variants["tqqq"] = np.tile(np.array([0.0, 1.0, 0.0]), (len(ts), 1))

    infos = {"full": info, "mean_tqqq_weight": mean_w,
             "sizing_mean": float(size.mean()),
             "size_min": float(size.min())}
    for k in ("binary_sizing_atr_stop", "fixed4_stop_sizing", "fixed4_stop_binary"):
        kw = {"use_sizing": k != "binary_sizing_atr_stop"}
        if k.startswith("fixed4"):
            kw.update(atr_mult=0.0, dist_floor=0.04, dist_cap=0.04)
        infos[k] = mod.build_weights(ts, o, c, first, last, atr, **kw)[1]
    return variants, infos


def main():
    ts, o, h, l, c = W.load_panel()
    dates = bt.session_dates(ts)
    _, last_b = bt.day_bounds_from_dates(dates)
    idx = pd.to_datetime(dates[last_b])
    bench = {
        "tqqq": pd.Series(c[last_b, 1], index=idx),
        "qqq": pd.Series(c[last_b, 0], index=idx),
    }
    bench_ret = {k: W.daily_returns(v) for k, v in bench.items()}

    out = {"ratio": {}, "vol": {}}

    rv, rinfo, froth, ext, first, last = ratio_variants(ts, o, c)
    vv, vinfo = vol_variants(ts, o, h, l, c)

    for group, variants, infos in (("ratio", rv, rinfo), ("vol", vv, vinfo)):
        labels = list(variants)
        ws = [variants[k] for k in labels]
        print(group, "running", labels)
        results = bt.run_many(ts, o, c, ws, W.START, band=0.02, slippage_bps=1.0)
        for k, r in zip(labels, results):
            d = W.daily_equity(r)
            sr = W.daily_returns(d)
            out[group][k] = {
                "daily": W.metrics(d),
                "minute": W.minute_metrics(r),
                "exposure": W.exposure(variants[k], ts),
                "beta_tqqq": W.beta_corr(sr, bench_ret["tqqq"]),
                "beta_qqq": W.beta_corr(sr, bench_ret["qqq"]),
                "yearly": W.yearly_returns_eoy(d),
            }
            m = out[group][k]["daily"]
            print(f"  {k:28s} CAGR {m['cagr']*100:6.2f}  DD {m['max_drawdown']*100:5.2f}  "
                  f"Sharpe {m['sharpe']:4.2f}  TQQQw {out[group][k]['exposure']['mean_tqqq']:.3f}  "
                  f"beta {out[group][k]['beta_tqqq']['beta']:.2f}")
    out["ratio_info"] = rinfo
    out["vol_info"] = vinfo

    # ratio state diagnostics: forward one-session TQQQ vs QQQ returns by froth state
    # Use session open-to-open, no costs, purely descriptive.
    first_arr, last_arr = first, last
    nxt_open = np.r_[o[first_arr[1:], 1], np.nan]
    prev_open = o[first_arr, 1]
    tq_fwd = nxt_open / prev_open - 1.0
    qq_fwd = np.r_[o[first_arr[1:], 0], np.nan] / o[first_arr, 0] - 1.0
    ok = np.isfinite(tq_fwd) & np.isfinite(qq_fwd) & np.r_[False, np.ones(len(first_arr) - 1, bool)]
    out["ratio_state"] = {
        "froth": {
            "n": int((froth & ok).sum()),
            "tqqq_mean_fwd": float(tq_fwd[froth & ok].mean()),
            "qqq_mean_fwd": float(qq_fwd[froth & ok].mean()),
            "tqqq_hit": float((tq_fwd[froth & ok] > 0).mean()),
            "tqqq_worst": float(tq_fwd[froth & ok].min()),
        },
        "nonfroth": {
            "n": int((~froth & ok).sum()),
            "tqqq_mean_fwd": float(tq_fwd[~froth & ok].mean()),
            "qqq_mean_fwd": float(qq_fwd[~froth & ok].mean()),
            "tqqq_hit": float((tq_fwd[~froth & ok] > 0).mean()),
            "tqqq_worst": float(tq_fwd[~froth & ok].min()),
        },
    }
    # cumulative TQQQ return on froth days vs others (open-to-open)
    out["ratio_state"]["tqqq_cum_froth"] = float(np.prod(1 + tq_fwd[froth & ok]) - 1)
    out["ratio_state"]["tqqq_cum_nonfroth"] = float(np.prod(1 + tq_fwd[~froth & ok]) - 1)
    print("ratio_state", json.dumps(out["ratio_state"], indent=1))

    W.save_json("winners_attrib.json", out)


if __name__ == "__main__":
    main()
