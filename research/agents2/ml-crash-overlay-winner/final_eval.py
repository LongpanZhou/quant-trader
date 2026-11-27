"""Full evaluation of the leading crash overlay configs at 1/5/10 bp."""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from validate import build  # noqa: E402
from analyze2 import winner_daily  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
BARS = 252 * 390
STARTS = {"10y": "2017-01-03", "5y": "2021-10-25"}


def daily_eq(r, ts):
    eq = pd.Series(r["equity"], index=ts)
    d = eq.groupby(eq.index.date).last()
    d.index = pd.DatetimeIndex(d.index)
    return d


def yearly(d, bench):
    out = {}
    for y in sorted(set(d.index.year)):
        m = d.index.year == y
        if m.sum() < 2:
            continue
        out[int(y)] = {"strategy": float(d[m].iloc[-1] / d[m].iloc[0] - 1),
                       "bench": float(bench[m].iloc[-1] / bench[m].iloc[0] - 1)}
    return out


def rolling3(d):
    out = []
    for start in pd.date_range(d.index[0], d.index[-1] - pd.Timedelta(days=365 * 3), freq="QE"):
        end = start + pd.Timedelta(days=365 * 3)
        seg = d[(d.index >= start) & (d.index <= end)]
        if len(seg) < 200:
            continue
        ret = seg.iloc[-1] / seg.iloc[0] - 1
        peak = np.maximum.accumulate(seg)
        out.append({"start": str(start.date()), "end": str(end.date()),
                    "cagr": float((1 + ret) ** (1 / 3) - 1),
                    "dd": float(-(seg / peak - 1).min())})
    return out


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w0, op0, st0, la0, fi0 = winner_daily(ts, o, c)
    out = {}
    # winner baseline
    for lab, st in STARTS.items():
        r = bt.run(ts, o, c, w0, st, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BARS)
        i0 = bt.start_index(ts, st)
        d = daily_eq(r, ts[i0:])
        b = c[i0:, 1]
        bd = pd.Series(b, index=ts[i0:])
        bd = bd.groupby(bd.index.date).last()
        bd.index = pd.DatetimeIndex(bd.index)
        out[f"winner_{lab}"] = {
            "cagr": s["cagr"], "dd": s["max_drawdown"], "sharpe": s["sharpe"],
            "sortino": s["sortino"], "vol": s["volatility"], "fills": s["fills"],
            "yearly": yearly(d, bd), "rolling3": rolling3(d),
        }

    for q in (0.90, 0.95):
        w, flag, opened, dts, f, p, rank = build(ts, o, c, 20, -0.15, q, "bil")
        for lab, st in STARTS.items():
            for slip in (1.0, 5.0, 10.0):
                r = bt.run(ts, o, c, w, st, band=0.02, slippage_bps=slip)
                s = bt.stats(r, BARS)
                out[f"q{q:.2f}_{lab}_{slip:.0f}bp"] = {
                    "cagr": s["cagr"], "dd": s["max_drawdown"], "sharpe": s["sharpe"],
                    "sortino": s["sortino"], "vol": s["volatility"], "fills": s["fills"],
                }
            r = bt.run(ts, o, c, w, st, band=0.02, slippage_bps=1.0)
            i0 = bt.start_index(ts, st)
            d = daily_eq(r, ts[i0:])
            b = c[i0:, 1]
            bd = pd.Series(b, index=ts[i0:])
            bd = bd.groupby(bd.index.date).last()
            bd.index = pd.DatetimeIndex(bd.index)
            out[f"q{q:.2f}_{lab}_yearly"] = yearly(d, bd)
            out[f"q{q:.2f}_{lab}_rolling3"] = rolling3(d)
        m = dts >= pd.Timestamp("2017-01-03")
        print(f"q{q}: flags {int((flag & opened & m).sum())} / held {int((opened & m).sum())}")
        for lab in STARTS:
            print(f"  {lab}: " + "  ".join(
                f"{slip:.0f}bp {out[f'q{q:.2f}_{lab}_{slip:.0f}bp']['cagr']*100:5.1f}/"
                f"{out[f'q{q:.2f}_{lab}_{slip:.0f}bp']['dd']*100:5.1f}/"
                f"{out[f'q{q:.2f}_{lab}_{slip:.0f}bp']['sharpe']:.2f}"
                for slip in (1, 5, 10)))
    print("\nyearly q0.90 10y:")
    for y, v in out["q0.90_10y_yearly"].items():
        print(f"  {y}: strat {v['strategy']*100:7.1f}%  tqqq {v['bench']*100:7.1f}%  "
              f"winner {out['winner_10y']['yearly'][y]['strategy']*100:7.1f}%")
    print("\nyearly q0.95 10y:")
    for y, v in out["q0.95_10y_yearly"].items():
        print(f"  {y}: strat {v['strategy']*100:7.1f}%  tqqq {v['bench']*100:7.1f}%  "
              f"winner {out['winner_10y']['yearly'][y]['strategy']*100:7.1f}%")
    print("\nrolling3 q0.90 10y:", [(x["start"], round(x["cagr"]*100,1), round(x["dd"]*100,1))
                                    for x in out["q0.90_10y_rolling3"][:5]])
    Path(Path(__file__).parent / "eval_out.json").write_text(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()
