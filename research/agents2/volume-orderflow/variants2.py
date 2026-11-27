"""Step 10: volume-weighted regime variants (VWAP / OBV / A-D line) at the daily gate."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402


def daily_hl(D):
    h = np.array([np.nanmax(D.hi[D.first[d]:D.last[d] + 1, 0]) for d in range(D.nd)])
    l = np.array([np.nanmin(D.lo[D.first[d]:D.last[d] + 1, 0]) for d in range(D.nd)])
    return h, l


def signals(D, n=165):
    qc, qv = D.qc, D.qv_day
    h, l = daily_hl(D)
    typ = (h + l + qc) / 3.0
    # volume-weighted average price over n days (trailing, excluding today)
    pv = pd.Series(typ * qv)
    vv = pd.Series(qv)
    vwap_n = (pv.rolling(n).sum() / vv.rolling(n).sum()).to_numpy()
    vwap_n = np.r_[np.nan, vwap_n[:-1]]
    # OBV
    ret = np.r_[np.nan, np.diff(qc)]
    obv = np.nancumsum(np.sign(np.nan_to_num(ret)) * qv)
    obv_ma = pd.Series(obv).rolling(n).mean().to_numpy()
    obv_ma = np.r_[np.nan, obv_ma[:-1]]
    # accumulation/distribution
    rng = np.where(h > l, h - l, np.nan)
    clv = np.where(h > l, ((qc - l) - (h - qc)) / rng, 0.0)
    ad = np.nancumsum(np.nan_to_num(clv) * qv)
    ad_ma = pd.Series(ad).rolling(n).mean().to_numpy()
    ad_ma = np.r_[np.nan, ad_ma[:-1]]
    return {"vwap": vwap_n, "obv": obv_ma, "ad": ad_ma, "typ": typ}


def regime_from(D, cond):
    r = np.zeros(D.nd, bool)
    r[1:] = cond[:-1]
    return r


def weights_regime(D, reg):
    w = np.zeros((D.n, 3))
    w[:, 1] = reg[D.day_id]
    w[:, 2] = 1 - w[:, 1]
    return w


def main():
    D = engine.Data()
    print("baseline regimes (no intraday stop)")
    w = weights_regime(D, D.reg)
    engine.evaluate(D, w, "price > SMA165 (round-1 gate)")

    for n in (100, 150, 165, 200):
        s = signals(D, n)
        sma = pd.Series(D.qc).rolling(n).mean().to_numpy()
        for name, cond in (
            (f"price>SMA{n}", D.qc > sma),
            (f"price>VWAP{n}", D.qc > s["vwap"]),
            (f"price>SMA{n} & SMA200", (D.qc > sma) & (D.qc > pd.Series(D.qc).rolling(200).mean().to_numpy())),
        ):
            reg = regime_from(D, cond)
            w = weights_regime(D, reg)
            engine.evaluate(D, w, name)

    print("\n-- OBV / AD gates on top of price>SMA165")
    s = signals(D, 165)
    base = D.qc > pd.Series(D.qc).rolling(165).mean().to_numpy()
    ret = np.r_[np.nan, np.diff(D.qc)]
    obv_lvl = np.nancumsum(np.sign(np.nan_to_num(ret)) * D.qv_day)
    obv_ma = np.r_[np.nan, pd.Series(obv_lvl).rolling(165).mean().to_numpy()[:-1]]
    h, l = daily_hl(D)
    rng = np.where(h > l, h - l, np.nan)
    clv = np.where(h > l, ((D.qc - l) - (h - D.qc)) / rng, 0.0)
    ad_lvl = np.nancumsum(np.nan_to_num(clv) * D.qv_day)
    ad_ma = np.r_[np.nan, pd.Series(ad_lvl).rolling(165).mean().to_numpy()[:-1]]
    obv20 = np.r_[np.nan, pd.Series(obv_lvl).rolling(20).mean().to_numpy()[:-1]]
    ad20 = np.r_[np.nan, pd.Series(ad_lvl).rolling(20).mean().to_numpy()[:-1]]

    for lab, cond in (
        ("price>SMA165", base),
        ("price>SMA165 & OBV>MA165", base & (obv_lvl > obv_ma)),
        ("price>SMA165 & OBV>MA20", base & (obv_lvl > obv20)),
        ("price>SMA165 & AD>MA165", base & (ad_lvl > ad_ma)),
        ("price>SMA165 & AD>MA20", base & (ad_lvl > ad20)),
        ("price>SMA165 | OBV>MA165", base | (obv_lvl > obv_ma)),
    ):
        reg = regime_from(D, cond)
        w = weights_regime(D, reg)
        engine.evaluate(D, w, f"{lab}  (on {reg.mean()*100:.0f}%)")


if __name__ == "__main__":
    main()
