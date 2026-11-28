"""Development-only exploration for the standalone ORB rebuild.

Period: 2016-01-04 .. 2023-12-29.  Never loads 2024+.
The strategy family is intraday-only ORB: flat at the session close, BIL
otherwise.  No moving-average gate of any kind.
"""
from __future__ import annotations

import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt  # noqa: E402

START = "2016-01-04"
END = "2023-12-29"
BARS = 252 * 390


def load_dev():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

    def prep(sym):
        df = bt.load_1m(sym)
        return df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts").reindex(ts).ffill()

    return ts, opens, closes, prep("QQQ"), prep("TQQQ"), prep("BIL")


def day_index(ts):
    dates = ts.date
    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    ends = np.r_[starts[1:], len(ts)]
    return dates, starts, ends


def daily_q(ts, q):
    g = pd.DataFrame({
        "date": ts.date,
        "qo": q["open"].to_numpy(), "qh": q["high"].to_numpy(),
        "ql": q["low"].to_numpy(), "qc": q["close"].to_numpy(),
    })
    d = g.groupby("date").agg(qo=("qo", "first"), qh=("qh", "max"),
                              ql=("ql", "min"), qc=("qc", "last"))
    return d


def build(ts, q, t, *, or_min=30, entry="breakout", stop="orlow",
          stop_mult=1.0, target="eod", target_r=3.0, cutoff_bars=30,
          size_mode="fixed", target_width=0.006, width_filter=None,
          filter_window=20, asset="TQQQ", one_trade=True):
    """Standalone intraday ORB weights.  Flat at each session's last bar."""
    n = len(ts)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    dates, starts, ends = day_index(ts)
    sym = t if asset == "TQQQ" else q
    col = 1 if asset == "TQQQ" else 0
    hi = sym["high"].to_numpy()
    lo = sym["low"].to_numpy()
    op = sym["open"].to_numpy()
    cl = sym["close"].to_numpy()
    nd = len(starts)

    or_hi = np.full(nd, np.nan)
    or_lo = np.full(nd, np.nan)
    or_open = np.full(nd, np.nan)
    or_close = np.full(nd, np.nan)
    or_w = np.full(nd, np.nan)
    for k, (s, e) in enumerate(zip(starts, ends)):
        j = min(s + or_min, e)
        if j > s + 1:
            or_hi[k] = hi[s:j].max()
            or_lo[k] = lo[s:j].min()
            or_open[k] = op[s]
            or_close[k] = cl[j - 1]
            or_w[k] = (or_hi[k] - or_lo[k]) / cl[j - 1]

    # rolling OR-width median for sizing / filtering (uses prior days only)
    width_med = pd.Series(or_w).rolling(filter_window, min_periods=10).median().shift(1).to_numpy()

    for k in range(nd):
        s, e = starts[k], ends[k]
        if e - s < or_min + 5 or not np.isfinite(or_hi[k]):
            continue
        if width_filter is not None and np.isfinite(width_med[k]):
            if width_filter == "narrow" and not (or_w[k] <= width_med[k]):
                continue
            if width_filter == "wide" and not (or_w[k] >= width_med[k]):
                continue
        last_signal = e - 2  # the last bar carries the target into the close
        entry_end = max(s + or_min, e - cutoff_bars)
        pos = 0
        stop_px = np.nan
        target_px = np.inf
        entry_px = np.nan
        size = 1.0
        if size_mode == "inv_width" and np.isfinite(or_w[k]) and or_w[k] > 0:
            size = min(1.0, target_width / or_w[k])

        for i in range(s, e):
            if pos == 1:
                hit_stop = np.isfinite(stop_px) and lo[i] <= stop_px
                hit_tgt = np.isfinite(target_px) and hi[i] >= target_px
                if hit_stop or hit_tgt or i >= last_signal:
                    w[i, 0] = 0.0
                    w[i, 1] = 0.0
                    w[i, 2] = 1.0
                    pos = 0
                else:
                    w[i, 0] = 0.0
                    w[i, 1] = 0.0
                    w[i, 2] = 0.0
                    w[i, col] = size
                continue

            # flat: entry checks
            if i == s + or_min - 1 and entry == "first":
                trig = or_close[k] > or_open[k] * (1.0 + 1e-9)
            elif entry == "breakout":
                trig = (i >= s + or_min) and (i < entry_end) and (cl[i] > or_hi[k])
            else:
                trig = False
            if trig:
                pos = 1
                entry_px = cl[i]
                if stop == "orlow":
                    stop_px = or_lo[k]
                elif stop == "width":
                    stop_px = entry_px - stop_mult * (or_hi[k] - or_lo[k])
                else:
                    stop_px = np.nan
                risk = entry_px - stop_px if np.isfinite(stop_px) else np.nan
                if target == "r" and np.isfinite(risk) and risk > 0:
                    target_px = entry_px + target_r * risk
                elif target == "width":
                    target_px = entry_px + target_r * (or_hi[k] - or_lo[k])
                else:
                    target_px = np.inf
                w[i, 0] = 0.0
                w[i, 1] = 0.0
                w[i, 2] = 0.0
                w[i, col] = size
                if not one_trade:
                    # allow another attempt after a stop on the same day
                    pass
    return w


