"""Swing ORB variant grid."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
sys.path.insert(0, "research/agents/opening-range-breakout")
import bt
import orb_core as oc
from bench import load_all, evaluate, line, passes


if __name__ == "__main__":
    ts, opens, closes, q, t, b = load_all()
    d = oc.daily_tables(ts, q, t)

    cfgs = [
        ("sw30 base", dict(or_min=30)),
        ("sw30 orbreak", dict(or_min=30, exit_on_or_break=True)),
        ("sw15 orbreak", dict(or_min=15, exit_on_or_break=True)),
        ("sw5  orbreak", dict(or_min=5, exit_on_or_break=True)),
        ("sw30 fixed2", dict(or_min=30, stop="fixed", fixed_pct=0.02)),
        ("sw30 fixed3", dict(or_min=30, stop="fixed", fixed_pct=0.03)),
        ("sw30 fixed5", dict(or_min=30, stop="fixed", fixed_pct=0.05)),
        ("sw30 tgt5r", dict(or_min=30, target="r", target_r=5.0)),
        ("sw30 tgt10r", dict(or_min=30, target="r", target_r=10.0)),
        ("sw30 hold10", dict(or_min=30, max_hold_days=10)),
        ("sw30 hold21", dict(or_min=30, max_hold_days=21)),
        ("sw30 hold63", dict(or_min=30, max_hold_days=63)),
        ("sw30 qsig", dict(or_min=30, signal="QQQ")),
        ("sw30 qsig15", dict(or_min=15, signal="QQQ")),
    ]
    for name, extra in cfgs:
        cfg = dict(stop="orlow", intraday_only=False)
        cfg.update(extra)
        w, info = oc.build_weights(ts, q, t, d, cfg)
        out, yr = evaluate(ts, opens, closes, w)
        flag = "".join("P" if passes(out[x], x) else "-" for x in ("10y", "5y"))
        print(f"\n{name:14s} [{flag}] sig={info['entry_signals']:4d}")
        for tag in ("10y", "5y"):
            print("  " + line(tag, out[tag]))
        print("  yr: " + " ".join(f"{y}:{v['strategy']*100:.0f}" for y, v in yr["10y"].items()))
