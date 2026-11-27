"""Max-hold parameter neighborhood for the swing ORB."""
import sys
import numpy as np

sys.path.insert(0, "research")
sys.path.insert(0, "research/agents/opening-range-breakout")
import orb_core as oc
from bench import load_all, evaluate, line, passes


if __name__ == "__main__":
    ts, opens, closes, q, t, b = load_all()
    d = oc.daily_tables(ts, q, t)
    for sig in ("TQQQ", "QQQ"):
        print(f"\n===== signal {sig} =====")
        for hold in (10, 21, 42, 63, 84, 126, 252, 10**6):
            cfg = dict(or_min=30, signal=sig, stop="orlow", intraday_only=False,
                       max_hold_days=hold)
            w, info = oc.build_weights(ts, q, t, d, cfg)
            out, yr = evaluate(ts, opens, closes, w)
            flag = "".join("P" if passes(out[x], x) else "-" for x in ("10y", "5y"))
            tag = "inf" if hold > 1000 else str(hold)
            print(f"hold={tag:4s} [{flag}] sig={info['entry_signals']:4d}  "
                  f"10y {out['10y']['cagr']*100:5.2f}/{out['10y']['max_drawdown']*100:5.2f}  "
                  f"5y {out['5y']['cagr']*100:5.2f}/{out['5y']['max_drawdown']*100:5.2f}  "
                  f"Sh {out['10y']['sharpe']:.2f}/{out['5y']['sharpe']:.2f}")
