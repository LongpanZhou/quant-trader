"""Development-only evidence: what does the 30-min ORB predict forward?

No strategy weights yet; just conditional forward returns on 2016-2023.
"""
from __future__ import annotations

import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
sys.path.insert(0, "research/revisit/opening-range-breakout")
import bt  # noqa: E402
from dev_explore import load_dev, day_index, daily_q, START, END  # noqa: E402


def main():
    ts, o, c, q, t, b = load_dev()
    dates, starts, ends = day_index(ts)
    uniq = np.array(dates[starts])
    qh = q["high"].to_numpy(); ql = q["low"].to_numpy()
    qc = q["close"].to_numpy(); qo = q["open"].to_numpy()
    th = t["high"].to_numpy(); tl = t["low"].to_numpy()
    tc = t["close"].to_numpy(); to = t["open"].to_numpy()

    # daily OHLC from the minute panel (last/first bar)
    d = pd.DataFrame({"date": dates, "qo": qo, "qh": qh, "ql": ql, "qc": qc,
                      "to": to, "th": th, "tl": tl, "tc": tc})
    dd = d.groupby("date").agg(qo=("qo", "first"), qh=("qh", "max"), ql=("ql", "min"),
                               qc=("qc", "last"), to=("to", "first"), th=("th", "max"),
                               tl=("tl", "min"), tc=("tc", "last"))
    # 30-min OR levels
    orh = np.full(len(starts), np.nan); orl = np.full(len(starts), np.nan)
    oro = np.full(len(starts), np.nan); orc = np.full(len(starts), np.nan)
    for k, (s, e) in enumerate(zip(starts, ends)):
        j = min(s + 30, e)
        orh[k] = th[s:j].max(); orl[k] = tl[s:j].min()
        oro[k] = to[s]; orc[k] = tc[j - 1]
    dd = dd.copy()
    dd["or_h"] = orh; dd["or_l"] = orl; dd["or_o"] = oro; dd["or_c"] = orc
    dd["or_w"] = (dd["or_h"] - dd["or_l"]) / dd["qc"]
    dd["above_or"] = dd["tc"] > dd["or_h"]
    dd["below_or"] = dd["tc"] < dd["or_l"]
    dd["or_up"] = dd["or_c"] > dd["or_o"]
    dd["close_pos"] = (dd["tc"] - dd["tl"]) / (dd["th"] - dd["tl"])
    dd["on_next"] = dd["to"].shift(-1) / dd["tc"] - 1
    dd["oc_next"] = dd["qc"].shift(-1) / dd["qo"].shift(-1) - 1
    dd["cc1"] = dd["qc"].shift(-1) / dd["qc"] - 1
    dd["cc3"] = dd["qc"].shift(-3) / dd["qc"] - 1
    dd["cc5"] = dd["qc"].shift(-5) / dd["qc"] - 1
    dd["or_w_med"] = dd["or_w"].rolling(20, min_periods=10).median().shift(1)
    dd["narrow"] = dd["or_w"] <= dd["or_w_med"]
    dd["wide"] = dd["or_w"] >= dd["or_w_med"]

    x = dd.dropna(subset=["on_next", "cc1"]).copy()
    print(f"dev days {len(x)}  {x.index[0]} .. {x.index[-1]}")

    groups = {
        "all": pd.Series(True, index=x.index),
        "above_or": x["above_or"],
        "below_or": x["below_or"],
        "or_up": x["or_up"],
        "above_or & or_up": x["above_or"] & x["or_up"],
        "above_or & close_pos>.7": x["above_or"] & (x["close_pos"] > 0.7),
        "above_or & narrow": x["above_or"] & x["narrow"],
        "above_or & wide": x["above_or"] & x["wide"],
        "or_up & narrow": x["or_up"] & x["narrow"],
        "or_up & wide": x["or_up"] & x["wide"],
    }
    print(f"{'group':26s} {'n':>5s} {'on%':>8s} {'oc%':>8s} {'cc1%':>8s} {'cc5%':>8s} {'t(on)':>7s}")
    for name, m in groups.items():
        m = m.fillna(False)
        g = x[m]
        if len(g) < 5:
            continue
        tstat = g["on_next"].mean() / (g["on_next"].std(ddof=1) / np.sqrt(len(g))) if len(g) > 1 else 0
        print(f"{name:26s} {len(g):5d} {g['on_next'].mean()*100:+8.3f} "
              f"{g['oc_next'].mean()*100:+8.3f} {g['cc1'].mean()*100:+8.3f} "
              f"{g['cc5'].mean()*100:+8.3f} {tstat:7.2f}")

    # Compounded return of simple overnight-only rules on TQQQ (BIL otherwise)
    print("\nSimple overnight-only rules (TQQQ overnight when signal, BIL otherwise):")
    for name, m in groups.items():
        m = m.fillna(False)
        r = x.loc[m, "on_next"].dropna()
        if len(r) < 5:
            continue
        # compound on signal nights, 0 otherwise, over the full dev span
        rr = np.where(m.reindex(x.index).to_numpy(), x["on_next"].fillna(0).to_numpy(), 0.0)
        eq = np.cumprod(1 + rr)
        yrs = (x.index[-1] - x.index[0]).days / 365.25
        cagr = eq[-1] ** (1 / yrs) - 1
        print(f"  {name:26s} n={len(r):4d}  overnight-only CAGR {cagr*100:6.2f}%  mean {r.mean()*100:+.3f}%")

    # Same for next-day close-to-close (hold from today's close to tomorrow's close)
    print("\n1-day close-to-close rules:")
    for name, m in groups.items():
        m = m.fillna(False)
        r = x.loc[m, "cc1"].dropna()
        if len(r) < 5:
            continue
        rr = np.where(m.reindex(x.index).to_numpy(), x["cc1"].fillna(0).to_numpy(), 0.0)
        eq = np.cumprod(1 + rr)
        yrs = (x.index[-1] - x.index[0]).days / 365.25
        cagr = eq[-1] ** (1 / yrs) - 1
        print(f"  {name:26s} n={len(r):4d}  CAGR {cagr*100:6.2f}%  mean {r.mean()*100:+.3f}%")


if __name__ == "__main__":
    main()