def baseline_165(ts, q, d):
    """Benchmark only: the old 165-day daily base.  Not used by the strategy."""
    dates, starts, ends = day_index(ts)
    uniq = dates[starts]
    sma = d["qc"].rolling(165, min_periods=120).mean()
    reg = (d["qc"] > sma).astype(float).shift(1).fillna(0.0).reindex(uniq).to_numpy()
    w = np.zeros((len(ts), 3))
    w[:, 2] = 1.0
    for k, (s, e) in enumerate(zip(starts, ends)):
        w[s:e, 1] = reg[k]
        w[s:e, 2] = 1.0 - reg[k]
    return w


def score(ts, o, c, w, slip=1.0):
    r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=slip)
    s = bt.stats(r, BARS)
    eq = pd.Series(r["equity"], index=r["ts"])
    daily = eq.groupby(eq.index.date).last()
    dr = daily.pct_change().dropna()
    sh = float(dr.mean() / dr.std(ddof=0) * np.sqrt(252)) if dr.std() > 0 else 0.0
    peak = np.maximum.accumulate(daily.to_numpy())
    dd = float(-(daily.to_numpy() / peak - 1).min())
    return {"cagr": float(s["cagr"]), "dd": float(s["max_drawdown"]),
            "sharpe": float(s["sharpe"]), "sharpe_d": sh, "dd_d": dd,
            "fills": int(s["fills"]), "turnover": float(s["turnover"]),
            "ending": float(s["ending_equity"]), "eq": eq, "daily": daily}


def yearly(ts, eq):
    out = {}
    for y in sorted(set(ts.year)):
        x = eq[eq.index.year == y]
        if len(x) > 1:
            out[int(y)] = float(x.iloc[-1] / x.iloc[0] - 1.0)
    return out


if __name__ == "__main__":
    ts, o, c, q, t, b = load_dev()
    dq = daily_q(ts, q)
    print("dev bars", len(ts), ts[0], ts[-1], "sessions", len(dq))

    cfgs = [
        ("orb30_break_eod", dict(or_min=30, entry="breakout", stop="orlow", target="eod")),
        ("orb15_break_eod", dict(or_min=15, entry="breakout", stop="orlow", target="eod")),
        ("orb5_break_eod", dict(or_min=5, entry="breakout", stop="orlow", target="eod")),
        ("orb30_first_10r", dict(or_min=30, entry="first", stop="orlow", target="r", target_r=10)),
        ("orb15_first_10r", dict(or_min=15, entry="first", stop="orlow", target="r", target_r=10)),
        ("orb5_first_10r", dict(or_min=5, entry="first", stop="orlow", target="r", target_r=10)),
        ("orb30_break_3r", dict(or_min=30, entry="breakout", stop="orlow", target="r", target_r=3)),
        ("orb30_break_2r", dict(or_min=30, entry="breakout", stop="orlow", target="r", target_r=2)),
        ("orb30_break_w1", dict(or_min=30, entry="breakout", stop="width", stop_mult=1.0, target="eod")),
        ("orb30_break_w05", dict(or_min=30, entry="breakout", stop="width", stop_mult=0.5, target="eod")),
    ]
    for name, cfg in cfgs:
        w = build(ts, q, t, **cfg)
        s = score(ts, o, c, w)
        print(f"{name:20s} CAGR {s['cagr']*100:6.2f}%  DD {s['dd']*100:5.2f}%  "
              f"Sh {s['sharpe']:.2f} (d {s['sharpe_d']:.2f})  fills {s['fills']:5d}  "
              f"turn {s['turnover']:6.1f}x")
