"""Exploratory feature/label diagnostics for the ML classifier agent."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402


def build_features(ts: pd.DatetimeIndex, o: np.ndarray, c: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Causal 5-minute features. Row i uses data through the close of bar i."""
    qqq, tqqq, bil = c[:, 0], c[:, 1], c[:, 2]
    n = len(ts)
    dates = pd.Index(ts.date)
    day_code, _ = pd.factorize(dates)
    # bar index within day
    tmp = pd.DataFrame({"day": day_code})
    bar_in_day = tmp.groupby("day").cumcount().to_numpy()
    day_size = tmp.groupby("day")["day"].transform("size").to_numpy()

    lr_q = np.zeros(n)
    lr_q[1:] = np.log(qqq[1:] / qqq[:-1])
    lr_t = np.zeros(n)
    lr_t[1:] = np.log(tqqq[1:] / tqqq[:-1])

    def ret(series: np.ndarray, k: int) -> np.ndarray:
        out = np.zeros(n)
        out[k:] = np.log(series[k:] / series[:-k])
        return out

    def rolling_std(x: np.ndarray, w: int) -> np.ndarray:
        s = pd.Series(x)
        return s.rolling(w, min_periods=max(3, w // 2)).std(ddof=0).to_numpy()

    # daily aggregates (completed days only, then map to next day)
    daily = pd.DataFrame({"date": dates, "ts": ts, "qqq": qqq, "tqqq": tqqq, "bil": bil})
    day_last = daily.groupby("date", sort=True).tail(1).set_index("date")
    dclose = day_last["qqq"]
    dsma165 = dclose.rolling(165, min_periods=100).mean()
    dclose_prev = dclose.shift(1)
    dsma165_prev = dsma165.shift(1)
    dret = np.log(dclose / dclose.shift(1))
    drv20 = dret.rolling(20, min_periods=10).std(ddof=0)
    dmax20 = dclose.rolling(20, min_periods=10).max()
    dmom5 = np.log(dclose / dclose.shift(5))
    dmom20 = np.log(dclose / dclose.shift(20))
    daily_feat = pd.DataFrame({
        "trend165": np.log(dclose_prev / dsma165_prev),
        "drv20": drv20,
        "dd20": dclose_prev / dmax20.shift(1) - 1.0,
        "dmom5": dmom5.shift(1),
        "dmom20": dmom20.shift(1),
    })
    # map each intraday bar to the most recent COMPLETED prior day
    prev_dates = pd.Series(day_last.index)
    mapping = pd.Series(np.arange(len(prev_dates)), index=prev_dates)
    # for each bar's date, the prior completed day's position in daily_feat is
    # (position of bar's own date) - 1; intraday bars use previous day's close.
    date_pos = mapping.reindex(pd.Index(dates)).to_numpy()
    prev_pos = date_pos - 1
    daily_vals = daily_feat.to_numpy()
    safe_prev = np.clip(prev_pos, 0, len(daily_vals) - 1)

    # session vwap
    qv = np.zeros(n)
    # volume is not returned by panel; use equal weights (typical price) VWAP proxy
    typical = (o[:, 0] + c[:, 0]) / 2.0
    dfv = pd.DataFrame({"day": day_code, "pv": typical})
    cum_pv = dfv.groupby("day")["pv"].cumsum().to_numpy()
    cum_n = (bar_in_day + 1).astype(float)
    vwap = cum_pv / cum_n
    vwap_dist = qqq / vwap - 1.0

    ema20 = pd.Series(qqq).ewm(span=20, adjust=False).mean().to_numpy()
    ema60 = pd.Series(qqq).ewm(span=60, adjust=False).mean().to_numpy()

    # RSI(14) on 5-minute closes (Wilder)
    delta = np.zeros(n)
    delta[1:] = np.diff(qqq)
    up = pd.Series(np.maximum(delta, 0.0)).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    dn = pd.Series(np.maximum(-delta, 0.0)).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    rs = up / np.maximum(dn, 1e-12)
    rsi = 100.0 - 100.0 / (1.0 + rs)

    # day open, prior day close, gap
    first_open = pd.DataFrame({"day": day_code, "o": o[:, 0]}).groupby("day")["o"].transform("first").to_numpy()
    prior_close = np.zeros(n)
    # previous day's last close per bar
    day_last_close = pd.Series(dclose.to_numpy()).reindex(pd.Index(dates)).to_numpy()
    # shift within day: prior completed day close
    dlc = np.full(n, np.nan)
    for d in range(1, day_code.max() + 1):
        mask = day_code == d
        dlc[mask] = dclose.iloc[d - 1] if d - 1 < len(dclose) else np.nan
    dlc = pd.Series(dlc).ffill().bfill().to_numpy()

    tod = bar_in_day / np.maximum(day_size - 1, 1)
    dow = pd.Index(ts.dayofweek).to_numpy().astype(float)

    feats = np.column_stack([
        lr_q,
        ret(qqq, 3), ret(qqq, 6), ret(qqq, 12), ret(qqq, 24),
        lr_t,
        ret(tqqq, 6), ret(tqqq, 12),
        np.log(qqq / dlc),
        np.log(first_open / dlc),
        rolling_std(lr_q, 6), rolling_std(lr_q, 12), rolling_std(lr_q, 78),
        rolling_std(lr_q, 6) / np.maximum(rolling_std(lr_q, 78), 1e-9),
        rsi / 100.0 - 0.5,
        vwap_dist,
        qqq / ema20 - 1.0,
        qqq / ema60 - 1.0,
        daily_vals[safe_prev, 0],
        daily_vals[safe_prev, 1],
        daily_vals[safe_prev, 2],
        daily_vals[safe_prev, 3],
        daily_vals[safe_prev, 4],
        np.sin(2 * np.pi * tod), np.cos(2 * np.pi * tod),
        np.sin(2 * np.pi * dow / 5.0), np.cos(2 * np.pi * dow / 5.0),
    ])
    names = [
        "q_r5", "q_r15", "q_r30", "q_r60", "q_r120",
        "t_r5", "t_r30", "t_r60",
        "q_dayret", "gap",
        "rv30", "rv60", "rvday", "rv_ratio",
        "rsi14", "vwap_dist", "ema20_dist", "ema60_dist",
        "trend165", "drv20", "dd20", "dmom5", "dmom20",
        "tod_sin", "tod_cos", "dow_sin", "dow_cos",
    ]
    return feats, names


def standardize_fit(x: np.ndarray):
    mu = np.nanmean(x, axis=0)
    sd = np.nanstd(x, axis=0)
    mu = np.where(np.isfinite(mu), mu, 0.0)
    sd = np.where(np.isfinite(sd) & (sd > 1e-12), sd, 1.0)
    return mu, sd


def logistic_fit(x: np.ndarray, y: np.ndarray, lam: float = 10.0, iters: int = 25):
    n, d = x.shape
    xb = np.column_stack([np.ones(n), x])
    w = np.zeros(d + 1)
    reg = np.full(d + 1, lam)
    reg[0] = 0.0
    for _ in range(iters):
        z = xb @ w
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))
        g = xb.T @ (p - y) + reg * w
        s = np.maximum(p * (1 - p), 1e-6)
        h = xb.T @ (xb * s[:, None]) + np.diag(reg + 1e-9)
        step = np.linalg.solve(h, g)
        w -= step
        if np.max(np.abs(step)) < 1e-6:
            break
    return w


