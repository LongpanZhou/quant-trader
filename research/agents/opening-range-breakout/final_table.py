"""Final variant table with consistent TQQQ OR-low stops."""
import sys
import numpy as np

sys.path.insert(0, "research")
sys.path.insert(0, "research/agents/opening-range-breakout")
import orb_core as oc
from bench import load_all, evaluate, line, passes


VARIANTS = [
    ("intraday_orb5", dict(or_min=5, intraday_only=True)),
    ("intraday_orb15", dict(or_min=15, intraday_only=True)),
    ("intraday_orb30", dict(or_min=30, intraday_only=True)),
    ("intraday_orb15_first", dict(or_min=15, entry="first", intraday_only=True,
                                  target="r", target_r=10)),
    ("swing_orb5", dict(or_min=5, intraday_only=False)),
    ("swing_orb15", dict(or_min=15, intraday_only=False)),
    ("swing_orb30", dict(or_min=30, intraday_only=False)),
    ("swing_orb45", dict(or_min=45, intraday_only=False)),
    ("swing_orb60", dict(or_min=60, intraday_only=False)),
    ("swing_orb30_fixed2", dict(or_min=30, intraday_only=False, stop="fixed", fixed_pct=0.02)),
    ("swing_orb30_fixed3", dict(or_min=30, intraday_only=False, stop="fixed", fixed_pct=0.03)),
    ("swing_orb30_fixed5", dict(or_min=30, intraday_only=False, stop="fixed", fixed_pct=0.05)),
    ("swing_orb30_atr3", dict(or_min=30, intraday_only=False, trail="atr", trail_k=3.0)),
    ("swing_orb30_atr4", dict(or_min=30, intraday_only=False, trail="atr", trail_k=4.0)),
    ("swing_orb30_tgt5r", dict(or_min=30, intraday_only=False, target="r", target_r=5.0)),
    ("regimehold_orb30", dict(mode="regime_hold", or_min=30)),
]


if __name__ == "__main__":
    ts, opens, closes, q, t, b = load_all()
    d = oc.daily_tables(ts, q, t)
    for name, cfg in VARIANTS:
        cfg = {**dict(stop="orlow", intraday_only=False), **cfg}
        w, info = oc.build_weights(ts, q, t, d, cfg)
        out, yr = evaluate(ts, opens, closes, w)
        flag = "".join("P" if passes(out[x], x) else "-" for x in ("10y", "5y"))
        print(f"{name:22s} [{flag}] sig={info['entry_signals']:5d}  "
              f"10y {out['10y']['cagr']*100:6.2f}/{out['10y']['max_drawdown']*100:5.2f}"
              f" Sh {out['10y']['sharpe']:4.2f}   "
              f"5y {out['5y']['cagr']*100:6.2f}/{out['5y']['max_drawdown']*100:5.2f}"
              f" Sh {out['5y']['sharpe']:4.2f}  fills {out['10y']['fills']}")
