"""Overnight-drift + opening-30min timing on TQQQ, gated by a daily QQQ SMA.

Idea
----
Almost all of TQQQ's total return accrues outside the 09:30-16:00 session:
the close-to-open ("overnight") block has ~78% of TQQQ's log return over
2016-2026 while carrying roughly the same volatility as the intraday block
(see report.md).  The last 30 minutes are the worst block of the day and the
first 30 minutes are the second best.  The tradable atom is therefore

    long TQQQ from the open of the day's last 1-minute bar (~15:59)
    until the open of the bar at `exit_min` next morning (~10:00),
    otherwise cash (or BIL).

That block is entered and exited once per day, so it costs two fills a day -
the dominant cost of the design.  A daily QQQ 165-day SMA regime switches the
whole thing off in downtrends (2022, 2018H2, 2025Q1).

Everything is long-only, signals use data up to the close of bar i and fill at
the open of bar i+1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / "panel.npz"

START = "2017-01-03"
END = "2026-10-23"
WINDOWS = (("10y", "2017-01-03", "2026-10-23"), ("5y", "2021-10-25", "2026-10-23"))
BARS_PER_YEAR = 252 * 390

# benchmark (README, daily bars on the same windows)
BENCH = {
    "10y": {"cagr": 0.3928, "max_drawdown": 0.8168, "sharpe": 0.83},
    "5y": {"cagr": 0.1347, "max_drawdown": 0.8168, "sharpe": 0.53},
}
DAILY_BASELINE = {
    "10y": {"cagr": 0.4531, "max_drawdown": 0.5871, "sharpe": 1.00},
    "5y": {"cagr": 0.3461, "max_drawdown": 0.3686, "sharpe": 0.88},
}


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_panel(force: bool = False):
    """1m panel (ts, opens, closes) for QQQ/TQQQ/BIL, cached to npz."""
    if CACHE.exists() and not force:
        z = np.load(CACHE)
        ts = pd.to_datetime(z["ts"], unit=str(z["unit"]), utc=True).tz_convert(
            "America/New_York")
        return ts, z["opens"], z["closes"]
    ts, op, cl = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    naive = ts.tz_convert("UTC").tz_localize(None)
    np.savez(CACHE, ts=naive.astype("int64"), unit=str(naive.unit),
             opens=op, closes=cl)
    return ts, op, cl


def day_frame(ts: pd.DatetimeIndex) -> pd.DataFrame:
    df = pd.DataFrame({"date": ts.date, "minute": ts.hour * 60 + ts.minute})
    g = df.groupby("date", sort=False)
    out = pd.DataFrame({"first": g.indices.apply(lambda a: a[0]),
                        "last": g.indices.apply(lambda a: a[-1])})
    out.index = pd.to_datetime(out.index)
    return out


def daily_close(ts: pd.DatetimeIndex, p: np.ndarray) -> pd.Series:
    s = pd.Series(p, index=ts)
    return s.groupby(s.index.date).last()


def regime(dcl: pd.Series, n: int = 165, lag: int = 1) -> pd.Series:
    """Boolean regime, strictly causal for a 15:58 decision.

    lag=1: compare yesterday's close with the SMA of closes through yesterday.
    lag=0: compare the current 15:58 price with the SMA through yesterday.
    """
    sma = dcl.rolling(n).mean().shift(1)
    return (dcl.shift(lag) > sma).fillna(False)


def regime_band(dcl: pd.Series, n: int = 165, lag: int = 1, band: float = 0.0) -> pd.Series:
    """SMA regime with hysteresis: on above SMA*(1+band), off below SMA*(1-band)."""
    sma = dcl.rolling(n).mean().shift(1)
    px = dcl.shift(lag)
    up = (px > sma * (1.0 + band)).to_numpy()
    dn = (px < sma * (1.0 - band)).to_numpy()
    state = np.zeros(len(dcl), dtype=bool)
    cur = False
    for i in range(len(dcl)):
        if up[i]:
            cur = True
        elif dn[i]:
            cur = False
        state[i] = cur
    return pd.Series(state, index=dcl.index)


# --------------------------------------------------------------------------- #
# weights
# --------------------------------------------------------------------------- #
def build_weights(df: pd.DataFrame, reg: pd.Series, exit_min: int = 600,
                  day_asset: str = "cash", long_val: float = 1.0,
                  live_filter: np.ndarray | None = None) -> np.ndarray:
    """Long TQQQ from the last-bar open to `exit_min` next morning.

    `day_asset`: what to hold outside the block, 'cash' (TQQQ weight 0) or
    'bil'.  `live_filter` optionally masks individual nights (bool per bar).
    """
    n = len(df)
    minute = df["minute"].to_numpy()
    rows = np.full((n, 3), np.nan)
    reg_on = reg.reindex(df["date"]).to_numpy()
    if live_filter is None:
        live_filter = np.ones(n, dtype=bool)
    day_w = [0.0, 0.0, 1.0] if day_asset == "bil" else [0.0, 0.0, 0.0]

    idx = df.groupby("date", sort=False).indices
    dates = list(idx.keys())
    for k, d in enumerate(dates):
        a = idx[d]
        i0, i1 = a[0], a[-1]
        on = bool(reg_on[i0]) and bool(live_filter[i1 - 1]) if i1 > i0 else False
        rows[i1 - 1] = [0.0, long_val, 0.0] if on else np.array(day_w)
        if not on or k + 1 >= len(dates):
            continue
        nxt = idx[dates[k + 1]]
        seg = nxt
        j = int(np.searchsorted(minute[seg], exit_min))
        i_exit = seg[j] - 1 if j < len(seg) else seg[-1] - 1
        if i_exit < seg[0]:
            i_exit = seg[0] - 1
        rows[i_exit] = np.array(day_w)
    w = pd.DataFrame(rows).ffill().fillna(0.0).to_numpy()
    return w


def tom_flags(dates: pd.DatetimeIndex, n_beg: int = 3, n_end: int = 2) -> dict:
    """Turn-of-month mask: first `n_beg` or last `n_end` trading days of month."""
    s = pd.Series(1, index=pd.to_datetime(dates))
    per = s.index.to_period("M")
    rank_beg = s.groupby(per).cumcount()
    rank_end = s.groupby(per).transform("size") - 1 - rank_beg
    return dict(zip(s.index.date, (rank_beg < n_beg) | (rank_end < n_end)))


def build_weights_tom(df: pd.DataFrame, reg: pd.Series, exit_min: int = 601,
                      tom: dict | None = None, day_asset: str = "cash") -> np.ndarray:
    """Overnight block normally; hold the whole session on turn-of-month days.

    Semantics: at the morning exit (10:01 of day j) we stay in instead of
    exiting iff day j is a turn-of-month day.  So the position then covers
    day j's full session and exits at 10:01 of j+1.  All decisions use the
    trading calendar and prices known before the 10:01 fill.
    """
    n = len(df)
    minute = df["minute"].to_numpy()
    rows = np.full((n, 3), np.nan)
    reg_on = reg.reindex(df["date"]).to_numpy()
    day_w = np.array([0.0, 0.0, 1.0 if day_asset == "bil" else 0.0])
    idx = df.groupby("date", sort=False).indices
    dates = list(idx.keys())

    for k, d in enumerate(dates):
        a = idx[d]
        i0, i1 = a[0], a[-1]
        on = bool(reg_on[i0])
        if not on:
            rows[i1 - 1] = day_w
            continue
        rows[i1 - 1] = [0.0, 1.0, 0.0]
        if k + 1 >= len(dates):
            continue
        nxt = dates[k + 1]
        # skip the 10:01 exit of `nxt` if `nxt` is itself a TOM day
        if tom is not None and bool(tom.get(nxt, False)):
            continue
        seg = idx[nxt]
        j = int(np.searchsorted(minute[seg], exit_min))
        i_exit = seg[j] - 1 if j < len(seg) else seg[-1] - 1
        if i_exit < seg[0]:
            i_exit = seg[0] - 1
        rows[i_exit] = day_w
    return pd.DataFrame(rows).ffill().fillna(0.0).to_numpy()


def build_weights_24h(ts: pd.DatetimeIndex, reg: pd.Series, day_asset="bil") -> np.ndarray:
    """Reference: hold TQQQ all day when the regime is on (the daily baseline,
    executed at the 1m close instead of the next open)."""
    df = pd.DataFrame({"date": ts.date})
    rows = pd.DataFrame(np.where(reg.reindex(df["date"]).to_numpy()[:, None],
                                 np.array([[0.0, 1.0, 0.0]]),
                                 np.array([[0.0, 0.0, 1.0 if day_asset == "bil" else 0.0]])))
    rows.index = ts.date
    return rows.groupby(level=0, sort=False).last().reindex(ts.date).to_numpy()


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
def evaluate(w: np.ndarray, ts, op, cl, start: str, slippage: float = 1.0,
             band: float = 0.02):
    res = bt.run(ts, op, cl, w, start, band=band, slippage_bps=slippage)
    s = bt.stats(res, BARS_PER_YEAR)
    i = bt.start_index(ts, start)
    b = bt.benchmark(cl[i:, 1], ts[i:], BARS_PER_YEAR)
    return res, s, b


def run_all(w, ts, op, cl, slippage=1.0, band=0.02):
    out = {}
    for tag, lo, hi in WINDOWS:
        res, s, b = evaluate(w, ts, op, cl, lo, slippage, band)
        out[tag] = {"stats": s, "bench": b, "result": res}
    return out


def yearly_table(res, cl, ts, lo):
    i = bt.start_index(ts, lo)
    return bt.yearly(res["ts"], res["equity"], cl[i:, 1])


def show(label, out):
    print(f"\n{label}")
    for tag in ("10y", "5y"):
        s, b = out[tag]["stats"], out[tag]["bench"]
        print(f"  [{tag}] CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sharpe {s['sharpe']:4.2f}  fills {s['fills']:6d}  turn {s['turnover']:8.1f}x  "
              f"| bench {b['cagr']*100:6.2f}%/{b['max_drawdown']*100:5.2f}%")


def passes(out) -> dict:
    res = {}
    for tag in ("10y", "5y"):
        s = out[tag]["stats"]
        res[tag] = bool(s["cagr"] > BENCH[tag]["cagr"]
                        and s["max_drawdown"] < BENCH[tag]["max_drawdown"])
    res["both"] = res["10y"] and res["5y"]
    return res


def main():
    ts, op, cl = load_panel()
    df = pd.DataFrame({"date": ts.date, "minute": ts.hour * 60 + ts.minute})
    dcl = daily_close(ts, cl[:, 0])
    print(f"bars {len(ts):,} days {dcl.size:,}")

    variants = {}
    for lag, tag in ((1, "lag1"), (0, "same")):
        reg = regime(dcl, 165, lag)
        for exit_min, etag in ((571, "0931"), (601, "1001"), (631, "1031")):
            for da in ("cash", "bil"):
                key = f"ON {tag} exit{etag} {da}"
                variants[key] = build_weights(df, reg, exit_min, day_asset=da)
    reg165 = regime(dcl, 165, 1)
    variants["24h lag1 bil (baseline ref)"] = build_weights_24h(ts, reg165, "bil")
    variants["24h lag1 cash (baseline ref)"] = build_weights_24h(ts, reg165, "cash")

    rows = []
    for key, w in variants.items():
        out = run_all(w, ts, op, cl, 1.0)
        p = passes(out)
        rows.append({
            "variant": key,
            "cagr10": out["10y"]["stats"]["cagr"],
            "dd10": out["10y"]["stats"]["max_drawdown"],
            "sh10": out["10y"]["stats"]["sharpe"],
            "f10": out["10y"]["stats"]["fills"],
            "cagr5": out["5y"]["stats"]["cagr"],
            "dd5": out["5y"]["stats"]["max_drawdown"],
            "sh5": out["5y"]["stats"]["sharpe"],
            "f5": out["5y"]["stats"]["fills"],
            "pass": p["both"],
        })
        show(key, out)
    print("\n" + "=" * 130)
    t = pd.DataFrame(rows).set_index("variant")
    print(t.assign(cagr10=lambda x: (x.cagr10 * 100).round(2),
                   dd10=lambda x: (x.dd10 * 100).round(2),
                   cagr5=lambda x: (x.cagr5 * 100).round(2),
                   dd5=lambda x: (x.dd5 * 100).round(2)).round(2).to_string())


if __name__ == "__main__":
    main()