def logistic_predict(w: np.ndarray, x: np.ndarray) -> np.ndarray:
    xb = np.column_stack([np.ones(len(x)), x])
    return 1.0 / (1.0 + np.exp(-np.clip(xb @ w, -35, 35)))


def main() -> None:
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), "2017-01-03", "2026-10-23", "5min")
    x, names = build_features(ts, o, c)
    n = len(ts)
    # label: TQQQ beats BIL over next 6 bars (30 min), 12 bars (60 min)
    for horizon in (6, 12):
        y = np.full(n, np.nan)
        fwd_t = np.zeros(n)
        fwd_t[:-horizon] = np.log(c[horizon:, 1] / c[:-horizon, 1])
        fwd_b = np.zeros(n)
        fwd_b[:-horizon] = np.log(c[horizon:, 2] / c[:-horizon, 2])
        y[:-horizon] = (fwd_t[:-horizon] > fwd_b[:-horizon]).astype(float)
        ok = np.isfinite(y) & np.isfinite(x).all(axis=1)
        years = np.array([t.year for t in ts])
        print(f"\n=== horizon {horizon} bars, base rate {np.nanmean(y):.4f}, usable {ok.sum()} ===")
        train = ok & (years <= 2019)
        mu, sd = standardize_fit(x[train])
        xs = (x - mu) / sd
        w = logistic_fit(xs[train], y[train], lam=10.0)
        for yr in range(2020, 2027):
            te = ok & (years == yr)
            if te.sum() < 100:
                continue
            p = logistic_predict(w, xs[te])
            acc = ((p > 0.5) == (y[te] > 0.5)).mean()
            # correlation with future excess return
            fwd_ex = fwd_t - fwd_b
            ic = np.corrcoef(p, fwd_ex[te])[0, 1]
            print(f"  {yr}: n={te.sum():6d} acc={acc:.4f} ic={ic:+.4f} meanp={p.mean():.3f}")
        # in-sample top coefficients
        order = np.argsort(-np.abs(w[1:]))[:10]
        print("  top coefs:", ", ".join(f"{names[j]}={w[1+j]:+.3f}" for j in order))


if __name__ == "__main__":
    main()
