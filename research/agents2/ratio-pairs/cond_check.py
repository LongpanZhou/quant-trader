"""Independent conditional-return check: does prior-close ext200 predict the
next session's open-to-open TQQQ return?  No harness, no weights."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bt_lib as L  # noqa: E402


def main():
    ts, opens, closes = L.load_panel()
    d = L.add_ratio_features(L.daily_frame(ts, opens, closes))
    dates, first, last = L.day_bounds(ts)
    nd = len(first)

    # open-to-open returns: hold from 09:31 of day k to 09:31 of day k+1
    o = opens[first]  # (nd, 3)
    r_tq = np.full(nd, np.nan)
    r_qq = np.full(nd, np.nan)
    r_tq[:-1] = o[1:, 1] / o[:-1, 1] - 1
    r_qq[:-1] = o[1:, 0] / o[:-1, 0] - 1
    # close-to-close for reference
    c_tq = d["tqqq_c"].to_numpy()
    cc_tq = np.r_[np.nan, c_tq[1:] / c_tq[:-1] - 1]

    ext = d["ext200"].shift(1).to_numpy()  # known at prior close
    yr = d.index.year.to_numpy()

    for theta in (0.16, 0.18, 0.20, 0.22):
        f = np.nan_to_num(ext, nan=-9) > theta
        ok = np.isfinite(r_tq) & np.isfinite(ext)
        f = f & ok
        nf = ~f & ok
        print(f"\ntheta {theta:.2f}: froth days {f.sum()} ({f.mean()*100:.1f}% of all days)")
        print(f"  open-open TQQQ: froth {r_tq[f].mean()*100:+.4f}%/day  "
              f"other {r_tq[nf].mean()*100:+.4f}%/day   diff {(r_tq[f].mean()-r_tq[nf].mean())*100:+.4f}")
        print(f"  open-open QQQ : froth {r_qq[f].mean()*100:+.4f}%/day  "
              f"other {r_qq[nf].mean()*100:+.4f}%/day")
        print(f"  cond-to-cond TQQQ: froth {np.nanmean(cc_tq[f]):+.4f}  other {np.nanmean(cc_tq[nf]):+.4f}")
        tab = pd.DataFrame({"yr": yr, "f": f, "tq": r_tq, "qq": r_qq})[ok]
        g = tab.groupby(["yr"]).apply(
            lambda x: pd.Series({
                "n_f": int(x["f"].sum()),
                "tq_f": x.loc[x["f"], "tq"].mean() * 100 if x["f"].any() else np.nan,
                "tq_o": x.loc[~x["f"], "tq"].mean() * 100,
                "qq_f": x.loc[x["f"], "qq"].mean() * 100 if x["f"].any() else np.nan,
            }), include_groups=False)
        print(g.to_string(float_format=lambda v: f"{v: .3f}"))

    # does the signal simply proxy for "ratio made a new high"?
    print("\ncorrelation of ext200(t-1) with same-day and next-day returns")
    for h, r in (("next open-open TQQQ", r_tq), ("next open-open QQQ", r_qq)):
        x, y = ext[:-1], r[:-1]
        ok = np.isfinite(x) & np.isfinite(y)
        print(f"  {h}: pearson {np.corrcoef(x[ok], y[ok])[0,1]:+.3f}  "
              f"spearman {pd.Series(x[ok]).rank().corr(pd.Series(y[ok]).rank()):+.3f}")

    # top/bottom froth-day returns in 2025 to explain the yearly jump
    print("\n2025 froth days (theta .18): date, ext200_prev, TQQQ o2o, QQQ o2o")
    f = np.nan_to_num(ext, nan=-9) > 0.18
    for k in np.flatnonzero(f & (yr == 2025)):
        print(f"  {d.index[k].date()}  {ext[k]*100:+6.1f}%  {r_tq[k]*100:+7.2f}%  {r_qq[k]*100:+6.2f}%")


if __name__ == "__main__":
    main()
