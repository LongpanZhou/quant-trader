"""Focused robustness grid for the swing ORB family."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
sys.path.insert(0, "research/agents/opening-range-breakout")
import bt
import orb_core as oc
from bench import load_all, evaluate, line, passes


def dd_dates(ts, opens, closes, w, start):
    res = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=1.0)
    eq = pd.Series(res["equity"], index=res["ts"])
    daily = eq.groupby(eq.index.date).last()
    peak = daily.cummax()
    dd = daily / peak - 1
    trough = dd.idxmin()
    peak_date = daily.loc[:trough].idxmax()
    return peak_date, trough, dd.min()


if __name__ == "__main__":
    ts, opens, closes, q, t, b = load_all()
    d = oc.daily_tables(ts, q, t)

    cfgs = [
        ("q30 base", dict(or_min=30, signal="QQQ")),
        ("q30 h63", dict(or_min=30, signal="QQQ", max_hold_days=63)),
        ("q30 h126", dict(or_min=30, signal="QQQ", max_hold_days=126)),
        ("q30 h21", dict(or_min=30, signal="QQQ", max_hold_days=21)),
        ("q30 fixed5", dict(or_min=30, signal="QQQ", stop="fixed", fixed_pct=0.05)),
        ("q30 orbrk", dict(or_min=30, signal="QQQ", exit_on_or_break=True)),
        ("q15 h63", dict(or_min=15, signal="QQQ", max_hold_days=63)),
        ("q15 base", dict(or_min=15, signal="QQQ")),
        ("t30 h63", dict(or_min=30, max_hold_days=63)),
    ]
    for name, extra in cfgs:
        cfg = dict(stop="orlow", intraday_only=False)
        cfg.update(extra)
        w, info = oc.build_weights(ts, q, t, d, cfg)
        out, yr = evaluate(ts, opens, closes, w)
        flag = "".join("P" if passes(out[x], x) else "-" for x in ("10y", "5y"))
        print(f"\n{name:12s} [{flag}] sig={info['entry_signals']:4d}")
        for tag, st in (("10y", "2017-01-03"), ("5y", "2021-10-25")):
            p, tr, v = dd_dates(ts, opens, closes, w, st)
            print("  " + line(tag, out[tag]) + f"  DD {p}->{tr}")
        print("  yr: " + " ".join(f"{y}:{v['strategy']*100:.0f}" for y, v in yr["10y"].items()))
