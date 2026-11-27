"""Final evaluation: chosen ORB config, costs, yearly, regime sensitivity."""
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
sys.path.insert(0, "research/agents/opening-range-breakout")
import bt
import orb_core as oc
from bench import load_all, evaluate, line, passes, BENCH, BASE, START10, START5


def run(ts, opens, closes, w, slip=1.0):
    return evaluate(ts, opens, closes, w, slip=slip)


if __name__ == "__main__":
    ts, opens, closes, q, t, b = load_all()
    d = oc.daily_tables(ts, q, t)

    # daily benchmarks exactly as README
    for tag, start in (("10y", START10), ("5y", START5)):
        i = bt.start_index(ts, start)
        dts, do, dc = bt.panel(("QQQ", "TQQQ", "BIL"), START10, "2026-10-23", "1D")
        j = bt.start_index(dts, start)
        bb = bt.benchmark(dc[j:, 1], dts[j:], 252)
        print(f"daily bench {tag}: CAGR {bb['cagr']*100:.2f}%  DD {bb['max_drawdown']*100:.2f}%  Sh {bb['sharpe']:.2f}")

    base_cfg = dict(or_min=30, signal="QQQ", stop="orlow", intraday_only=False)
    for label, extra in [
        ("q30 base", {}),
        ("q30 5bp", {}),
        ("q30 sma100", {"_sma": 100}),
        ("q30 sma200", {"_sma": 200}),
    ]:
        slip = 5.0 if "5bp" in label else 1.0
        dd = d
        if "_sma" in extra:
            dd = d.copy()
            dd["sma165"] = dd["qc"].rolling(extra["_sma"]).mean()
            dd["regime"] = (dd["qc"] > dd["sma165"]).astype(float)
            dd["regime_prev"] = dd["regime"].shift(1).fillna(0.0)
        cfg = dict(base_cfg)
        cfg.pop("_sma", None)
        w, info = oc.build_weights(ts, q, t, dd, cfg)
        out, yr = run(ts, opens, closes, w, slip=slip)
        flag = "".join("P" if passes(out[x], x) else "-" for x in ("10y", "5y"))
        print(f"\n{label} [{flag}] sig={info['entry_signals']} slip={slip}")
        for tag in ("10y", "5y"):
            print("  " + line(tag, out[tag]))
        print("  yearly 10y: " + " ".join(f"{y}:{v['strategy']*100:.1f}" for y, v in yr["10y"].items()))
        print("  yearly 5y:  " + " ".join(f"{y}:{v['strategy']*100:.1f}" for y, v in yr["5y"].items()))
