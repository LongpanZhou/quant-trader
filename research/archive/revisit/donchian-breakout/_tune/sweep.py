"""Step 3 variant sweep (dev only). Every variant evaluated is logged to sweep.jsonl.

    python sweep.py scale            # signal bar size with the original bar counts
    python sweep.py nbhd <rule>      # +-1-step neighbourhood at one bar size
    python sweep.py overnight <rule> # flat-overnight toggle
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from common import (HERE, DEV_START, bt, to_minutes, load_mod, panel1, stats, corr_base,
                    sub_periods)

S = load_mod(HERE.parent / "strategy.py", "dal_new")
TS1, O1, C1 = panel1()
_LOADED = {}
LOG = HERE / "sweep.jsonl"


def bars(rule):
    if rule not in _LOADED:
        _LOADED[rule] = S.load_5m(rule=rule)
    return _LOADED[rule]


def flat_overnight(w1):
    """BIL from the session's second-to-last minute decision; restore next morning."""
    d = pd.DatetimeIndex(TS1).normalize().as_unit("ns").asi8
    last = np.r_[d[1:] != d[:-1], True]
    pen = np.r_[last[1:], False]
    w = w1.copy()
    w[last | pen] = (0.0, 0.0, 1.0)
    return w


def evaluate(rule, params=None, overnight="hold", tag=""):
    ts, o, c, qh, ql, qc, tc, aq, at = bars(rule)
    p = dict(params or {})
    p["rule"] = rule
    w, info = S.build_weights(ts, qh, ql, qc, tc, aq, at, p)
    w1 = to_minutes(ts, w, TS1, rule)
    if overnight == "flat":
        w1 = flat_overnight(w1)
    out = {"tag": tag, "rule": rule, "params": params or {}, "overnight": overnight}
    for bps in (0, 1, 5, 10):
        r = bt.run(TS1, O1, C1, w1, DEV_START, 0.02, float(bps))
        out[f"{bps}bp"] = stats(r)
        if bps == 1:
            r1 = r
    i1 = bt.start_index(TS1, DEV_START)
    wd = w1[i1:]
    lev = float((wd[:, 0] + 3 * wd[:, 1]).mean())
    ws = np.zeros_like(w1)
    ws[:, 1] = lev / 3
    ws[:, 2] = 1 - lev / 3
    out["static_mix_1bp"] = stats(bt.run(TS1, O1, C1, ws, DEV_START, 0.02, 1.0))
    out["avg_lev"] = lev
    out["frac_riskon"] = float((wd[:, 2] < 1).mean())
    out["corr"] = corr_base(r1)
    out["sub_1bp"] = sub_periods(r1)
    out["state_changes"] = info["align_changes"]
    with open(LOG, "a", newline="\n", encoding="utf-8") as f:
        f.write(json.dumps(out, default=float) + "\n")
    return out, w1, r1


def show(o):
    a, b, c = (o[k] for k in ("1bp", "5bp", "10bp"))
    sp = o["sub_1bp"]
    print(f"{o['tag']:<28} {o['rule']:>5} {o['overnight']:>5} 0bp {o['0bp']['cagr']*100:6.2f}% | "
          f"1bp {a['cagr']*100:6.2f}% DD {a['max_drawdown']*100:5.1f}% Sh {a['sharpe']:5.2f} | "
          f"5bp {b['cagr']*100:6.2f}% 10bp {c['cagr']*100:6.2f}% | fills {a['fills']:6.0f} "
          f"lev {o['avg_lev']:.2f} on {o['frac_riskon']:.2f} mix {o['static_mix_1bp']['cagr']*100:5.2f}%/"
          f"{o['static_mix_1bp']['sharpe']:.2f} | corr {o['corr']:.2f} | "
          f"{sp['2016-19']*100:5.1f}/{sp['2020-21']*100:5.1f}/{sp['2022-23']*100:5.1f}", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "scale":
        for rule in ("5min", "10min", "15min", "30min", "1h"):
            show(evaluate(rule, tag="scale")[0])
    elif mode == "nbhd":
        rule = sys.argv[2]
        show(evaluate(rule, tag="centre")[0])
        for k, vals in S.NEIGHBOURS.items():
            for v in vals:
                if v == {"fast_entry": 20, "med_entry": 55, "slow_entry": 390,
                         "atr_k": 2.5, "target_vol": 0.30}[k]:
                    continue
                show(evaluate(rule, {k: v}, tag=f"{k}={v}")[0])
    elif mode == "overnight":
        rule = sys.argv[2]
        show(evaluate(rule, overnight="flat", tag="flat-overnight")[0])
