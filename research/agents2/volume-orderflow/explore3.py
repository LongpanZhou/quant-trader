"""Step 3: alternative flow proxies + controls (is volume just volatility?)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlib  # noqa: E402
from explore1 import day_matrices, cum_features, rolling_rvol  # noqa: E402
from explore2 import last_valid, at_time  # noqa: E402

pd.set_option("display.width", 200)


def tick_flow(M):
    """Tick-rule signed volume cumulated within the day, normalised."""
    d = np.diff(M["c"], axis=1, prepend=np.nan)
    sgn = np.sign(np.nan_to_num(d))
    sv = sgn * np.nan_to_num(M["v"])
    cv = np.cumsum(np.nan_to_num(M["v"]), axis=1)
    cs = np.cumsum(sv, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(cv > 0, cs / cv, np.nan)


def ud_pressure(M):
    """log(up-volume / down-volume) cumulated, clipped."""
    d = np.diff(M["c"], axis=1, prepend=np.nan)
    v = np.nan_to_num(M["v"])
    up = np.cumsum(np.where(np.nan_to_num(d) > 0, v, 0.0), axis=1) + 1.0
    dn = np.cumsum(np.where(np.nan_to_num(d) < 0, v, 0.0), axis=1) + 1.0
    return np.log(up / dn)


def main():
    ts, op, cl, hi, lo, vo = vlib.build_panel()
    dates, first, last, _ = vlib.session_index(ts)
    Q = day_matrices(ts, op, cl, hi, lo, vo, k=0)[3]
    T = day_matrices(ts, op, cl, hi, lo, vo, k=1)[3]
    cvQ, FQ, devQ, _ = cum_features(Q)
    rvolQ = rolling_rvol(Q)
    TKQ = tick_flow(Q)
    UDQ = ud_pressure(Q)

    qc, qo = last_valid(Q["c"]), Q["o"][:, 0]
    tc, to = last_valid(T["c"]), T["o"][:, 0]
    nd = len(qc)
    sma = pd.Series(qc).rolling(165).mean().to_numpy()
    reg = np.zeros(nd, bool)
    reg[1:] = qc[:-1] > sma[:-1]

    # QQQ daily realized vol over prior 20 sessions
    qret = np.r_[np.nan, qc[1:] / qc[:-1] - 1]
    rv20 = pd.Series(qret).rolling(20).std().to_numpy()
    rv60 = pd.Series(qret).rolling(60).std().to_numpy()

    f = pd.DataFrame({"date": dates[first]})
    f["reg"] = reg
    f["q_ret"] = qc / qo - 1
    f["t_ret"] = tc / to - 1
    f["q_absret"] = np.abs(f["q_ret"])
    f["t_ov"] = np.r_[np.nan, to[1:] / tc[:-1] - 1]
    f["rv20"] = rv20
    f["rv60"] = rv60
    f["rvol_day"] = (np.nan_to_num(Q["v"]).sum(1)
                     / pd.Series(np.nan_to_num(Q["v"]).sum(1)).rolling(20).mean().shift(1).to_numpy())
    f["F_1500"] = at_time(FQ, 300)
    f["F_close"] = at_time(FQ, 359)
    f["TK_1500"] = at_time(TKQ, 300)
    f["TK_close"] = at_time(TKQ, 359)
    f["UD_1500"] = at_time(UDQ, 300)
    f["UD_close"] = at_time(UDQ, 359)
    f["dev_close"] = at_time(devQ, 359)
    f["ret_1500"] = at_time(Q["c"], 300) / qo - 1
    f["ret_first30"] = at_time(Q["c"], 29) / qo - 1
    f["ret_last30"] = qc / at_time(Q["c"], 329) - 1
    f["t_last30"] = tc / at_time(T["c"], 329) - 1

    def buck(x, y, label, q=5, sub=None):
        m = np.isfinite(x) & np.isfinite(y)
        if sub is not None:
            m &= sub
        x, y = x[m], y[m]
        if len(x) < 40:
            print(f"  {label}: n={len(x)} too few")
            return
        e = np.quantile(x, np.linspace(0, 1, q + 1)[1:-1])
        idx = np.searchsorted(e, x)
        print(f"  {label}: n={len(x)} r={np.corrcoef(x, y)[0,1]:+.3f}")
        print("     " + " | ".join(
            f"q{b} {y[idx==b].mean()*1e4:+6.1f}/{np.median(y[idx==b])*1e4:+6.1f}bp "
            f"w{100*(y[idx==b]>0).mean():4.1f}%" for b in range(q)))

    ok = f["reg"].to_numpy(bool)
    print("== overnight TQQQ: flow proxies (risk-on)")
    for c in ("TK_close", "TK_1500", "UD_close", "UD_1500"):
        buck(f[c].to_numpy(), f["t_ov"].to_numpy(), c, sub=ok)

    print("\n== control: is rvol just volatility?  overnight by rvol within rv20 halves")
    med = np.nanmedian(rv20)
    for lab, sub in (("low rv20", ok & (rv20 < med)), ("high rv20", ok & (rv20 >= med))):
        buck(f["rvol_day"].to_numpy(), f["t_ov"].to_numpy(), f"rvol|{lab}", sub=sub)
    print("\n== control: rv20 alone -> overnight")
    buck(f["rv20"].to_numpy(), f["t_ov"].to_numpy(), "rv20", sub=ok)
    print("== control: |daily ret| -> overnight")
    buck(f["q_absret"].to_numpy(), f["t_ov"].to_numpy(), "|ret|", sub=ok)

    print("\n== joint: high rvol (>1.5) crossed with day return sign")
    hi = np.nan_to_num(f["rvol_day"].to_numpy()) > 1.5
    for lab, sub in (("rvol>1.5 & down", ok & hi & (f["q_ret"].to_numpy() < 0)),
                     ("rvol>1.5 & up", ok & hi & (f["q_ret"].to_numpy() > 0)),
                     ("rvol<=1.5 & down", ok & ~hi & (f["q_ret"].to_numpy() < 0)),
                     ("rvol<=1.5 & up", ok & ~hi & (f["q_ret"].to_numpy() > 0))):
        y = f["t_ov"].to_numpy()[sub]
        y = y[np.isfinite(y)]
        print(f"  {lab:20s} n={len(y):4d} mean {y.mean()*1e4:+7.1f}bp "
              f"med {np.median(y)*1e4:+6.1f}bp win {100*(y>0).mean():4.1f}% "
              f"p05 {np.quantile(y,0.05)*1e4:+7.0f}bp")

    print("\n== market intraday momentum: first30 -> last30 (QQQ and TQQQ)")
    for c, y in (("ret_first30", "ret_last30"), ("ret_first30", "t_last30")):
        buck(f[c].to_numpy(), f[y].to_numpy(), f"{c}->{y}", sub=ok)
    print("  -- split by rvol_day median")
    mrv = np.nanmedian(f["rvol_day"].to_numpy())
    for lab, sub in (("lowrvol", ok & (f["rvol_day"].to_numpy() < mrv)),
                     ("hirvol", ok & (f["rvol_day"].to_numpy() >= mrv))):
        buck(f["ret_first30"].to_numpy(), f["t_last30"].to_numpy(),
             f"first30->tlast30|{lab}", sub=sub)


if __name__ == "__main__":
    main()
