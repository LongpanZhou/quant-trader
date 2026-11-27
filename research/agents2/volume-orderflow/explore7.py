"""Step 8: daily-level volume features as stress / participation signals."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402

pd.set_option("display.width", 220)


def fwd(c, h):
    out = np.full(len(c), np.nan)
    out[:-h] = c[h:] / c[:-h] - 1
    return out


def main():
    D = engine.Data()
    qc, qv = D.qc, D.qv_day
    qret = np.r_[np.nan, qc[1:] / qc[:-1] - 1]
    up = np.where(qret > 0, qv, 0.0)
    dn = np.where(qret < 0, qv, 0.0)
    s = lambda x, n: pd.Series(x).rolling(n, min_periods=max(2, n // 2)).sum().to_numpy()

    vp10 = np.log((s(up, 10) + 1) / (s(dn, 10) + 1))
    vp20 = np.log((s(up, 20) + 1) / (s(dn, 20) + 1))
    rvol20 = s(qv, 5) / s(qv, 60)
    rvol60 = s(qv, 20) / s(qv, 120)
    # volume trend: is participation expanding?
    vtrend = s(qv, 10) / s(qv, 50)

    feats = {"vp10": vp10, "vp20": vp20, "rvol5_60": rvol20, "rvol20_120": rvol60,
             "vtrend": vtrend, "rvol_day": D.rvol_day}
    tgt = {"1d": fwd(D.tc, 1), "5d": fwd(D.tc, 5), "20d": fwd(D.tc, 20)}

    def buck(x, y, label, q=5, sub=None):
        m = np.isfinite(x) & np.isfinite(y)
        if sub is not None:
            m &= sub
        x, y = x[m], y[m]
        if len(x) < 50:
            print(f"  {label}: n={len(x)} too few")
            return
        e = np.quantile(x, np.linspace(0, 1, q + 1)[1:-1])
        i = np.searchsorted(e, x)
        print(f"  {label:26s} n={len(x):4d} r={np.corrcoef(x,y)[0,1]:+.3f} | " + " ".join(
            f"{y[i==b].mean()*100:+5.2f}" for b in range(q)))

    for h in ("1d", "5d", "20d"):
        print(f"\n== forward TQQQ {h} return by daily volume feature (risk-on)")
        for name, x in feats.items():
            buck(x, tgt[h], name, sub=D.reg)

    print("\n== era split for the best two (5d forward)")
    for lab, a, b_ in (("2017-2019", "2017-01-01", "2020-01-01"),
                       ("2020-2021", "2020-01-01", "2022-01-01"),
                       ("2022-2026", "2022-01-01", "2027-01-01")):
        mk = D.reg & np.array([(pd.Timestamp(a).date() <= d < pd.Timestamp(b_).date())
                               for d in D.dates[D.first]])
        print(f"  {lab}")
        for name in ("vp10", "rvol5_60", "rvol_day"):
            buck(feats[name], tgt["5d"], name, sub=mk)

    print("\n== high-volume return premium check: rvol_day quantiles -> 20d fwd (all days)")
    buck(D.rvol_day, tgt["20d"], "rvol_day", sub=None)
    buck(D.rvol_day, tgt["1d"], "rvol_day", sub=None)


if __name__ == "__main__":
    main()
