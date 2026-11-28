"""Development-only test: overnight-only ORB-direction strategy."""
from __future__ import annotations

import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
sys.path.insert(0, "research/revisit/opening-range-breakout")
import bt  # noqa: E402
from dev_explore import (load_dev, day_index, daily_q, baseline_165, score,
                         yearly, START, END)  # noqa: E402


def build_overnight(ts, q, t, *, or_min=30, buffer=0.0, signal="TQQQ",
                    asset="TQQQ", width_filter=None, filter_window=20,
                    size_mode="fixed", target_width=0.006):
    """Hold TQQQ only overnight after an up first OR candle; BIL otherwise.

    The position is bought at the last bar's open (weight set at the prior
    bar) and sold at 09:31 the next session.  No daytime exposure.
    """
    n = len(ts)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0
    dates, starts, ends = day_index(ts)
    sig_sym = t if signal == "TQQQ" else q
    trade = t if asset == "TQQQ" else q
    col = 1 if asset == "TQQQ" else 0
    so = sig_sym["open"].to_numpy()
    sc = sig_sym["close"].to_numpy()
    sh = sig_sym["high"].to_numpy()
    sl = sig_sym["low"].to_numpy()
    nd = len(starts)

    or_w = np.full(nd, np.nan)
    up = np.zeros(nd, dtype=bool)
    for k, (s, e) in enumerate(zip(starts, ends)):
        j = min(s + or_min, e)
        if j > s:
            up[k] = sc[j - 1] > so[s] * (1.0 + buffer)
            or_w[k] = (sh[s:j].max() - sl[s:j].min()) / sc[j - 1]
    width_med = pd.Series(or_w).rolling(filter_window, min_periods=10).median().shift(1).to_numpy()

    for k, (s, e) in enumerate(zip(starts, ends)):
        if e - s < or_min + 5:
            continue
        use = up[k]
        if width_filter is not None and np.isfinite(width_med[k]):
            if width_filter == "narrow" and not (or_w[k] <= width_med[k]):
                use = False
            if width_filter == "wide" and not (or_w[k] >= width_med[k]):
                use = False
        size = 1.0
        if size_mode == "inv_width" and np.isfinite(or_w[k]) and or_w[k] > 0:
            size = min(1.0, target_width / or_w[k])
        if use:
            # buy at the last bar's open, carry through the close
            w[e - 2, 0] = 0.0; w[e - 2, 1] = 0.0; w[e - 2, 2] = 0.0
            w[e - 2, col] = size
            w[e - 1, 0] = 0.0; w[e - 1, 1] = 0.0; w[e - 1, 2] = 0.0
            w[e - 1, col] = size
    return w


def daily_returns(eq, start=START, end=END):
    x = eq[(eq.index >= pd.Timestamp(start, tz="America/New_York")) &
           (eq.index <= pd.Timestamp(end, tz="America/New_York") + pd.Timedelta(days=1))]
    d = x.groupby(x.index.date).last()
    return d.pct_change().dropna()


if __name__ == "__main__":
    ts, o, c, q, t, b = load_dev()
    dq = daily_q(ts, q)

    base_w = baseline_165(ts, q, dq)
    base_s = score(ts, o, c, base_w)
    base_dr = daily_returns(base_s["eq"])
    print(f"baseline 165d dev: CAGR {base_s['cagr']*100:6.2f}%  DD {base_s['dd']*100:5.2f}%  "
          f"Sh {base_s['sharpe']:.2f}  fills {base_s['fills']}")

    cfgs = [
        ("orb30_up_tqqq", dict(or_min=30, signal="TQQQ", asset="TQQQ")),
        ("orb30_up_qsig", dict(or_min=30, signal="QQQ", asset="TQQQ")),
        ("orb15_up_tqqq", dict(or_min=15, signal="TQQQ", asset="TQQQ")),
        ("orb5_up_tqqq", dict(or_min=5, signal="TQQQ", asset="TQQQ")),
        ("orb60_up_tqqq", dict(or_min=60, signal="TQQQ", asset="TQQQ")),
        ("orb30_up_b5bp", dict(or_min=30, signal="TQQQ", asset="TQQQ", buffer=0.0005)),
        ("orb30_up_narrow", dict(or_min=30, signal="TQQQ", asset="TQQQ", width_filter="narrow")),
        ("orb30_up_inv", dict(or_min=30, signal="TQQQ", asset="TQQQ", size_mode="inv_width")),
        ("orb30_up_qqq", dict(or_min=30, signal="TQQQ", asset="QQQ")),
    ]
    for name, cfg in cfgs:
        w = build_overnight(ts, q, t, **cfg)
        s = score(ts, o, c, w)
        dr = daily_returns(s["eq"])
        joined = pd.concat([dr, base_dr], axis=1, join="inner").dropna()
        corr = float(np.corrcoef(joined.iloc[:, 0], joined.iloc[:, 1])[0, 1])
        print(f"{name:18s} CAGR {s['cagr']*100:6.2f}%  DD {s['dd']*100:5.2f}%  "
              f"Sh {s['sharpe']:.2f} (d {s['sharpe_d']:.2f})  fills {s['fills']:5d}  "
              f"turn {s['turnover']:6.1f}x  corr_base {corr:+.3f}")
