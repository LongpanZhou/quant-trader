"""Step 18: volume-scaled stop distance (continuous), and event attribution."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

pd.set_option("display.width", 240)


def winner_vscale(D, stop=0.04, ma_n=20, buf=0.01, c=0.3, lo=0.02, hi_stop=0.08):
    """Stop distance widens when the session's volume is quiet.

    stop_i = clip(stop * (1 + c * (1 - rvol_i)), lo, hi_stop)
    """
    ma = pd.Series(D.qc).rolling(ma_n).mean().to_numpy()
    mprev = np.r_[np.nan, ma[:-1]]
    w = np.zeros((D.n, 3))
    hold = np.ones(D.n, bool)
    hold[~D.reg_bar] = False
    events = []
    for d in range(D.nd):
        if not D.reg[d]:
            continue
        f, l = int(D.first[d]), int(D.last[d])
        m = l - f + 1
        a_ma = bool(np.isfinite(mprev[d]) and D.qc_m[d, 0] < mprev[d] * (1 + buf))
        if not a_ma:
            continue
        rv = D.rvol_cum_q[d, :m]
        c_ = D.cl[f:l + 1, 1]
        base = D.to[d]
        s = np.clip(stop * (1 + c * (1 - np.nan_to_num(rv, nan=1.0))), lo, hi_stop)
        hit = c_ < base * (1 - s)
        if hit.any():
            j = int(np.argmax(hit))
            hold[f + j: l + 1] = False
            events.append((str(D.dates[f]), int(D.tod[f + j]), float(rv[j]), float(s[j])))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1 - w[:, 1]
    return w, events


def stops_of(D, w):
    """List (date, minute) where the weight leaves TQQQ intraday."""
    out = []
    h = w[:, 1]
    for d in range(D.nd):
        f, l = int(D.first[d]), int(D.last[d])
        seg = h[f:l + 1]
        if seg[0] > 0 and (seg == 0).any():
            j = int(np.argmax(seg == 0))
            out.append((str(D.dates[f]), int(D.tod[f + j])))
    return out


def main():
    D = engine.Data()
    base, _ = engine.winner_weights(D)
    b = engine.evaluate(D, base, "winner")
    W = {k: (v["cagr"], v["max_drawdown"]) for k, v in b.items()}

    print("\n-- continuous volume-scaled stop: S*(1 + c*(1-rvol)), clipped")
    for stop in (0.035, 0.040, 0.045):
        for c in (0.0, 0.1, 0.2, 0.3, 0.4):
            w, ev = winner_vscale(D, stop=stop, c=c)
            r = engine.evaluate(D, w)
            print(f"  S={stop:.3f} c={c}: 10y {r['10y']['cagr']*100:5.2f}/"
                  f"{r['10y']['max_drawdown']*100:5.2f} "
                  f"({(r['10y']['cagr']-W['10y'][0])*100:+5.2f},"
                  f"{(r['10y']['max_drawdown']-W['10y'][1])*100:+5.2f}) | 5y "
                  f"{r['5y']['cagr']*100:5.2f}/{r['5y']['max_drawdown']*100:5.2f} "
                  f"({(r['5y']['cagr']-W['5y'][0])*100:+5.2f},"
                  f"{(r['5y']['max_drawdown']-W['5y'][1])*100:+5.2f}) | {len(ev)}")

    print("\n-- attribution: stops in 2025-11..2026-10, baseline vs variants")
    from arming_grid import winner_vol
    cfgs = {"baseline": base,
            "vol hi1.5 q0.8": winner_vol(D, hi=1.5, quiet=0.8)[0],
            "vol hi1.5 q0.9": winner_vol(D, hi=1.5, quiet=0.9)[0],
            "vscale c0.3": winner_vscale(D, c=0.3)[0]}
    for name, w in cfgs.items():
        st = stops_of(D, w)
        recent = [x for x in st if x[0] >= "2025-10-01"]
        print(f"  {name}: total {len(st)}, since 2025-10: {len(recent)} -> "
              + ", ".join(f"{d}@{m//60+9}:{m%60:02d}" for d, m in recent))


if __name__ == "__main__":
    main()
