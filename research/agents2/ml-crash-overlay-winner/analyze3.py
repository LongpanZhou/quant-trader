"""Third exploration: overnight vs intraday decomposition and gap predictability."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from analyze2 import winner_daily  # noqa: E402

START, END = "2017-01-03", "2026-10-23"


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w, opened, stopped, last, first = winner_daily(ts, o, c)
    dates = np.array([t.date() for t in ts])
    f = pd.read_pickle(Path(__file__).parent / "features.pkl")
    f.index = pd.to_datetime(f.index)
    dts = pd.DatetimeIndex([pd.Timestamp(x) for x in dates[last]])
    qo = pd.Series(o[first, 1], index=dts)
    qc = pd.Series(c[last, 1], index=dts)
    qqc_o = pd.Series(o[first, 0], index=dts)
    qqc_c = pd.Series(c[last, 0], index=dts)
    bil_c = pd.Series(c[last, 2], index=dts)

    over = qo / qc.shift(1) - 1.0
    intra = qc / qo - 1.0
    d = pd.DataFrame({"held": opened, "stopped": stopped, "over": over, "intra": intra,
                      "q_over": qqc_o / qqc_c.shift(1) - 1.0,
                      "q_intra": qqc_c / qqc_o - 1.0}, index=dts).join(f, how="left")
    d["bil_ret"] = bil_c.pct_change()

    m = d.index >= pd.Timestamp("2017-01-03")
    q = d[m & d.held]
    print("winner-held days:", len(q))
    print(f"overnight mean {q.over.mean()*100:.4f}%  median {q.over.median()*100:.4f}%  "
          f"std {q.over.std()*100:.2f}%  min {q.over.min()*100:.1f}%")
    print(f"intraday  mean {q.intra.mean()*100:.4f}%  median {q.intra.median()*100:.4f}%  "
          f"std {q.intra.std()*100:.2f}%  min {q.intra.min()*100:.1f}%")
    print(f"gap<-2% days {(q.over<-0.02).sum()}  gap<-1% {(q.over<-0.01).sum()}  "
          f"intra<-2% {(q.intra<-0.02).sum()}")

    print("\nconditional mean overnight / intraday by feature decile:")
    for col in ["rv_pct", "last30", "vwap_dist", "dd_high", "rsi14", "sma20", "decay20", "gap"]:
        x = q[col].to_numpy()
        for tgt in ("over", "intra"):
            y = q[tgt].to_numpy()
            ok = np.isfinite(x) & np.isfinite(y)
            qs = np.quantile(x[ok], np.linspace(0, 1, 11))
            qs[0] -= 1e-12
            idx = np.clip(np.searchsorted(qs, x[ok], side="right") - 1, 0, 9)
            means = [y[ok][idx == k].mean() * 100 for k in range(10)]
            print(f"  {col:11s} {tgt:5s} " + " ".join(f"{v:5.2f}" for v in means))

    print("\nOracle avoid-overnight (perfect forecast of gap) on winner-held days:")
    base = q["over"].to_numpy() + q["intra"].to_numpy()  # approx total day return while held
    # Use actual strategy daily return for non-swapped days later; here simple decomposition
    for thr in (-0.01, -0.02, -0.03):
        mask = q["over"].to_numpy() < thr
        alt = np.where(mask, q["bil_ret"].to_numpy(), base)
        sr = pd.Series(alt, index=q.index)
        eq = (1 + sr.fillna(0)).cumprod()
        yrs = (q.index[-1] - q.index[0]).days / 365.25
        cagr = eq.iloc[-1] ** (1 / yrs) - 1
        peak = np.maximum.accumulate(eq)
        dd = -(eq / peak - 1).min()
        print(f"  gap<{thr*100:4.0f}%: n={mask.sum():3d} CAGR {cagr*100:6.2f}% DD {dd*100:6.2f}% "
              f"Sharpe {sr.mean()/sr.std()*np.sqrt(252):5.2f}")

    print("\nOracle avoid-intraday:")
    for thr in (-0.01, -0.02, -0.03):
        mask = q["intra"].to_numpy() < thr
        alt = np.where(mask, q["bil_ret"].to_numpy(), base)
        sr = pd.Series(alt, index=q.index)
        eq = (1 + sr.fillna(0)).cumprod()
        yrs = (q.index[-1] - q.index[0]).days / 365.25
        cagr = eq.iloc[-1] ** (1 / yrs) - 1
        peak = np.maximum.accumulate(eq)
        dd = -(eq / peak - 1).min()
        print(f"  intra<{thr*100:4.0f}%: n={mask.sum():3d} CAGR {cagr*100:6.2f}% DD {dd*100:6.2f}% "
              f"Sharpe {sr.mean()/sr.std()*np.sqrt(252):5.2f}")

    # correlation of prior-day features with next overnight gap
    print("\ncorr(feature at close d-1, overnight gap d):")
    for col in ["rv_pct", "last30", "vwap_dist", "dd_high", "rsi14", "sma20", "sma165",
                "decay20", "gap", "range20", "dvol20", "close_loc", "intraday", "first30"]:
        x = q[col].to_numpy()
        y = q["over"].to_numpy()
        ok = np.isfinite(x) & np.isfinite(y)
        print(f"  {col:11s} {np.corrcoef(x[ok], y[ok])[0,1]: .3f}")

    print("\nregression-style crash-day overlap: fraction of big down days that are gap vs intraday")
    big = q[(q.over + q.intra) < -0.05]
    print("  n", len(big), " gap<-2%", (big.over < -0.02).mean(), " intra<-2%", (big.intra < -0.02).mean())
    big3 = q[(q.over + q.intra) < -0.03]
    print("  n", len(big3), " gap<-2%", (big3.over < -0.02).mean(), " intra<-2%", (big3.intra < -0.02).mean())


if __name__ == "__main__":
    main()
