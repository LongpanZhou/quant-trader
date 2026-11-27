"""Independent verification of the headline variants.

1. Re-simulate the weight array with a hand-written next-open simulator
   (no band) and compare to bt.simulate.
2. Rebuild equity purely from block returns (no weights at all) and compare.
3. Audit the 1m data for jumps that could fake an overnight edge.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402

import bt  # noqa: E402


def naive_sim(op, cl, w, start_idx):
    """Long-only, next-open fills, no band, no costs. Returns equity from start."""
    n = w.shape[0]
    cash = 1.0
    sh = np.zeros(3)
    eq = np.empty(n - start_idx)
    for i in range(start_idx, n - 1):
        px = op[i + 1]
        book = cash + sh @ px
        tgt = w[i]
        # sell everything not wanted
        for s in range(3):
            if sh[s] > 0:
                want = tgt[s] * book
                cur = sh[s] * px[s]
                if want < cur:
                    q = (cur - want) / px[s]
                    cash += q * px[s]
                    sh[s] -= q
        for s in range(3):
            if tgt[s] > 0:
                book = cash + sh @ px
                want = tgt[s] * book
                cur = sh[s] * px[s]
                if want > cur:
                    q = (want - cur) / px[s]
                    if q * px[s] > cash:
                        q = cash / px[s]
                    cash -= q * px[s]
                    sh[s] += q
        eq[i + 1 - start_idx] = cash + sh @ cl[i + 1]
    eq[0] = 1.0
    return eq


def block_equity(op, cl, reg, dates, df, tom=None, exit_min=601):
    """Rebuild equity from first principles: only two return atoms."""
    minute = df["minute"].to_numpy()
    idx = df.groupby("date", sort=False).indices
    dts = list(idx.keys())
    on = reg.reindex(pd.DatetimeIndex(dts)).to_numpy()
    p1001 = np.full(len(dts), np.nan)
    last_open = np.full(len(dts), np.nan)
    for k, d in enumerate(dts):
        seg = idx[d]
        j = int(np.searchsorted(minute[seg], exit_min))
        if j < len(seg):
            p1001[k] = op[seg[j], 1]
        last_open[k] = op[seg[-1], 1]
    fac = np.ones(len(dts))
    for k in range(len(dts) - 1):
        if not on[k] or not np.isfinite(p1001[k + 1]):
            continue
        fac[k] = p1001[k + 1] / last_open[k]          # overnight + first 30m
        if tom is not None and on[k] and bool(tom.get(dts[k + 1], False)):
            # no exit at 10:01 of k+1 -> also hold k+1's session
            if np.isfinite(p1001[k + 1]):
                fac[k] *= last_open[k + 1] / p1001[k + 1]
    return pd.Series(fac, index=pd.DatetimeIndex(dts))


def main():
    ts, op, cl = S.load_panel()
    df = pd.DataFrame({"date": ts.date, "minute": ts.hour * 60 + ts.minute})
    dcl = S.daily_close(ts, cl[:, 0])
    dates = pd.DatetimeIndex(sorted(set(ts.date)))

    regb = S.regime_band(dcl, 165, 1, 0.02)
    tom31 = S.tom_flags(dates, 3, 1)

    # ---------------- 1. weights vs naive simulator ----------------------- #
    wP = S.build_weights(df, regb, 601, "cash")
    wT = S.build_weights_tom(df, regb, 601, tom31)
    i0 = bt.start_index(ts, "2017-01-03")
    for name, w in (("P overnight+band2", wP), ("T +TOM(3+1)", wT)):
        eqn = naive_sim(op, cl, w, i0)
        res, s, b = S.evaluate(w, ts, op, cl, "2017-01-03", 0.0)
        print(f"[{name}] naive sim CAGR {((eqn[-1])**(365.25/((ts[-1]-ts[i0]).days))-1)*100:6.2f}%"
              f"   harness 0bp CAGR {s['cagr']*100:6.2f}%"
              f"   ratio end {eqn[-1]/ (res['equity'][-1]/res['equity'][0]):.4f}")

    # ---------------- 2. block-return equity ------------------------------ #
    print("\nBlock-return reconstruction (gross, no cost) vs harness 0bp")
    for name, w, tom in (("P", wP, None), ("T", wT, tom31)):
        f = block_equity(op, cl, regb, dates, df, tom)
        cum = f.cumprod()
        for tag, lo, hi in S.WINDOWS:
            a = dates.searchsorted(pd.Timestamp(lo))
            bb = dates.searchsorted(pd.Timestamp(hi))
            g = cum.iloc[bb - 1] / cum.iloc[a - 1]
            yrs = (dates[bb - 1] - dates[a - 1]).days / 365.25
            res, s, _ = S.evaluate(w, ts, op, cl, lo, 0.0)
            print(f"  [{name} {tag}] block {(g**(1/yrs)-1)*100:6.2f}%  "
                  f"harness {s['cagr']*100:6.2f}%  (diff {((g**(1/yrs))-(1+s['cagr']))*100:+.2f}pp)")

    # ---------------- 3. data audit --------------------------------------- #
    print("\nData audit")
    tq = cl[:, 1]
    print(f"  TQQQ adj price {tq[0]:.4f} -> {tq[-1]:.4f}  "
          f"({(tq[-1]/tq[0])**(365.25/((ts[-1]-ts[0]).days))-1:.2%} CAGR over full panel)")
    dd = pd.DataFrame({"open": pd.Series(op[:, 1], index=ts).groupby(ts.date).first(),
                       "close": pd.Series(cl[:, 1], index=ts).groupby(ts.date).last()})
    gap = dd["open"] / dd["close"].shift(1) - 1
    intr = dd["close"] / dd["open"] - 1
    print("  5 biggest overnight gaps:")
    print("   ", {str(k): round(float(v), 4) for k, v in gap.nlargest(5).items()})
    print("  5 smallest overnight gaps:")
    print("   ", {str(k): round(float(v), 4) for k, v in gap.nsmallest(5).items()})
    print("  3 biggest intraday moves:")
    print("   ", {str(k): round(float(v), 4) for k, v in intr.nlargest(3).items()})
    print("  3 smallest intraday moves:")
    print("   ", {str(k): round(float(v), 4) for k, v in intr.nsmallest(3).items()})
    # cross-check QQQ returns against the daily parquet
    daily = pd.read_parquet(bt.DATA_DIR / "QQQ-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    daily = daily.set_index("date")
    q1m = pd.Series(cl[:, 0], index=ts).groupby(ts.date).last()
    common = [d for d in q1m.index if d in daily.index]
    a = q1m.reindex(common)
    b = daily["adjclose"].reindex(common)
    ra = a.pct_change().dropna()
    rb = b.pct_change().dropna()
    idx = ra.index.intersection(rb.index)
    err = (ra.reindex(idx) - rb.reindex(idx)).abs()
    print(f"  QQQ 1m-derived daily returns vs Yahoo adjclose: n={len(idx)} "
          f"max abs diff {err.max()*1e4:.2f}bp  mean {err.mean()*1e4:.3f}bp  "
          f">5bp days: {(err > 5e-4).sum()}")


if __name__ == "__main__":
    main()
