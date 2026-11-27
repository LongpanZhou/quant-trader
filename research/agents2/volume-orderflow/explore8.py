"""Step 9: event study - does volume at the stop bar separate real crashes from wicks?"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

pd.set_option("display.width", 220)


def stop_events(D, stop=0.04, arm_buf=0.01, arm_ma_n=20, extra_arm=None):
    """Return list of stop events with the state at the trigger bar."""
    ma = pd.Series(D.qc).rolling(arm_ma_n).mean().to_numpy()
    arm_prev = np.r_[np.nan, ma[:-1]]
    out = []
    for d in range(D.nd - 1):
        if not D.reg[d]:
            continue
        if extra_arm is not None and not extra_arm(d):
            continue
        armed = bool(np.isfinite(arm_prev[d]) and D.qc_m[d, 0] < arm_prev[d] * (1 + arm_buf))
        if not armed:
            continue
        base = D.to[d]
        for i in range(D.first[d], D.last[d] + 1):
            if D.cl[i, 1] < base * (1 - stop):
                j = min(i, D.last[d])
                out.append({
                    "day": d, "i": i, "minute": int(D.tod[i]),
                    "rvol": D.rvol_cum_q[d, min(int(D.tod[i]), 389)],
                    "rvol_bar": D.rvol_bar_q[d, min(int(D.tod[i]), 389)],
                    "dev": D.dev_q[d, min(int(D.tod[i]), 389)],
                    "fall": D.cl[i, 1] / base - 1,
                    # TQQQ return from the signal close to the next session open
                    "to_open": D.to[d + 1] / D.cl[j, 1] - 1,
                    "to_close": D.tc[d + 1] / D.cl[j, 1] - 1,
                    "same_day_left": D.tc[d] / D.cl[j, 1] - 1,
                })
                break
    return pd.DataFrame(out)


def main():
    D = engine.Data()
    for stop, buf in ((0.04, 0.0), (0.04, 0.01), (0.03, 0.0), (0.05, 0.0)):
        ev = stop_events(D, stop=stop, arm_buf=buf)
        print(f"\n=== stop {stop*100:.0f}% arm_buf {buf*100:.0f}%: n={len(ev)}")
        if len(ev) < 20:
            continue
        print(f"  all: mean to_open {ev.to_open.mean()*100:+.2f}% "
              f"med {ev.to_open.median()*100:+.2f}% "
              f"neg {100*(ev.to_open<0).mean():.0f}% "
              f"| to_close {ev.to_close.mean()*100:+.2f}%")
        e = pd.qcut(ev["rvol"], 4, duplicates="drop")
        g = ev.groupby(e, observed=True).agg(
            n=("to_open", "size"), rvol=("rvol", "mean"),
            to_open=("to_open", "mean"), med_open=("to_open", "median"),
            neg=("to_open", lambda x: (x < 0).mean()),
            to_close=("to_close", "mean"),
            same_day=("same_day_left", "mean"))
        for c in ("to_open", "med_open", "to_close", "same_day"):
            g[c] *= 100
        g["neg"] *= 100
        print(g.round(2).to_string())

    ev = stop_events(D, stop=0.04, arm_buf=0.0)
    print("\n=== fixed bins of rvol at the stop bar (4%, ungated)")
    edges = [0, 0.8, 1.0, 1.3, 1.8, 2.5, 99]
    ev["bin"] = pd.cut(ev["rvol"], edges)
    g = ev.groupby("bin", observed=True).agg(
        n=("to_open", "size"), to_open=("to_open", "mean"), med=("to_open", "median"),
        neg=("to_open", lambda x: (x < 0).mean()), to_close=("to_close", "mean"),
        same_day=("same_day_left", "mean"), fall=("fall", "mean"))
    for c in ("to_open", "med", "to_close", "same_day", "fall"):
        g[c] *= 100
    g["neg"] *= 100
    print(g.round(2).to_string())

    print("\n=== by minute of day")
    ev["hour"] = pd.cut(ev["minute"], [0, 60, 120, 240, 330, 390],
                        labels=["9:30-10:30", "10:30-11:30", "11:30-13:30",
                                "13:30-15:00", "15:00-16:00"])
    g = ev.groupby("hour", observed=True).agg(
        n=("to_open", "size"), to_open=("to_open", "mean"), to_close=("to_close", "mean"),
        rvol=("rvol", "mean"))
    g[["to_open", "to_close"]] *= 100
    print(g.round(2).to_string())


if __name__ == "__main__":
    main()
