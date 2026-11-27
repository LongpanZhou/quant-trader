"""Conditional anatomy: when does the overnight / first-30m block pay?"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

pd.set_option("display.width", 200)


def qstats(x, label):
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    if len(x) < 10:
        print(f"{label:44s} n={len(x)}")
        return
    print(f"{label:44s} n={len(x):5d}  mean {x.mean()*1e4:7.2f}bp  "
          f"med {np.median(x)*1e4:7.2f}bp  ann {(np.exp(np.log1p(x).mean()*252)-1)*100:7.2f}%  "
          f"t {x.mean()/x.std(ddof=1)*np.sqrt(len(x)):5.2f}")


def main():
    ts, o, h, lo, c, v = lab.load_panel()
    d = lab.Days(ts, o, c)
    on = d.overnight_ret(1)
    f30 = d.first_m_ret(30, 1)
    f60 = d.first_m_ret(60, 1)
    sess = d.session_ret(1)
    qon = d.overnight_ret(0)
    qsess = d.session_ret(0)
    vol20 = d.vol(20, 0)
    gate = d.gate()
    m = (d.ddates >= np.datetime64("2016-01-05")) & (d.ddates <= np.datetime64("2026-10-23"))

    def show(mask, ret, label):
        qstats(ret[mask & m & np.isfinite(ret)], label)

    print("=== unconditional blocks, TQQQ (2016-2026) ===")
    qstats(on[m], "overnight 15:59->09:30")
    qstats(f30[m], "first 30m 09:30->10:00")
    qstats(f60[m], "first 60m 09:30->10:30")
    qstats(sess[m], "session 09:30->15:59")
    qstats(qon[m], "QQQ overnight")
    qstats(qsess[m], "QQQ session")

    print("\n=== overnight TQQQ by QQQ 20d realised vol quintile (annualised) ===")
    ok = np.isfinite(vol20) & np.isfinite(on) & m
    q = pd.qcut(vol20[ok], 5, labels=False)
    idx = np.flatnonzero(ok)
    for i in range(5):
        sel = idx[q == i]
        qstats(on[sel], f"q{i+1} vol {vol20[sel].min()*100:4.1f}-{vol20[sel].max()*100:5.1f}%")

    print("\n=== overnight TQQQ by absolute annualised vol buckets ===")
    for lo_, hi_ in [(0, .12), (.12, .16), (.16, .20), (.20, .25), (.25, .30),
                     (.30, .40), (.40, .60), (.60, 9)]:
        show((vol20 >= lo_) & (vol20 < hi_), on, f"vol {lo_*100:.0f}-{hi_*100:.0f}%")

    print("\n=== overnight TQQQ by prior QQQ session return ===")
    pqs = np.r_[np.nan, qsess[:-1]]
    for lo_, hi_ in [(-1, -.03), (-.03, -.02), (-.02, -.01), (-.01, 0),
                     (0, .01), (.01, .02), (.02, .03), (.03, 1)]:
        show((pqs >= lo_) & (pqs < hi_), on, f"prior session {lo_*100:+.0f}..{hi_*100:+.0f}%")

    print("\n=== overnight TQQQ by regime (lag 1) ===")
    show(gate, on, "regime ON")
    show(~gate, on, "regime OFF")

    print("\n=== first 30m TQQQ by QQQ overnight gap ===")
    qgap = np.r_[np.nan, qon[:-1]]
    for lo_, hi_ in [(-1, -.03), (-.03, -.02), (-.02, -.01), (-.01, 0),
                     (0, .01), (.01, .02), (.02, 1)]:
        show((qgap >= lo_) & (qgap < hi_), f30, f"gap {lo_*100:+.0f}..{hi_*100:+.0f}%")

    print("\n=== first 30m TQQQ by gap, regime ON only ===")
    for lo_, hi_ in [(-1, -.02), (-.02, -.01), (-.01, 0), (0, .01), (.01, 1)]:
        show((qgap >= lo_) & (qgap < hi_) & gate, f30,
             f"gap {lo_*100:+.0f}..{hi_*100:+.0f}%")

    print("\n=== session TQQQ by first30 sign, regime ON ===")
    sgn = np.r_[np.nan, np.sign(f30[:-1])]
    show((sgn > 0) & gate, sess, "after up first30")
    show((sgn < 0) & gate, sess, "after down first30")

    print("\n=== overnight by vol percentile (504d rolling, causal) ===")
    vp = pd.Series(vol20).rolling(504, min_periods=252).rank(pct=True).to_numpy()
    for lo_, hi_ in [(0, .5), (.5, .8), (.8, .9), (.9, .95), (.95, 1.0)]:
        show((vp >= lo_) & (vp < hi_), on, f"pct {lo_:.2f}-{hi_:.2f}")

    print("\n=== yearly TQQQ block returns (compounded, gross) ===")
    yr = np.array([x.year for x in d.ddates])
    rows = []
    for y in sorted(set(yr)):
        sel = (yr == y) & m
        if sel.sum() < 20:
            continue
        rows.append({
            "year": y,
            "overnight": (np.exp(np.log1p(on[sel]).sum()) - 1) * 100,
            "first30": (np.exp(np.log1p(f30[sel]).sum()) - 1) * 100,
            "session": (np.exp(np.log1p(sess[sel]).sum()) - 1) * 100,
            "on_days": int(gate[sel].sum()),
        })
    print(pd.DataFrame(rows).to_string(index=False, float_format=lambda x: f"{x:7.2f}"))


if __name__ == "__main__":
    main()
