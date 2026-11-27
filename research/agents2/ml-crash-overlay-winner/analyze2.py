"""Second exploration: winner state + conditional value of a crash forecast."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from explore import daily_from_1m  # noqa: E402

START, END = "2017-01-03", "2026-10-23"
SMA_N, MA_FAST, STOP, ARM_BUF = 165, 20, 0.04, 0.01


def winner_daily(ts, o, c):
    """Winner logic per minute; return day-level open position, stop flag, weights."""
    dates = np.array([t.date() for t in ts])
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(dates) - 1]
    n = len(ts)
    qc = c[:, 0]
    tc = c[:, 1]
    dclose = qc[last]
    sma = pd.Series(dclose).rolling(SMA_N).mean().to_numpy()
    ma20 = pd.Series(dclose).rolling(MA_FAST).mean().to_numpy()
    sma_prev = np.r_[np.nan, sma[:-1]]
    ma20_prev = np.r_[np.nan, ma20[:-1]]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
    hold = np.zeros(n, bool)
    opened = np.zeros(len(first), bool)
    stopped = np.zeros(len(first), bool)
    for k, (f, l) in enumerate(zip(first, last)):
        risk_on = k > 0 and sma_prev[k] == sma_prev[k] and dclose[k - 1] > sma_prev[k]
        if not risk_on:
            continue
        opened[k] = True
        armed = ma20_prev[k] == ma20_prev[k] and qc[f] < ma20_prev[k] * (1.0 + ARM_BUF)
        base = o[f, 1]
        state = True
        for i in range(f, l + 1):
            if armed and state and tc[i] < base * (1.0 - STOP):
                state = False
                stopped[k] = True
            hold[i] = state
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w, opened, stopped, last, first


def main():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min")
    w, opened, stopped, last, first = winner_daily(ts, o, c)
    dates = np.array([t.date() for t in ts])
    f = pd.read_pickle(Path(__file__).parent / "features.pkl")
    f.index = pd.to_datetime(f.index)
    dts = pd.DatetimeIndex([pd.Timestamp(x) for x in dates[last]])
    # winner daily equity
    r = bt.run(ts, o, c, w, START, band=0.02, slippage_bps=1.0)
    s = bt.stats(r, 252 * 390)
    print(f"winner: CAGR {s['cagr']*100:.2f}% DD {s['max_drawdown']*100:.2f}% Sharpe {s['sharpe']:.3f}")

    eq = pd.Series(r["equity"], index=ts)
    deq = eq.groupby(eq.index.date).last()
    deq.index = pd.DatetimeIndex(deq.index)
    dr = deq.pct_change()
    print("daily winner ret mean/std", dr.mean(), dr.std())

    d = pd.DataFrame({
        "held": opened,
        "stopped": stopped,
    }, index=dts)
    d["t_ret"] = pd.Series(c[last, 1], index=dts).pct_change()
    d["q_ret"] = pd.Series(c[last, 0], index=dts).pct_change()
    d["strat_ret"] = dr.reindex(dts).to_numpy()
    d = d.join(f, how="left")

    m = d.index >= pd.Timestamp("2017-01-03")
    q = d[m & d.held]
    print(f"\nwinner held days: {len(q)}  mean {q.strat_ret.mean()*100:.3f}%/d  std {q.strat_ret.std()*100:.2f}%")

    print("\nnext-day TQQQ return by rv_pct decile (winner-held days):")
    for col in ["rv_pct", "dvol20", "rv_ratio", "range20", "vwap_dist", "dd_high", "gap", "rsi14", "decay20", "sma20"]:
        x = q[col].to_numpy()
        y = q["t_ret"].to_numpy()
        ok = np.isfinite(x) & np.isfinite(y)
        qs = np.quantile(x[ok], np.linspace(0, 1, 11))
        qs[0] -= 1e-12
        idx = np.clip(np.searchsorted(qs, x[ok], side="right") - 1, 0, 9)
        means = [np.mean(y[ok][idx == k]) * 100 for k in range(10)]
        crash = [(y[ok][idx == k] < -0.03).mean() * 100 for k in range(10)]
        print(f"  {col:12s} mean " + " ".join(f"{v:5.2f}" for v in means))
        print(f"  {'':12s} p<-3 " + " ".join(f"{v:5.1f}" for v in crash))

    # oracle: on winner-held days, swap TQQQ -> BIL when next-day t_ret below threshold.
    print("\nOracle upper bounds (winner-held days, full-day swap):")
    for thr in (-0.01, -0.02, -0.03, -0.04):
        mask = (q["t_ret"] < thr).to_numpy()
        # strategy still earns its normal return otherwise; replace that day's strat ret by BIL ret
        bil = np.r_[np.nan, np.diff(np.log(pd.Series(c[last, 2], index=dts).to_numpy()))]
        bret = pd.Series(np.expm1(bil), index=dts).reindex(q.index).to_numpy()
        alt = np.where(mask, bret, q["strat_ret"].to_numpy())
        sr = pd.Series(alt, index=q.index)
        eqq = (1 + sr.fillna(0)).cumprod()
        yrs = (q.index[-1] - q.index[0]).days / 365.25
        cagr = eqq.iloc[-1] ** (1 / yrs) - 1
        peak = np.maximum.accumulate(eqq)
        dd = -(eqq / peak - 1).min()
        sharpe = sr.mean() / sr.std() * np.sqrt(252)
        print(f"  thr {thr*100:5.1f}%: n={mask.sum():4d} CAGR {cagr*100:6.2f}% DD {dd*100:6.2f}% Sharpe {sharpe:5.2f}")

    print("\nOracle QQQ swap:")
    for thr in (-0.02, -0.03):
        mask = (q["t_ret"] < thr).to_numpy()
        qret = q["q_ret"].to_numpy()
        alt = np.where(mask, qret, q["strat_ret"].to_numpy())
        sr = pd.Series(alt, index=q.index)
        eqq = (1 + sr.fillna(0)).cumprod()
        yrs = (q.index[-1] - q.index[0]).days / 365.25
        cagr = eqq.iloc[-1] ** (1 / yrs) - 1
        peak = np.maximum.accumulate(eqq)
        dd = -(eqq / peak - 1).min()
        sharpe = sr.mean() / sr.std() * np.sqrt(252)
        print(f"  thr {thr*100:5.1f}%: n={mask.sum():4d} CAGR {cagr*100:6.2f}% DD {dd*100:6.2f}% Sharpe {sharpe:5.2f}")

    # simple vol rules on held days
    print("\nSimple rules: move TQQQ->BIL when feature in top decile")
    for col in ["rv_pct", "dvol20", "range20", "rv_ratio", "vwap_dist", "decay20"]:
        x = q[col].to_numpy()
        ok = np.isfinite(x)
        thr = np.nanquantile(x, 0.9)
        mask = ok & (x > thr)
        bil = np.r_[np.nan, np.diff(np.log(pd.Series(c[last, 2], index=dts).to_numpy()))]
        bret = pd.Series(np.expm1(bil), index=dts).reindex(q.index).to_numpy()
        alt = np.where(mask, bret, q["strat_ret"].to_numpy())
        sr = pd.Series(alt, index=q.index)
        eqq = (1 + sr.fillna(0)).cumprod()
        yrs = (q.index[-1] - q.index[0]).days / 365.25
        cagr = eqq.iloc[-1] ** (1 / yrs) - 1
        peak = np.maximum.accumulate(eqq)
        dd = -(eqq / peak - 1).min()
        sharpe = sr.mean() / sr.std() * np.sqrt(252)
        print(f"  {col:12s} n={mask.sum():4d} CAGR {cagr*100:6.2f}% DD {dd*100:6.2f}% Sharpe {sharpe:5.2f}")


if __name__ == "__main__":
    main()
