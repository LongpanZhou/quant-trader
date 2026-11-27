"""Benchmark ORB variants against TQQQ buy-and-hold (10y and 5y)."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
sys.path.insert(0, "research/agents/opening-range-breakout")
import bt
import orb_core as oc

START10 = "2017-01-03"
START5 = "2021-10-25"
END = "2026-10-23"
BENCH = {"10y": (39.28, 81.68, 0.83), "5y": (13.47, 81.68, 0.53)}
BASE = {"10y": (45.31, 58.71, 1.00), "5y": (34.61, 36.86, 0.88)}


def load_all():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

    def prep(sym):
        df = bt.load_1m(sym)
        return df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts).ffill()

    return ts, opens, closes, prep("QQQ"), prep("TQQQ"), prep("BIL")


def evaluate(ts, opens, closes, w, slip=1.0):
    out = {}
    yearly = {}
    for tag, start in (("10y", START10), ("5y", START5)):
        res = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(res, 252 * 390)
        i = bt.start_index(ts, start)
        b = bt.benchmark(closes[i:, 1], ts[i:], 252 * 390)
        eqs = pd.Series(res["equity"], index=res["ts"])
        daily = eqs.groupby(eqs.index.date).last()
        dr = daily.pct_change().dropna()
        sh = float(dr.mean() / dr.std(ddof=0) * np.sqrt(252)) if dr.std() > 0 else 0.0
        peak = np.maximum.accumulate(daily.to_numpy())
        dd = float(-(daily.to_numpy() / peak - 1).min())
        out[tag] = dict(s, sharpe_daily=sh, dd_daily=dd,
                        bench_cagr=b["cagr"], bench_dd=b["max_drawdown"])
        yearly[tag] = bt.yearly(res["ts"], res["equity"], closes[i:i + len(res["ts"]), 1])
    return out, yearly


def line(tag, s):
    return (f"{tag}: {s['cagr']*100:6.2f}% / {s['max_drawdown']*100:5.2f}%  "
            f"Sh {s['sharpe']:4.2f} (d {s['sharpe_daily']:4.2f})  DDd {s['dd_daily']*100:5.2f}%  "
            f"fills {s['fills']:5d}  turn {s['turnover']:6.1f}x")


def passes(s, tag):
    return s["cagr"] * 100 > BENCH[tag][0] and s["max_drawdown"] * 100 < BENCH[tag][1]


if __name__ == "__main__":
    ts, opens, closes, q, t, b = load_all()
    d = oc.daily_tables(ts, q, t)

    cfgs = [
        ("orb5_break", dict(or_min=5, entry="breakout", stop="orlow", intraday_only=True)),
        ("orb15_break", dict(or_min=15, entry="breakout", stop="orlow", intraday_only=True)),
        ("orb30_break", dict(or_min=30, entry="breakout", stop="orlow", intraday_only=True)),
        ("orb5_first", dict(or_min=5, entry="first", stop="orlow", intraday_only=True, target="r", target_r=10)),
        ("orb15_first", dict(or_min=15, entry="first", stop="orlow", intraday_only=True, target="r", target_r=10)),
        ("orb30_first", dict(or_min=30, entry="first", stop="orlow", intraday_only=True, target="r", target_r=10)),
        ("regime_hold30", dict(mode="regime_hold", or_min=30)),
        ("regime_hold15", dict(mode="regime_hold", or_min=15)),
        ("regime_hold5", dict(mode="regime_hold", or_min=5)),
    ]
    for name, cfg in cfgs:
        w, info = oc.build_weights(ts, q, t, d, cfg)
        out, yr = evaluate(ts, opens, closes, w)
        flag = "".join("P" if passes(out[x], x) else "-" for x in ("10y", "5y"))
        print(f"\n{name:16s} [{flag}] signals={info['entry_signals']}")
        for tag in ("10y", "5y"):
            print("  " + line(tag, out[tag]))
