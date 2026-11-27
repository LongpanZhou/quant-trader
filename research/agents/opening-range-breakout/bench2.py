"""Compare exact daily baseline and ORB swing variants."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
sys.path.insert(0, "research/agents/opening-range-breakout")
import bt
import orb_core as oc
from bench import load_all, evaluate, line, passes, BENCH, BASE, START10, START5


def baseline_weights(ts, d):
    dates, starts, ends = oc.day_arrays(ts)
    uniq = dates[starts]
    reg = d["regime"].reindex(uniq).to_numpy()
    w = np.zeros((len(ts), 3))
    for k, (s, e) in enumerate(zip(starts, ends)):
        # regime known at the close of the previous day applies from this open
        prev = reg[k - 1] if k > 0 else 0.0
        w[s:e - 1, 1] = prev
        w[s:e - 1, 2] = 1.0 - prev
        # the last bar sets the target for the next open using today's close
        w[e - 1, 1] = reg[k]
        w[e - 1, 2] = 1.0 - reg[k]
    return w


if __name__ == "__main__":
    ts, opens, closes, q, t, b = load_all()
    d = oc.daily_tables(ts, q, t)

    w = baseline_weights(ts, d)
    out, yr = evaluate(ts, opens, closes, w)
    print("EXACT DAILY BASELINE")
    for tag in ("10y", "5y"):
        print("  " + line(tag, out[tag]))
    print("  yearly:")
    for y, v in yr["10y"].items():
        print(f"    {y}: strat {v['strategy']*100:7.2f}%  bench {v['benchmark']*100:7.2f}%")

    cfgs = [
        ("swing30_break", dict(or_min=30, entry="breakout", stop="orlow", intraday_only=False)),
        ("swing15_break", dict(or_min=15, entry="breakout", stop="orlow", intraday_only=False)),
        ("swing5_break", dict(or_min=5, entry="breakout", stop="orlow", intraday_only=False)),
        ("swing30_first", dict(or_min=30, entry="first", stop="orlow", intraday_only=False,
                               target="r", target_r=10)),
        ("swing15_first", dict(or_min=15, entry="first", stop="orlow", intraday_only=False,
                               target="r", target_r=10)),
        ("swing5_first", dict(or_min=5, entry="first", stop="orlow", intraday_only=False,
                              target="r", target_r=10)),
    ]
    for name, cfg in cfgs:
        w, info = oc.build_weights(ts, q, t, d, cfg)
        out, yr = evaluate(ts, opens, closes, w)
        flag = "".join("P" if passes(out[x], x) else "-" for x in ("10y", "5y"))
        print(f"\n{name:16s} [{flag}] signals={info['entry_signals']}")
        for tag in ("10y", "5y"):
            print("  " + line(tag, out[tag]))
        print("  yearly: " + " ".join(f"{y}:{v['strategy']*100:.0f}" for y, v in yr["10y"].items()))
