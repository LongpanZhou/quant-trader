"""Exploratory statistics for the TQQQ/QQQ leverage ratio.

Builds a daily frame from the 1-minute panel, then asks whether the ratio's
trend / mean reversion predicts TQQQ's relative performance.  Purely
diagnostic: signals at close t are matched to forward close-to-close returns.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

START10, END = "2017-01-03", "2026-10-23"
CACHE = ROOT / "research" / "agents" / "daily-regime-minute-entry" / "panel_cache.npz"


def load_daily():
    if CACHE.exists():
        z = np.load(CACHE)
        ts = pd.DatetimeIndex(
            pd.to_datetime(z["ts"], unit="ns", utc=True).tz_convert("America/New_York")
        )
        opens, closes = z["opens"], z["closes"]
    else:  # pragma: no cover
        ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min", 500)
    dates = np.array(ts.date)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    d = pd.DataFrame(
        {
            "qqq_o": opens[first, 0],
            "qqq_c": closes[last, 0],
            "tqqq_o": opens[first, 1],
            "tqqq_c": closes[last, 1],
            "bil_c": closes[last, 2],
        },
        index=pd.DatetimeIndex(ts[last]).normalize(),
    )
    # first-bar close (09:30) is the opening print of the session
    d["qqq_1m"] = closes[first, 0]
    d["tqqq_1m"] = closes[first, 1]
    d["ratio"] = d["tqqq_c"] / d["qqq_c"]
    d["logr"] = np.log(d["ratio"])
    return d


def rank_corr(x: pd.Series, y: pd.Series) -> float:
    if len(x) < 10:
        return float("nan")
    return float(x.rank().corr(y.rank()))


def ic_table(d: pd.DataFrame) -> None:
    r = d["ratio"]
    lr = d["logr"]
    sig = {}
    for n in (10, 20, 60, 120, 200):
        ma = r.rolling(n).mean()
        sig[f"logR/MA{n}"] = np.log(r / ma)
    vol20 = lr.diff().rolling(20).std()
    sig["z20"] = sig["logR/MA20"] / vol20
    sig["z60"] = sig["logR/MA60"] / (lr.diff().rolling(60).std())
    for n in (5, 20, 60, 120):
        sig[f"mom{n}"] = lr - lr.shift(n)
    sig["dd252"] = r / r.rolling(252).max() - 1.0
    sig["rsi14"] = (
        lr.diff().clip(lower=0).rolling(14).mean()
        / lr.diff().abs().rolling(14).mean()
    )

    tq = d["tqqq_c"]
    qq = d["qqq_c"]
    fwd = {}
    for h in (1, 5, 20, 60):
        # traded from next open to the close h days later: no look-ahead
        entry = d["tqqq_o"].shift(-1)
        fwd[f"tqqq_h{h}"] = tq.shift(-h) / entry - 1.0
        fwd[f"qqq_h{h}"] = qq.shift(-h) / d["qqq_o"].shift(-1) - 1.0
        fwd[f"exc_h{h}"] = fwd[f"tqqq_h{h}"] - 3.0 * fwd[f"qqq_h{h}"]

    mask = d.index >= pd.Timestamp(START10, tz="America/New_York")
    rows = []
    for name, s in sig.items():
        row = {"signal": name}
        for h in (1, 5, 20, 60):
            x = s[mask]
            y = fwd[f"tqqq_h{h}"][mask]
            ok = x.notna() & y.notna()
            row[f"ic_tq{h}"] = rank_corr(x[ok], y[ok])
            y2 = fwd[f"exc_h{h}"][mask]
            ok2 = x.notna() & y2.notna()
            row[f"ic_exc{h}"] = rank_corr(x[ok2], y2[ok2])
        rows.append(row)
    print("\nSpearman IC, signal at close t vs forward return from next open")
    print(pd.DataFrame(rows).to_string(index=False, float_format=lambda v: f"{v: .3f}"))


def quintiles(d: pd.DataFrame) -> None:
    mask = d.index >= pd.Timestamp(START10, tz="America/New_York")
    entry = d["tqqq_o"].shift(-1)
    fwd5 = d["tqqq_c"].shift(-5) / entry - 1.0
    fwd20 = d["tqqq_c"].shift(-20) / entry - 1.0
    for name, s in (
        ("logR/MA20", np.log(d["ratio"] / d["ratio"].rolling(20).mean())),
        ("logR/MA60", np.log(d["ratio"] / d["ratio"].rolling(60).mean())),
        ("logR/MA200", np.log(d["ratio"] / d["ratio"].rolling(200).mean())),
        ("mom20", d["logr"] - d["logr"].shift(20)),
        ("dd252", d["ratio"] / d["ratio"].rolling(252).max() - 1.0),
    ):
        x = s[mask]
        q = pd.qcut(x, 5, labels=False, duplicates="drop")
        tab = pd.DataFrame(
            {"q": q, "f5": fwd5[mask], "f20": fwd20[mask], "x": x}
        ).dropna()
        g = tab.groupby("q").agg(
            n=("f5", "size"), x_lo=("x", "min"), x_hi=("x", "max"),
            f5=("f5", "mean"), f20=("f20", "mean"),
            f5_hit=("f5", lambda v: float((v > 0).mean())),
        )
        print(f"\nQuintiles of {name}")
        print(g.to_string(float_format=lambda v: f"{v: .4f}"))


def regime_ic(d: pd.DataFrame) -> None:
    """Does the ratio signal add information inside the QQQ 165d regime?"""
    mask = d.index >= pd.Timestamp(START10, tz="America/New_York")
    qma = d["qqq_c"].rolling(165).mean()
    on = (d["qqq_c"] > qma).shift(1)  # known at previous close, same as strategy
    entry = d["tqqq_o"].shift(-1)
    fwd5 = d["tqqq_c"].shift(-5) / entry - 1.0
    z60 = np.log(d["ratio"] / d["ratio"].rolling(60).mean())
    for name, sel in (("risk_on", on), ("risk_off", ~on)):
        x = z60[mask & sel]
        y = fwd5[mask & sel]
        ok = x.notna() & y.notna()
        print(f"{name}: n={ok.sum():4d}  corr(z60,fwd5)={rank_corr(x[ok], y[ok]): .3f}")
        q = pd.qcut(x[ok], 4, labels=False, duplicates="drop")
        print(pd.DataFrame({"q": q, "y": y[ok]}).groupby("q")["y"].agg(["size", "mean"]).to_string())


def main() -> None:
    d = load_daily()
    print(f"daily rows {len(d)}  {d.index[0].date()} .. {d.index[-1].date()}")
    print(d[["qqq_c", "tqqq_c", "ratio"]].describe().to_string())
    print("\nratio change: annualized drift by year")
    y = d["logr"].diff().groupby(d.index.year).agg(["sum", "std", "count"])
    y["ann_drift"] = np.exp(y["sum"] * 252 / y["count"]) - 1
    print(y.to_string(float_format=lambda v: f"{v: .4f}"))
    ic_table(d)
    quintiles(d)
    regime_ic(d)


if __name__ == "__main__":
    main()
