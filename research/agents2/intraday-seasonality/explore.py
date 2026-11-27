"""Descriptive intraday-seasonality study on local 1-minute QQQ/TQQQ/BIL.

Builds a daily table of intraday block returns, calendar flags and regime state,
then prints conditional means (bp/day, t-stats) split in-sample (2017-2021) and
out-of-sample (2022-2026).

Run:
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/agents2/intraday-seasonality/explore.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

OUT = Path(__file__).resolve().parent
CACHE = OUT / "panel.npz"
START, END = "2017-01-03", "2026-10-23"
SMA_N = 165


def load_panel(force: bool = False):
    if CACHE.exists() and not force:
        z = np.load(CACHE, allow_pickle=True)
        ts = pd.DatetimeIndex(pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York"))
        return ts, z["opens"], z["closes"]
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=500)
    np.savez_compressed(
        CACHE,
        ts=ts.tz_convert("UTC").tz_localize(None).to_numpy(dtype="datetime64[ns]").astype("int64"),
        opens=opens, closes=closes,
    )
    return ts, opens, closes


def bar_index(ts: pd.DatetimeIndex, first: np.ndarray, last: np.ndarray, hh: int, mm: int) -> np.ndarray:
    """Index of the first bar at or after hh:mm within each session."""
    target = hh * 60 + mm
    mins = ts.hour.to_numpy() * 60 + ts.minute.to_numpy()
    out = np.empty(len(first), dtype=np.int64)
    for k, (f, l) in enumerate(zip(first, last)):
        j = np.searchsorted(mins[f:l + 1], target)
        out[k] = min(f + j, l)
    return out


def day_bounds(dates: np.ndarray):
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    return first, last


def holiday_flags(dates: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """pre-holiday / post-holiday from missing weekdays in the sample."""
    d = pd.DatetimeIndex(pd.to_datetime(list(dates)))
    weekdays = pd.bdate_range(d[0], d[-1])
    missing = weekdays.difference(d)
    pre = np.zeros(len(d), bool)
    post = np.zeros(len(d), bool)
    pos = {x: i for i, x in enumerate(d)}
    for m in missing:
        before = m - pd.Timedelta(days=1)
        while before not in pos and before > d[0]:
            before -= pd.Timedelta(days=1)
        after = m + pd.Timedelta(days=1)
        while after not in pos and after < d[-1]:
            after += pd.Timedelta(days=1)
        if before in pos:
            pre[pos[before]] = True
        if after in pos:
            post[pos[after]] = True
    return pre, post


def opex_flags(dates: np.ndarray):
    """OpEx week = week containing the third Friday; also +1 / -1 week."""
    d = pd.DatetimeIndex(pd.to_datetime(list(dates)))
    # third Friday of each month
    third = []
    for p in pd.period_range(d[0], d[-1], freq="M"):
        first = p.to_timestamp()
        fridays = [first + pd.Timedelta(days=k) for k in range(31)
                   if (first + pd.Timedelta(days=k)).month == first.month
                   and (first + pd.Timedelta(days=k)).weekday() == 4]
        third.append(fridays[2])
    third = pd.DatetimeIndex(third)
    week_start = third - pd.to_timedelta(third.weekday, unit="D")  # Monday
    opex_week = np.zeros(len(d), bool)
    pre_week = np.zeros(len(d), bool)
    post_week = np.zeros(len(d), bool)
    for ws in week_start:
        we = ws + pd.Timedelta(days=4)
        opex_week |= (d >= ws) & (d <= we)
        pre_week |= (d >= ws - pd.Timedelta(days=7)) & (d <= we - pd.Timedelta(days=7))
        post_week |= (d >= ws + pd.Timedelta(days=7)) & (d <= we + pd.Timedelta(days=7))
    return opex_week, pre_week, post_week


def build_table():
    ts, opens, closes = load_panel()
    dates_all = np.array([t.date() for t in ts])
    first, last = day_bounds(dates_all)
    dates = dates_all[first]
    n_days = len(first)

    idx = {}
    for hh, mm in ((9, 30), (9, 31), (9, 35), (10, 0), (11, 30), (12, 0),
                   (13, 0), (14, 0), (15, 0), (15, 30), (15, 58), (15, 59)):
        idx[(hh, mm)] = bar_index(ts, first, last, hh, mm)

    def px_open(sym, hhmm):
        return opens[idx[hhmm], sym]

    def px_close(sym, hhmm):
        return closes[idx[hhmm], sym]

    tab = pd.DataFrame({"date": pd.to_datetime(list(dates))})
    tab["dow"] = tab["date"].dt.weekday
    tab["year"] = tab["date"].dt.year
    tab["month"] = tab["date"].dt.month

    for sym, s in (("q", 0), ("t", 1), ("b", 2)):
        tab[f"{sym}_open"] = px_open(s, (9, 30))
        tab[f"{sym}_c0931"] = px_close(s, (9, 31))
        tab[f"{sym}_c0935"] = px_close(s, (9, 35))
        tab[f"{sym}_c1000"] = px_close(s, (10, 0))
        tab[f"{sym}_c1130"] = px_close(s, (11, 30))
        tab[f"{sym}_c1200"] = px_close(s, (12, 0))
        tab[f"{sym}_c1400"] = px_close(s, (14, 0))
        tab[f"{sym}_c1500"] = px_close(s, (15, 0))
        tab[f"{sym}_c1530"] = px_close(s, (15, 30))
        tab[f"{sym}_close"] = px_close(s, (15, 59))

    for sym in ("q", "t"):
        c = tab[f"{sym}_close"]
        o = tab[f"{sym}_open"]
        tab[f"{sym}_prev_close"] = c.shift(1)
        tab[f"{sym}_gap"] = o / c.shift(1) - 1.0
        tab[f"{sym}_on"] = tab[f"{sym}_gap"]          # overnight block
        tab[f"{sym}_m1"] = tab[f"{sym}_c0931"] / o - 1.0
        tab[f"{sym}_m5"] = tab[f"{sym}_c0935"] / tab[f"{sym}_c0931"] - 1.0
        tab[f"{sym}_m5g"] = tab[f"{sym}_c0935"] / o - 1.0   # open -> 09:35
        tab[f"{sym}_f30"] = tab[f"{sym}_c1000"] / o - 1.0   # first 30m
        tab[f"{sym}_morning"] = tab[f"{sym}_c1200"] / o - 1.0
        tab[f"{sym}_lunch"] = tab[f"{sym}_c1400"] / tab[f"{sym}_c1200"] - 1.0
        tab[f"{sym}_earlypm"] = tab[f"{sym}_c1500"] / tab[f"{sym}_c1400"] - 1.0
        tab[f"{sym}_l1"] = tab[f"{sym}_c1530"] / tab[f"{sym}_c1500"] - 1.0
        tab[f"{sym}_l2"] = tab[f"{sym}_close"] / tab[f"{sym}_c1530"] - 1.0
        tab[f"{sym}_last60"] = tab[f"{sym}_close"] / tab[f"{sym}_c1500"] - 1.0
        tab[f"{sym}_last30"] = tab[f"{sym}_l2"]
        tab[f"{sym}_session"] = tab[f"{sym}_close"] / o - 1.0
        tab[f"{sym}_cc"] = c / c.shift(1) - 1.0
        tab[f"{sym}_am_pm"] = tab[f"{sym}_session"]

    # regime: QQQ daily close vs 165d SMA, signal at prior close
    dc = tab["q_close"]
    sma = dc.rolling(SMA_N).mean()
    tab["regime"] = (dc.shift(1) > sma.shift(1)).astype(float)
    ma20 = dc.rolling(20).mean()
    tab["ma20"] = ma20
    tab["dist_ma20"] = dc / ma20 - 1.0

    pre, post = holiday_flags(dates)
    tab["pre_hol"] = pre
    tab["post_hol"] = post
    op, prew, postw = opex_flags(dates)
    tab["opex"] = op
    tab["pre_opex"] = prew
    tab["post_opex"] = postw
    # day of month rank from end
    tab["is_month_end"] = tab["date"].dt.is_month_end
    return tab, ts, opens, closes, first, last


def stat(x: np.ndarray) -> tuple[float, float, int]:
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return np.nan, np.nan, len(x)
    m = x.mean() * 1e4
    se = x.std(ddof=1) / np.sqrt(len(x)) * 1e4
    return m, m / se if se > 0 else np.nan, len(x)


def report_block(tab, col, mask, label, periods):
    rows = []
    for pname, m in periods:
        m = m & mask
        mean, t, n = stat(tab.loc[m, col].to_numpy())
        rows.append((pname, mean, t, n))
    print(f"  {label:28s} " + "  ".join(f"{p}: {mn:7.2f}bp t={t:5.2f} n={n:4d}" for p, mn, t, n in rows))


def main():
    tab, ts, opens, closes, first, last = build_table()
    tab = tab[tab["date"] >= "2016-01-04"].reset_index(drop=True)
    is_mask = tab["date"] < "2022-01-01"
    oos_mask = tab["date"] >= "2022-01-01"
    periods = [("IS17-21", is_mask), ("OOS22-26", oos_mask)]

    print(f"days: {len(tab)}  IS {is_mask.sum()}  OOS {oos_mask.sum()}")
    print("\n=== unconditional block means, TQQQ (bp/day) ===")
    for col in ("t_on", "t_m1", "t_m5", "t_f30", "t_morning", "t_lunch",
                "t_earlypm", "t_l1", "t_l2", "t_last60", "t_session", "t_cc"):
        report_block(tab, col, np.ones(len(tab), bool), col, periods)

    print("\n=== 1. opening 5-minute reversal, by gap bucket (TQQQ m5 = 09:31->09:35) ===")
    bins = [-1, -0.02, -0.01, -0.005, 0.0, 0.005, 0.01, 0.02, 1]
    lab = ["<-2%", "-2..-1", "-1..-.5", "-.5..0", "0..+.5", "+.5..1", "+1..2", ">2%"]
    g = pd.cut(tab["t_gap"], bins, labels=lab)
    for L in lab:
        m = (g == L).to_numpy()
        report_block(tab, "t_m5", m, f"gap {L}", periods)
        report_block(tab, "t_m5g", m, f"gap {L} (o->935)", periods)

    print("\n=== 2. lunch 12:00-14:00 vs morning (TQQQ) ===")
    g2 = pd.cut(tab["t_morning"], [-1, -0.03, -0.015, -0.005, 0.005, 0.015, 0.03, 1],
                labels=["<-3%", "-3..-1.5", "-1.5..-.5", "-.5..+.5", "+.5..1.5", "+1.5..3", ">3%"])
    for L in ["<-3%", "-3..-1.5", "-1.5..-.5", "-.5..+.5", "+.5..1.5", "+1.5..3", ">3%"]:
        m = (g2 == L).to_numpy()
        report_block(tab, "t_lunch", m, f"morning {L}", periods)
        report_block(tab, "t_earlypm", m, f"  12-14 {L} earlypm", periods)

    print("\n=== 3. last hour by first-30m bucket ===")
    g3 = pd.cut(tab["q_f30"], [-1, -0.01, -0.005, -0.002, 0.002, 0.005, 0.01, 1],
                labels=["<-1%", "-1..-.5", "-.5..-.2", "-.2..+.2", "+.2..+.5", "+.5..1", ">1%"])
    for L in ["<-1%", "-1..-.5", "-.5..-.2", "-.2..+.2", "+.2..+.5", "+.5..1", ">1%"]:
        m = (g3 == L).to_numpy()
        report_block(tab, "t_last60", m, f"QQQ f30 {L}", periods)
        report_block(tab, "t_l2", m, f"  last30 {L}", periods)

    print("\n=== 4. day of week, TQQQ blocks ===")
    for dow, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"]):
        m = (tab["dow"] == dow).to_numpy()
        print(f"  {name}:")
        for col in ("t_on", "t_session", "t_morning", "t_lunch", "t_last60", "t_cc"):
            report_block(tab, col, m, f"  {col}", periods)

    print("\n=== 5. OpEx week ===")
    for flag in ("opex", "pre_opex", "post_opex"):
        m = tab[flag].to_numpy()
        print(f"  {flag} (n={m.sum()}):")
        for col in ("t_on", "t_session", "t_morning", "t_lunch", "t_last60", "t_cc"):
            report_block(tab, col, m, f"  {col}", periods)
    m = ~(tab["opex"] | tab["pre_opex"] | tab["post_opex"]).to_numpy()
    print("  other weeks:")
    for col in ("t_on", "t_session", "t_cc"):
        report_block(tab, col, m, f"  {col}", periods)

    print("\n=== 6. pre/post holiday ===")
    for flag in ("pre_hol", "post_hol"):
        m = tab[flag].to_numpy()
        print(f"  {flag} (n={m.sum()}):")
        for col in ("t_on", "t_session", "t_morning", "t_lunch", "t_last60", "t_cc"):
            report_block(tab, col, m, f"  {col}", periods)
    m = ~(tab["pre_hol"] | tab["post_hol"]).to_numpy()
    print("  normal days:")
    for col in ("t_on", "t_session", "t_last60", "t_cc"):
        report_block(tab, col, m, f"  {col}", periods)

    print("\n=== day-of-week x overnight, QQQ ===")
    for dow, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"]):
        m = (tab["dow"] == dow).to_numpy()
        report_block(tab, "q_on", m, f"{name} QQQ overnight", periods)


if __name__ == "__main__":
    main()
