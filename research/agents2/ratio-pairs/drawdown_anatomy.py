"""Drawdown anatomy and ratio-state diagnostics for the round-1 winner."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from explore import load_daily  # noqa: E402

START10, START5, END = "2017-01-03", "2021-10-25", "2026-10-23"
BARS = 252 * 390
CACHE = ROOT / "research" / "agents" / "daily-regime-minute-entry" / "panel_cache.npz"


def winner_weights(ts, opens, closes, sma_n=165, stop=0.04, ma_fast=20, arm_buf=0.01):
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    dclose = qqq_close[last]
    sma = pd.Series(dclose).rolling(sma_n).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(ma_fast).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    hold = np.zeros(n, bool)
    for f, l in zip(first, last):
        k = int(day_id[f])
        if k == 0 or not (sma_prev[k] == sma_prev[k] and dclose[k - 1] > sma_prev[k]):
            continue
        armed = bool(ma20_prev[k] == ma20_prev[k] and qqq_close[f] < ma20_prev[k] * (1 + arm_buf))
        base = opens[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tqqq_close[i] < base * (1 - stop):
                state = False
            hold[i] = state
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1 - w[:, 1]
    return w


def main():
    z = np.load(CACHE)
    ts = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York"))
    opens, closes = z["opens"], z["closes"]
    w = winner_weights(ts, opens, closes)
    r = bt.run(ts, opens, closes, w, START10, band=0.02, slippage_bps=1.0)
    eq = pd.Series(r["equity"], index=r["ts"])
    deq = eq.groupby(eq.index.date).last()
    deq.index = pd.to_datetime(deq.index)
    peak = deq.cummax()
    dd = deq / peak - 1

    d = load_daily()
    d.index = d.index.tz_localize(None).normalize()
    d["ma200"] = d["ratio"].rolling(200).mean()
    d["ext200"] = np.log(d["ratio"] / d["ma200"])
    d["ma60"] = d["ratio"].rolling(60).mean()
    d["ext60"] = np.log(d["ratio"] / d["ma60"])
    d["dd252"] = d["ratio"] / d["ratio"].rolling(252).max() - 1

    # worst 12 drawdown episodes at daily resolution
    under = dd < -0.10
    grp = (under != under.shift()).cumsum()
    eps = []
    for g, seg in dd[under].groupby(grp[under]):
        eps.append((seg.index[0], seg.index[-1], seg.min(), (seg.index[-1] - seg.index[0]).days))
    eps = sorted(eps, key=lambda x: x[2])[:8]
    print("worst winner drawdown episodes (daily marks) and ratio state at the prior peak")
    for a, b, m, days in eps:
        pk = deq[:a].idxmax()
        x = d.loc[pk] if pk in d.index else None
        print(f"  {a.date()} -> {b.date()}  dd {m*100:6.2f}%  {days:4d}d   "
              f"ratio peak {pk.date()} ext200 {x['ext200']*100:6.1f}%  dd252 {x['dd252']*100:6.1f}%  "
              f"ext60 {x['ext60']*100:6.1f}%")

    print("\nmonthly winner DD and ratio extension")
    m = pd.DataFrame({"dd": dd, "ext200": d["ext200"], "ext60": d["ext60"],
                      "dd252": d["dd252"], "ratio": d["ratio"]})
    mm = m.resample("ME").last()
    for y in range(2017, 2027):
        row = mm[mm.index.year == y]
        s = " ".join(
            f"{ts_.month:02d}:{v.dd*100:5.1f}/{v.ext200*100:5.0f}"
            for ts_, v in row.iterrows()
        )
        print(f"{y}  dd/ext200  {s}")

    print("\nforward 20d TQQQ return by ext200 bucket and year")
    entry = d["tqqq_o"].shift(-1)
    f20 = d["tqqq_c"].shift(-20) / entry - 1
    b = pd.cut(d["ext200"], [-1, -0.10, 0.0, 0.10, 0.16, 0.22, 1.0])
    tab = pd.DataFrame({"b": b, "f20": f20}).dropna()
    tab["year"] = tab.index.year
    print(tab.pivot_table(index="year", columns="b", values="f20", aggfunc="mean", observed=False)
          .to_string(float_format=lambda v: f"{v*100:6.1f}"))
    print("\ncounts")
    print(tab.pivot_table(index="year", columns="b", values="f20", aggfunc="size", observed=False).to_string())


if __name__ == "__main__":
    main()
