"""Diagnostics for the chosen ATR stop: stop-event anatomy, distance
distribution vs the fixed 4%, and where the improvement comes from.

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/vol-scaled-crash-stop/diag.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

from sweep1 import build_measures, load_cache, regime_arrays  # noqa: E402


def stop_events(ts, opens, closes, first, last, risk_on, armed, dist):
    """Return list of (day, trigger_ts, stop_dist, fwd_ret_to_next_open)."""
    ev = []
    for k, (f, l) in enumerate(zip(first, last)):
        if not risk_on[k] or not armed[k]:
            continue
        d = dist[k]
        base = opens[f, 1]
        for i in range(f, l + 1):
            if d == d and closes[i, 1] < base * (1.0 - d):
                # exit at open[i+1] (or last close if trigger is the last bar)
                px_exit = opens[i + 1, 1] if i + 1 < len(ts) else closes[i, 1]
                px_next = opens[f + 390, 1] if f + 390 < len(opens) else closes[-1, 1]
                fwd_day = closes[l, 1] / px_exit - 1.0
                fwd_ngt = px_next / px_exit - 1.0
                ev.append(dict(day=str(ts[i].date()), time=str(ts[i].time()),
                               dist=float(d), fwd_day=float(fwd_day),
                               fwd_ngt=float(fwd_ngt)))
                break
    return ev


def main():
    ts, opens, highs, lows, closes, vols = load_cache()
    m = build_measures(ts, opens, highs, lows, closes)
    dates, first, last = m["dates"], m["first"], m["last"]
    risk_on, armed, _ = regime_arrays(ts, closes, first, last)
    nd = len(first)
    cl = np.clip
    d_atr = cl(0.70 * m["atr14"], 0.025, 0.06)
    d_fix = np.full(nd, 0.04)
    i0 = bt.start_index(ts, "2017-01-03")

    out = {}
    for name, d in (("fixed4", d_fix), ("atr070", d_atr)):
        ev = [e for e in stop_events(ts, opens, closes, first, last, risk_on, armed, d)
              if e["day"] >= "2017-01-03"]
        n = len(ev)
        mean_ngt = float(np.mean([e["fwd_ngt"] for e in ev]))
        med_ngt = float(np.median([e["fwd_ngt"] for e in ev]))
        win = float(np.mean([e["fwd_ngt"] > 0 for e in ev]))
        worst = sorted(ev, key=lambda e: e["fwd_ngt"])[:6]
        by_year = {}
        for e in ev:
            by_year[e["day"][:4]] = by_year.get(e["day"][:4], 0) + 1
        out[name] = dict(events=n, mean_fwd_overnight=mean_ngt,
                         median_fwd_overnight=med_ngt, share_positive=win,
                         mean_fwd_to_close=float(np.mean([e["fwd_day"] for e in ev])),
                         by_year=by_year, median_dist=float(np.median([e["dist"] for e in ev])),
                         worst=[(e["day"], round(e["fwd_ngt"] * 100, 2)) for e in worst])
        print(f"\n{name}: {n} events, median stop {out[name]['median_dist']*100:.2f}%")
        print(f"  stop->next open: mean {mean_ngt*100:+.2f}%  median {med_ngt*100:+.2f}%  "
              f"share positive {win*100:.0f}% (a positive number = the stop saved money)")
        print(f"  by year: {by_year}")
        print(f"  worst saved: {out[name]['worst']}")

    # distribution of the ATR stop distance on armed risk-on days
    arm_days = risk_on & armed
    q = np.percentile(d_atr[arm_days & np.isfinite(d_atr)], [10, 25, 50, 75, 90]) * 100
    out["atr070_armed_dist_quantiles"] = [float(x) for x in q]
    print(f"\nATR x0.70 stop distance on armed risk-on days: "
          f"p10 {q[0]:.2f}%  p25 {q[1]:.2f}%  med {q[2]:.2f}%  p75 {q[3]:.2f}%  p90 {q[4]:.2f}%")

    (HERE / "diag.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
