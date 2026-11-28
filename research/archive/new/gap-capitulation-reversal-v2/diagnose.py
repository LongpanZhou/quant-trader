"""Dev-only event/definition diagnostics for gap-capitulation-reversal v2.

Exploratory, NOT the pre-registered grid.  Data is physically filtered to
2015-01-01 .. 2023-12-29 before use; 2024+ is never materialised.

    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/new/gap-capitulation-reversal-v2/diagnose.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
TZ = "America/New_York"


def qqq_daily_extras():
    """Daily QQQ low and volume, physically filtered to the dev window."""
    p = ROOT / "data" / "intraday-hf" / "QQQ-1m.parquet"
    lo = pd.Timestamp("2015-01-01", tz=TZ)
    hi = pd.Timestamp(DEV_END, tz=TZ) + pd.Timedelta(days=1)
    df = pd.read_parquet(p, columns=["ts", "low", "volume"],
                         filters=[("ts", ">=", lo.tz_convert("UTC")),
                                  ("ts", "<", hi.tz_convert("UTC"))])
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert(TZ)
    df = df[(df["ts"].dt.time >= pd.Timestamp("09:30").time())
            & (df["ts"].dt.time < pd.Timestamp("16:00").time())].copy()
    df["date"] = df["ts"].dt.date
    g = df.groupby("date")
    return g["low"].min(), g["volume"].sum()


def daily_frame(ts, o, c, qlow_s, qvol_s):
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    sess = pd.DatetimeIndex(sorted(set(pd.Timestamp(t.date()) for t in ts)))
    qlow = qlow_s.reindex(pd.Index([d.date() for d in sess])).to_numpy(float)
    qvol = qvol_s.reindex(pd.Index([d.date() for d in sess])).to_numpy(float)
    qo, qc = o[first, 0], c[last, 0]
    to, tc = o[first, 1], c[last, 1]
    prior = np.r_[np.nan, qc[:-1]]
    qret = qc / prior - 1.0
    qdd = qlow / prior - 1.0
    q20 = pd.Series(qc).pct_change(20).to_numpy()
    rvol = qvol / pd.Series(qvol).shift(1).rolling(20).mean().to_numpy()
    vol20 = pd.Series(qret).rolling(20).std(ddof=0).to_numpy() * np.sqrt(252.0)
    return dict(dates=dates, first=first, last=last, nd=len(first), qo=qo, qc=qc,
                to=to, tc=tc, qret=qret, qdd=qdd, q20=q20, rvol=rvol, vol20=vol20)


def forward_ret(d, o, c, s, hold, col):
    """Entry at open of session s, exit at close of s+hold-1."""
    if s < 1 or s + hold - 1 >= d["nd"]:
        return np.nan
    ent = o[d["first"][s], col]
    ex = c[d["last"][s + hold - 1], col]
    return float(ex / ent - 1.0)


def mask_stats(d, o, c, mask, hold, col):
    rs = np.array([forward_ret(d, o, c, s + 1, hold, col)
                   for s in range(d["nd"]) if mask[s] and np.isfinite(mask[s])])
    rs = rs[np.isfinite(rs)]
    if len(rs) < 3:
        return dict(n=int(len(rs)))
    t = float(rs.mean() / rs.std(ddof=1) * np.sqrt(len(rs))) if rs.std(ddof=1) > 0 else None
    return dict(n=int(len(rs)), mean=float(rs.mean()), median=float(np.median(rs)),
                win=float((rs > 0).mean()), t=t)


def build_mask(d, drop, intraday, rvol_max, oversold):
    cap = (d["qret"] <= -drop) | (d["qdd"] <= -intraday)
    quiet = d["rvol"] <= rvol_max
    over = d["q20"] <= -oversold
    fin = (np.isfinite(d["qret"]) & np.isfinite(d["qdd"]) & np.isfinite(d["rvol"])
           & np.isfinite(d["q20"]) & np.isfinite(d["vol20"]))
    return cap & quiet & over & fin, cap, quiet, over


def sequential_held_days(d, mask, hold):
    """Count held days under one-position-at-a-time, clock-reset-on-event."""
    active_until = -1
    held = 0
    starts = 0
    for s in range(1, d["nd"]):
        if mask[s - 1]:
            was = s <= active_until
            active_until = max(active_until, (s - 1) + hold)
            if not was:
                starts += 1
        if s <= active_until:
            held += 1
    return held, starts


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min")
    assert ts[-1] < pd.Timestamp("2023-12-30", tz=TZ)
    qlow_s, qvol_s = qqq_daily_extras()
    d = daily_frame(ts, o, c, qlow_s, qvol_s)
    nd = d["nd"]

    base, cap, quiet, over = build_mask(d, 0.020, 0.030, 1.20, 0.030)
    print(f"sessions={nd}  cap={cap.sum()}  cap&quiet={(cap & quiet).sum()}  "
          f"cap&over={(cap & over).sum()}  base={base.sum()}")
    for hold in (3, 5, 10):
        held, starts = sequential_held_days(d, base, hold)
        print(f"  base hold={hold}: starts={starts} held_days={held} "
              f"exposure={held / (nd - 1) * 100:.2f}%")

    print("\n-- event counts by year (base)")
    yrs = pd.Series([d["dates"][d["first"][s]].year for s in range(nd) if base[s]])
    print(yrs.value_counts().sort_index().to_dict())

    print("\n-- definition grid (count / TQQQ fwd mean / t / win)")
    grid = []
    for drop in (0.015, 0.020, 0.025):
        for rvol_max in (1.2, 1.3, 1.5):
            for oversold in (0.02, 0.03):
                m, _, _, _ = build_mask(d, drop, 0.030, rvol_max, oversold)
                st3 = mask_stats(d, o, c, m, 3, 1)
                st5 = mask_stats(d, o, c, m, 5, 1)
                held5, starts5 = sequential_held_days(d, m, 5)
                rec = dict(drop=drop, intraday=0.03, rvol_max=rvol_max,
                           oversold=oversold, n=int(m.sum()),
                           tqqq3=st3, tqqq5=st5, starts5=starts5,
                           expo5=held5 / (nd - 1))
                grid.append(rec)
                print(f"drop={drop:.3f} rvol<={rvol_max:.1f} over={oversold:.2f} "
                      f"n={rec['n']:3d} 3d={st3.get('mean', np.nan)*100:6.2f}% "
                      f"t={st3.get('t', np.nan):5.2f} 5d={st5.get('mean', np.nan)*100:6.2f}% "
                      f"t={st5.get('t', np.nan):5.2f} starts={starts5:3d} "
                      f"expo5={rec['expo5']*100:5.1f}%")

    print("\n-- base event study by hold and asset")
    for hold in (1, 3, 5, 10):
        for col, name in ((0, "QQQ"), (1, "TQQQ")):
            print(f"  hold={hold:2d} {name:4s} {mask_stats(d, o, c, base, hold, col)}")

    print("\n-- volume split (3d/5d TQQQ)")
    for name, m in (("quiet", base), ("heavy", cap & (~quiet) & over),
                    ("no_volume", cap & over)):
        print(f"  {name:9s} n={int(m.sum()):3d} 3d={mask_stats(d,o,c,m,3,1)} "
              f"5d={mask_stats(d,o,c,m,5,1)}")

    print("\n-- base events list")
    rows = []
    for s in range(nd):
        if not base[s]:
            continue
        rows.append(dict(date=str(d["dates"][d["first"][s]]),
                         qret=float(d["qret"][s]), qdd=float(d["qdd"][s]),
                         q20=float(d["q20"][s]), rvol=float(d["rvol"][s]),
                         vol20=float(d["vol20"][s]),
                         tq3=mask_stats(d, o, c, np.eye(1, nd, s, dtype=bool).ravel(), 3, 1).get("mean")))
    for r in rows:
        print(f"  {r['date']} qret={r['qret']*100:6.2f}% qdd={r['qdd']*100:6.2f}% "
              f"q20={r['q20']*100:6.2f}% rvol={r['rvol']:4.2f} vol20={r['vol20']*100:5.1f}% "
              f"tq3={r['tq3']*100 if r['tq3'] is not None else float('nan'):6.2f}%")

    (HERE / "diagnose.json").write_text(json.dumps(dict(base_n=int(base.sum()),
                                                        grid=grid, events=rows),
                                                   indent=1, default=float))
    print("\nwrote", HERE / "diagnose.json")


if __name__ == "__main__":
    main()
