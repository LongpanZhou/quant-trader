"""Yearly/attribution diagnostics for the ML risk-off overlay."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "agents" / "ml-classifier"))
import bt  # noqa: E402


def build(ts, c, p, qlo):
    n = len(ts)
    q = c[:, 0]
    sma = pd.Series(q).rolling(165, min_periods=100).mean().to_numpy()
    base = (q > sma)
    thr = pd.Series(p).rolling(252, min_periods=60).quantile(qlo).shift(1).to_numpy()
    bear = p < thr
    pos = base & ~bear
    w = np.zeros((n, 3))
    w[:, 1] = pos.astype(float)
    w[:, 2] = 1.0 - pos
    return base, pos, bear, thr, w


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "1D")
    n = len(ts)
    q = c[:, 0]
    sma = pd.Series(q).rolling(165, min_periods=100).mean().to_numpy()
    base = (q > sma)
    for h, win, qlo in [(5, 750, 0.2), (10, 750, 0.1), (10, 750, 0.2),
                        (20, 750, 0.2), (5, None, 0.2)]:
        p = np.load(ROOT / "research" / "agents" / "ml-classifier" / f"pd_h{h}_w{win}.npy")
        b, pos, bear, thr, w = build(ts, c, p, qlo)
        r = bt.run(ts, o, c, w, "2017-01-03", band=0.02, slippage_bps=1.0)
        s = bt.stats(r, 252)
        print(f"\n=== h={h} w={win} q={qlo}: CAGR {s['cagr']*100:.2f} DD {s['max_drawdown']*100:.2f} "
              f"Sharpe {s['sharpe']:.2f} fills {s['fills']} turnover {s['turnover']:.0f} ===")
        yr = bt.yearly(r["ts"], r["equity"], c[bt.start_index(ts, '2017-01-03'):, 1][-len(r['ts']):])
        # recompute benchmark alignment safely
        i0 = bt.start_index(ts, "2017-01-03")
        yr = bt.yearly(r["ts"], r["equity"], c[i0:i0 + len(r["ts"]), 1])
        for y, v in yr.items():
            print(f"  {y}: strat {v['strategy']*100:7.1f}%  tqqq {v['benchmark']*100:7.1f}%")
        # exposure / switches from full array
        sw = np.nansum(pos[1:] != pos[:-1])
        print(f"  TQQQ days {pos[i0:].mean()*100:.1f}%  switches {sw}  bear days {bear[i0:].sum()}")
        # exit days: days base=1 but pos=0, with next-day return
        d = pd.DataFrame({
            "date": ts, "pos": pos, "base": base, "bear": bear, "p": p, "thr": thr,
            "q_open": o[:, 0], "t_open": o[:, 1], "q_close": q, "t_close": c[:, 1], "b_close": c[:, 2],
        })
        d["t_ret_next"] = d.t_close.shift(-1) / d.t_close - 1
        d["t_intraday_next"] = d.t_close.shift(-1) / d.t_open.shift(-1) - 1
        ex = d[(d.base) & (~d.pos)]
        print(f"  exit days {len(ex)}  mean avoided intraday {ex.t_intraday_next.mean()*100:.2f}%  "
              f"sum avoided {ex.t_intraday_next.sum()*100:.1f}%  worst {ex.t_intraday_next.min()*100:.1f}%")
        base_days = d[d.base]
        print(f"  base days {len(base_days)}  base intraday {base_days.t_intraday_next.mean()*100:.3f}%  "
              f"held intraday {base_days[base_days.pos].t_intraday_next.mean()*100:.3f}%")
        print("  worst avoided:")
        print(ex.nsmallest(8, "t_intraday_next")[["date", "t_intraday_next", "p", "thr"]].to_string(index=False))


if __name__ == "__main__":
    main()
