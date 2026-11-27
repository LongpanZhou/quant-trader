"""Step 2: day-level feature table + event studies for flow proxies."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlib  # noqa: E402
from explore1 import day_matrices, cum_features, rolling_rvol  # noqa: E402

pd.set_option("display.width", 180)


def last_valid(A):
    nd, nm = A.shape
    idx = np.where(np.isfinite(A), np.arange(nm)[None, :], -1).max(axis=1)
    return A[np.arange(nd), np.maximum(idx, 0)]


def at_time(A, m, valid=None):
    """Feature value at minute index m, using the last valid value <= m."""
    nd = A.shape[0]
    sub = A[:, : m + 1]
    return last_valid(sub)


def main():
    ts, op, cl, hi, lo, vo = vlib.build_panel()
    Q = day_matrices(ts, op, cl, hi, lo, vo, k=0)[3]
    T = day_matrices(ts, op, cl, hi, lo, vo, k=1)[3]
    cvQ, FQ, devQ, vwapQ = cum_features(Q)
    cvT, FT, devT, vwapT = cum_features(T)
    rvolQ = rolling_rvol(Q)
    rvolT = rolling_rvol(T)

    qc, qo = last_valid(Q["c"]), Q["o"][:, 0]
    tc, to = last_valid(T["c"]), T["o"][:, 0]
    nd = len(qc)
    # session lengths and covers
    qv = np.nan_to_num(Q["v"]).sum(1)
    dvol = Q["v"].sum(1)  # NaN-safe-ish

    sma = pd.Series(qc).rolling(165).mean().to_numpy()
    reg = np.zeros(nd, bool)
    reg[1:] = qc[:-1] > sma[:-1]

    dates, first, last, _ = vlib.session_index(ts)
    feats = pd.DataFrame({"date": dates[first]})
    feats["reg"] = reg
    feats["qqq_ret"] = qc / qo - 1
    feats["tqqq_ret"] = tc / to - 1
    feats["tqqq_ov"] = np.r_[np.nan, to[1:] / tc[:-1] - 1]
    for m, tag in ((30, "1000"), (60, "1030"), (120, "1130"), (210, "1300"),
                   (300, "1430"), (330, "1500")):
        feats[f"F_{tag}"] = at_time(FQ, m)
        feats[f"dev_{tag}"] = at_time(devQ, m)
        feats[f"rvol_{tag}"] = at_time(rvolQ, m)
    for m, tag in ((330, "T1500"), (359, "T1559")):
        feats[f"FT_{tag}"] = at_time(FT, m)
    # last-30-min flow: mean of F over the last 30 valid bars is not causal-free;
    # instead use F at 15:59 minus F at 15:29 (incremental flow of the last 30m)
    feats["F_last30"] = at_time(FQ, 359) - at_time(FQ, 329)
    feats["F_last60"] = at_time(FQ, 359) - at_time(FQ, 299)
    feats["dev_close"] = at_time(devQ, 359)
    feats["rvol_day"] = dvol / pd.Series(dvol).rolling(20, min_periods=10).mean().shift(1).to_numpy()

    ok = feats["reg"].to_numpy(bool)
    print(f"risk-on share {ok.mean()*100:.1f}%  n={ok.sum()}")

    def buck(x, y, label, q=5, sub=None):
        m = np.isfinite(x) & np.isfinite(y)
        if sub is not None:
            m &= sub
        x, y = x[m], y[m]
        if len(x) < 30:
            print(f"  {label}: n={len(x)} too few")
            return
        e = np.quantile(x, np.linspace(0, 1, q + 1)[1:-1])
        idx = np.searchsorted(e, x)
        print(f"  {label}: n={len(x)} corr={np.corrcoef(x, y)[0,1]:+.3f}")
        rows = []
        for b in range(q):
            s = idx == b
            rows.append(f"q{b} n={s.sum():>4} mean {y[s].mean()*1e4:+7.1f}bp "
                        f"med {np.median(y[s])*1e4:+7.1f}bp win {100*(y[s]>0).mean():4.1f}%")
        print("     " + " | ".join(rows))

    print("\n== overnight TQQQ return conditioned on QQQ flow/price features (risk-on days)")
    for col in ("F_1500", "F_last30", "F_last60", "dev_close", "rvol_day"):
        buck(feats[col].to_numpy(), feats["tqqq_ov"].to_numpy(), col, sub=ok)

    print("\n== next-day intraday TQQQ return conditioned on the same features")
    nd_intr = np.r_[feats["tqqq_ret"].to_numpy()[1:], np.nan]
    for col in ("F_1500", "F_last30", "dev_close", "rvol_day"):
        buck(feats[col].to_numpy(), nd_intr, col, sub=reg)

    print("\n== intraday down-day continuation: TQQQ intraday < -3%")
    down = feats["tqqq_ret"].to_numpy() < -0.03
    rest = np.r_[tc[0], tc[:-1]]
    # return from 15:00 close to session close (proxy for what is left after 15:00)
    c1500 = at_time(T["c"], 329)
    feats["t_from1500"] = tc / c1500 - 1
    for col, lab in (("rvol_day", "daily RVOL"), ("F_1500", "flow@15:00"),
                     ("dev_close", "vwap dev@close")):
        print(f"  -- {lab} (down days, n={down.sum()})")
        buck(feats[col].to_numpy(), feats["tqqq_ov"].to_numpy(), f"{lab}->overnight", sub=down)
        buck(feats[col].to_numpy(), feats["t_from1500"].to_numpy(), f"{lab}->15:00-close", sub=down)


if __name__ == "__main__":
    main()
