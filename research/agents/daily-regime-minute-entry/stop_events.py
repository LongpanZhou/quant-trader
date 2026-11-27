"""Event-level attribution of the 4% intraday stop."""
import numpy as np
import pandas as pd

import strat_lib as sl

A = sl.load_arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
oc, oo = A["closes"], A["opens"]
reg, dc, sma, _, _, _ = sl.daily_regime(ts, oc[:, 0], 165)
n = len(ts)
c = oc[:, 1]


def stop_events(x=0.04):
    ev = []
    for k, (f, l) in enumerate(zip(first, last)):
        if not reg[f] or k + 1 >= len(first):
            continue
        base = oo[f, 1]
        for i in range(f, l + 1):
            if c[i] < base * (1 - x):
                nxt = first[k + 1]
                ev.append(dict(date=dates[f], time=ts[i].time(), stop_px=c[i],
                               close_px=c[l], next_open=oo[nxt, 1],
                               close_ret=c[l] / base - 1,
                               stop_to_close=c[l] / c[i] - 1,
                               night=oo[nxt, 1] / c[l] - 1,
                               stop_to_next=oo[nxt, 1] / c[i] - 1))
                break
    return pd.DataFrame(ev)


for x in (0.035, 0.04, 0.045):
    ev = stop_events(x)
    print(f"\n=== stop {x*100:.1f}%: {len(ev)} events ===")
    print("by year:")
    g = ev.groupby(ev["date"].astype(str).str[:4]).agg(
        n=("date", "size"), stop_to_close=("stop_to_close", "mean"),
        night=("night", "mean"), stop_to_next=("stop_to_next", "mean"),
        worst=("stop_to_next", "min"))
    print(g.round(4).to_string())
    print(f"mean stop->close {ev['stop_to_close'].mean()*100:+.3f}%  mean night {ev['night'].mean()*100:+.3f}%  "
          f"mean stop->next {ev['stop_to_next'].mean()*100:+.3f}%")
    print(f"median stop->next {ev['stop_to_next'].median()*100:+.3f}%  share<0 {np.mean(ev['stop_to_next']<0)*100:.1f}%")
    if x == 0.04:
        print("\ntop 12 events by stop->next:")
        print(ev.sort_values("stop_to_next")[["date", "time", "close_ret", "stop_to_close", "night", "stop_to_next"]]
              .head(12).round(4).to_string(index=False))
        print("\ntop 12 events by +stop->next:")
        print(ev.sort_values("stop_to_next", ascending=False)[["date", "time", "close_ret", "stop_to_close", "night", "stop_to_next"]]
              .head(12).round(4).to_string(index=False))
        print("\nhour of stop:")
        print(ev["time"].astype(str).str[:2].value_counts().sort_index().to_string())
