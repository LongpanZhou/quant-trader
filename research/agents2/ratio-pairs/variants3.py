"""Variant sweep 3: cost, yearly attribution, rolling windows, causal checks."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bt_lib as L  # noqa: E402


def slice_stats(r, start):
    ts = r["ts"]
    i = int(ts.searchsorted(pd.Timestamp(start, tz="America/New_York")))
    eq = r["equity"][i:]
    t = ts[i:]
    years = (t[-1] - t[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(eq)
    rets = np.diff(eq) / eq[:-1]
    return {
        "cagr": (eq[-1] / eq[0]) ** (1 / years) - 1,
        "dd": float(-(eq / peak - 1).min()),
        "sharpe": float(np.mean(rets) / np.std(rets) * np.sqrt(L.BARS)),
        "years": years,
    }


def main():
    import bt
    ts, opens, closes = L.load_panel()
    d = L.add_ratio_features(L.daily_frame(ts, opens, closes))
    dates, first, last = L.day_bounds(ts)
    nd = len(first)
    hold, risk_on, _, _ = L.winner_state(ts, opens, closes)

    def build(ext_series, theta, asset="QQQ", use_stop=True, hi=None, lo=None):
        ext = ext_series.shift(1).to_numpy() if hasattr(ext_series, "shift") else ext_series
        if hi is None:
            froth = np.nan_to_num(ext, nan=-9) > theta
        else:
            # hysteresis state machine on the daily series
            froth = np.zeros(nd, bool)
            state = False
            for k in range(nd):
                x = ext[k]
                if not np.isfinite(x):
                    state = False
                elif state and x < lo:
                    state = False
                elif not state and x > hi:
                    state = True
                froth[k] = state
        tgt = np.zeros((nd, 3))
        if asset == "QQQ":
            tgt[risk_on & ~froth, 1] = 1
            tgt[risk_on & froth, 0] = 1
        elif asset == "BIL":
            tgt[risk_on & ~froth, 1] = 1
        elif asset == "HALF":
            tgt[risk_on & ~froth, 1] = 1
            tgt[risk_on & froth, 1] = 0.5
            tgt[risk_on & froth, 0] = 0.5
        tgt[~risk_on, 2] = 1
        if asset == "BIL":
            tgt[froth, 2] = 1
            tgt[froth, 0] = 0
            tgt[froth, 1] = 0
        w = L.weights_from_daily(ts, tgt, first, last, stopped=~hold if use_stop else None)
        return w, froth

    def go(label, w, shows=(True, True)):
        r = bt.run(ts, opens, closes, w, L.START10, band=0.02, slippage_bps=1.0)
        s10 = slice_stats(r, L.START10)
        s5 = slice_stats(r, L.START5)
        print(f"{label:42s} 10y {s10['cagr']*100:6.2f}/{s10['dd']*100:5.2f}  "
              f"5y {s5['cagr']*100:6.2f}/{s5['dd']*100:5.2f}  fills {r['fills']:4d}")
        return r, s10, s5

    base = np.zeros((nd, 3))
    base[risk_on, 1] = 1
    base[~risk_on, 2] = 1
    wb = L.weights_from_daily(ts, base, first, last, stopped=~hold)
    print("baseline + slice check")
    rb, s10b, s5b = go("winner", wb)
    print(f"   winner full 5y run: {L.metrics(ts, opens, closes, wb, start=L.START5)['cagr']*100:.2f}"
          f" / {L.metrics(ts, opens, closes, wb, start=L.START5)['max_drawdown']*100:.2f}")

    print("\next200 thresholds (QQQ swap), including no-stop-on-QQQ variant")
    for theta in (0.16, 0.18, 0.20, 0.22):
        w, froth = build(d["ext200"], theta)
        go(f"ext200>{theta:.2f} QQQ   stop-on", w)
        w2, _ = build(d["ext200"], theta, use_stop=False)
        go(f"ext200>{theta:.2f} QQQ   no-stop", w2)

    print("\nhysteresis ext200 hi/lo")
    for hi, lo in ((0.22, 0.10), (0.20, 0.10), (0.20, 0.12), (0.18, 0.10), (0.18, 0.14)):
        w, froth = build(d["ext200"], None, hi=hi, lo=lo)
        go(f"ext200 hi{hi:.2f} lo{lo:.2f} ({froth.mean()*100:4.1f}%)", w)

    print("\nBIL swap")
    for theta in (0.18, 0.20, 0.22):
        w, _ = build(d["ext200"], theta, asset="BIL")
        go(f"ext200>{theta:.2f} BIL", w)

    print("\ncost sensitivity, ext200>0.18 QQQ")
    w, froth = build(d["ext200"], 0.18)
    for slip in (0.0, 1.0, 5.0, 10.0):
        r = bt.run(ts, opens, closes, w, L.START10, band=0.02, slippage_bps=slip)
        s10 = slice_stats(r, L.START10)
        s5 = slice_stats(r, L.START5)
        print(f"  {slip:4.1f}bp  10y {s10['cagr']*100:6.2f}/{s10['dd']*100:5.2f}   "
              f"5y {s5['cagr']*100:6.2f}/{s5['dd']*100:5.2f}")

    print("\nyearly returns (strategy vs TQQQ) for ext200>0.18 QQQ and winner")
    w, froth = build(d["ext200"], 0.18)
    r2 = bt.run(ts, opens, closes, w, L.START10, band=0.02, slippage_bps=1.0)
    y2 = bt.yearly(r2["ts"], r2["equity"], closes[bt.start_index(ts, L.START10):, 1])
    yb = bt.yearly(rb["ts"], rb["equity"], closes[bt.start_index(ts, L.START10):, 1])
    print("  year   winner        froth        TQQQ")
    for y in sorted(y2):
        print(f"  {y}  {yb[y]['strategy']*100:8.2f}%  {y2[y]['strategy']*100:8.2f}%  "
              f"{y2[y]['benchmark']*100:9.2f}%")

    print("\nlook-ahead robustness: shift the signal forward/backward")
    for sh in (-2, -1, 0, 1, 2):
        if sh == 0:
            ext = d["ext200"]
        else:
            ext = d["ext200"].shift(sh)
        # build() shifts by 1 internally
        w, _ = build(ext, 0.18)
        go(f"ext200 shifted {sh:+d} extra days", w)


if __name__ == "__main__":
    main()
