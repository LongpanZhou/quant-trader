"""Trade log and exposure diagnostics for the chosen ORB variant."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
sys.path.insert(0, "research/agents/opening-range-breakout")
import bt
import orb_core as oc
from bench import load_all, START10


def main():
    ts, opens, closes, q, t, b = load_all()
    d = oc.daily_tables(ts, q, t)
    cfg = dict(or_min=30, signal="QQQ", stop="orlow", intraday_only=False)
    w, info = oc.build_weights(ts, q, t, d, cfg)
    res = bt.run(ts, opens, closes, w, START10, band=0.02, slippage_bps=1.0)

    tt = w[:, 1]
    trades = []
    inpos = False
    entry_i = None
    for i in range(len(ts) - 1):
        if not inpos and tt[i] > 0:
            inpos = True
            entry_i = i + 1
        elif inpos and tt[i] == 0:
            exit_i = i + 1
            trades.append(dict(entry=ts[entry_i], exit=ts[exit_i],
                               entry_px=opens[entry_i, 1], exit_px=opens[exit_i, 1],
                               ret=opens[exit_i, 1] / opens[entry_i, 1] - 1,
                               days=(ts[exit_i] - ts[entry_i]).total_seconds() / 86400))
            inpos = False
    if inpos:
        trades.append(dict(entry=ts[entry_i], exit=ts[-1], entry_px=opens[entry_i, 1],
                           exit_px=opens[-1, 1], ret=opens[-1, 1] / opens[entry_i, 1] - 1,
                           days=(ts[-1] - ts[entry_i]).total_seconds() / 86400))
    tr = pd.DataFrame(trades)
    tr = tr[tr["entry"] >= pd.Timestamp(START10, tz="America/New_York")]
    print(f"trades {len(tr)}  win {(tr.ret>0).mean()*100:.1f}%  avg {tr.ret.mean()*100:+.1f}%  "
          f"median {tr.ret.median()*100:+.1f}%  avg_days {tr.days.mean():.0f}  max_days {tr.days.max():.0f}")
    print(tr.to_string())

    # exposure
    longs = pd.Series(w[:, 1] > 0, index=ts)
    print("\nexposure % by year:")
    print((longs.groupby(longs.index.year).mean() * 100).round(1))

    # stop distance at entry, QQQ OR range
    dates, starts, ends = oc.day_arrays(ts)
    uniq = dates[starts]
    orh, orl, oro, orc = oc.orb_hl(q, starts, ends, 30)
    scl = q["close"].to_numpy()
    dist = []
    for _, row in tr.iterrows():
        i = ts.searchsorted(row["entry"])
        k = np.searchsorted(np.array([ts[s] for s in starts]), ts[i])
        # first bar of the day containing entry i
        k = np.searchsorted(starts, i, side="right") - 1
        dist.append(orl[k] / scl[i] - 1)
    dist = np.array(dist)
    print(f"\nQQQ OR-low to entry-close distance: mean {dist.mean()*100:.2f}%  "
          f"median {np.median(dist)*100:.2f}%  p10 {np.percentile(dist,10)*100:.2f}%  "
          f"p90 {np.percentile(dist,90)*100:.2f}%")
    print(f"TQQQ stop is the same percentage: median {abs(np.median(dist))*100:.2f}% below entry")
    print(f"QQQ OR30 range as % of price: median {np.median((orh-orl)/scl[starts])*100:.2f}%")


if __name__ == "__main__":
    main()
