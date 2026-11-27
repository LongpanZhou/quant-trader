"""Step 1: do volume / order-flow proxies predict anything at 1m?

Builds day x minute matrices of QQQ flow features and measures conditional
forward returns of TQQQ.  Pure diagnostics; nothing here is a strategy yet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlib  # noqa: E402

NM = 390


def day_matrices(ts, op, cl, hi, lo, vo, k=0):
    dates, first, last, day_id = vlib.session_index(ts)
    nd = len(first)
    tod = vlib.tod_minutes(ts)
    M = {name: np.full((nd, NM), np.nan) for name in
         ("o", "c", "h", "l", "v", "sv", "clv")}
    for arr, name in ((op, "o"), (cl, "c"), (hi, "h"), (lo, "l"), (vo, "v")):
        M[name][day_id, tod] = arr[:, k]
    c, h, l, v = M["c"], M["h"], M["l"], M["v"]
    rng = np.where(h > l, h - l, np.nan)
    M["clv"] = np.where(h > l, ((c - l) - (h - c)) / rng, 0.0)
    M["clv"] = np.where(np.isnan(c), np.nan, M["clv"])
    M["sv"] = M["v"] * M["clv"]
    return dates, first, last, M


def cum_features(M):
    v = np.nan_to_num(M["v"])
    sv = np.nan_to_num(M["sv"])
    typ = np.nan_to_num((M["h"] + M["l"] + M["c"]) / 3.0)
    pv = typ * v
    cv = np.cumsum(v, axis=1)
    csv = np.cumsum(sv, axis=1)
    cpv = np.cumsum(pv, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        vwap = np.where(cv > 0, cpv / cv, np.nan)
        F = np.where(cv > 0, csv / cv, np.nan)
        dev = M["c"] / vwap - 1.0
    return cv, F, dev, vwap


def rolling_rvol(M):
    v = pd.DataFrame(M["v"])
    base = v.rolling(20, min_periods=10).mean().shift(1)
    return (v / base).to_numpy()


def fwd_ret(M, fwd):
    """Return opened at minute m+fwd+1 open?  Simpler: close-to-close fwd bars."""
    c = M["c"]
    out = np.full_like(c, np.nan)
    for j in range(fwd, NM):
        out[:, :NM - j] = c[:, j:] / c[:, :NM - j] - 1.0
    return out


def bucket_stats(x, y, qs=(0.05, 0.2, 0.4, 0.6, 0.8, 0.95)):
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    edges = np.quantile(x, qs)
    idx = np.searchsorted(edges, x)
    print(f"    n={len(x):,}  corr={np.corrcoef(x, y)[0, 1]:+.4f}")
    for b in range(len(edges) + 1):
        m = idx == b
        if m.sum() == 0:
            continue
        print(f"      b{b}: n={m.sum():>8,}  mean {y[m].mean()*1e4:+7.2f} bp  "
              f"median {np.median(y[m])*1e4:+7.2f} bp  win {100*(y[m]>0).mean():4.1f}%")


def main():
    ts, op, cl, hi, lo, vo = vlib.build_panel()
    dates, first, last, M = day_matrices(ts, op, cl, hi, lo, vo, k=1)  # TQQQ prices
    _, _, _, Q = day_matrices(ts, op, cl, hi, lo, vo, k=0)             # QQQ flow
    cvQ, FQ, devQ, vwapQ = cum_features(Q)
    cvT, FT, devT, vwapT = cum_features(M)
    rvolQ = rolling_rvol(Q)
    rvolT = rolling_rvol(M)

    # daily regime
    qclose = Q["c"][:, -1]
    sma = pd.Series(qclose).rolling(165).mean().to_numpy()
    reg = np.zeros(len(qclose), bool)
    reg[1:] = qclose[:-1] > sma[:-1]
    print("sessions", len(qclose), "risk-on", reg.sum(), f"({reg.mean()*100:.1f}%)")

    # forward 30m and 60m TQQQ returns
    r30 = fwd_ret(M, 30)
    r60 = fwd_ret(M, 60)

    # mask: risk-on day, after 10:00, before 15:00
    tod = np.arange(NM)
    ok_t = (tod >= 30) & (tod <= 330)
    mask = reg[:, None] & ok_t[None, :]

    print("\n== QQQ cumulative flow score F -> next 30m TQQQ return (risk-on, 10:00-15:00)")
    bucket_stats(FQ[mask], r30[mask])
    print("\n== QQQ VWAP deviation -> next 30m TQQQ return")
    bucket_stats(devQ[mask], r30[mask])
    cum_rvolQ = cvQ / np.nanmean(cvQ[reg], axis=0)[None, :]
    print("\n== QQQ cumulative RVOL -> next 30m TQQQ return")
    bucket_stats(cum_rvolQ[mask], r30[mask])
    print("\n== QQQ 1-bar RVOL -> next 30m TQQQ return")
    bucket_stats(rvolQ[mask], r30[mask])

    # overnight: last 30 min flow
    print("\n== end-of-day QQQ flow (15:30-15:59 aggregate) -> TQQQ overnight return")
    cT = M["c"]
    ov = np.full(len(cT), np.nan)
    ov[:-1] = M["o"][1:, 0] / cT[:-1, -1] - 1.0
    eod_F = np.nanmean(FQ[:, 360:], axis=1)
    eod_dev = np.nanmean(devQ[:, 360:], axis=1)
    eod_rvol = np.nanmean(rvolQ[:, 360:], axis=1)
    for name, x in (("F", eod_F), ("dev", eod_dev), ("rvol", eod_rvol)):
        y = np.where(reg, ov, np.nan)
        print(f"  {name}:")
        bucket_stats(x, y)

    # full-day flow and same-day return relation
    print("\n== full-day QQQ flow -> next-day TQQQ overnight")
    full_F = np.nanmean(FQ, axis=1)
    bucket_stats(full_F, np.where(reg, ov, np.nan))


if __name__ == "__main__":
    main()
