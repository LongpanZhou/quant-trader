"""ORB exploration harness (scratch; final rules live in strategy.py)."""
from __future__ import annotations

import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
import bt  # noqa: E402

START10 = "2017-01-03"
START5 = "2021-10-25"
END = "2026-10-23"


def load_all():
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START10, END, "1min")
    lo, hi = pd.Timestamp(ts[0]), pd.Timestamp(ts[-1])

    def prep(sym):
        df = bt.load_1m(sym)
        df = df[(df["ts"] >= lo) & (df["ts"] <= hi)].set_index("ts")
        return df.reindex(ts).ffill()

    q = prep("QQQ")
    t = prep("TQQQ")
    b = prep("BIL")
    return ts, opens, closes, q, t, b


def daily_qqq(ts, q, t):
    dates = ts.date
    g = pd.DataFrame(
        {
            "date": dates,
            "q_o": q["open"].to_numpy(),
            "q_h": q["high"].to_numpy(),
            "q_l": q["low"].to_numpy(),
            "q_c": q["close"].to_numpy(),
            "t_o": t["open"].to_numpy(),
            "t_h": t["high"].to_numpy(),
            "t_l": t["low"].to_numpy(),
            "t_c": t["close"].to_numpy(),
        }
    ).groupby("date", sort=True)
    d = g.agg(
        q_o=("q_o", "first"), q_h=("q_h", "max"), q_l=("q_l", "min"), q_c=("q_c", "last"),
        t_o=("t_o", "first"), t_h=("t_h", "max"), t_l=("t_l", "min"), t_c=("t_c", "last"),
    )
    for pre in ("q", "t"):
        pc = d[f"{pre}_c"].shift(1)
        tr = pd.concat(
            [d[f"{pre}_h"] - d[f"{pre}_l"],
             (d[f"{pre}_h"] - pc).abs(),
             (d[f"{pre}_l"] - pc).abs()], axis=1).max(axis=1)
        d[f"{pre}_atr14"] = tr.rolling(14).mean()
        d[f"{pre}_atrpct"] = d[f"{pre}_atr14"] / d[f"{pre}_c"]
    d["sma165"] = d["q_c"].rolling(165).mean()
    d["regime"] = (d["q_c"] > d["sma165"]).astype(float)
    d["regime_prev"] = d["regime"].shift(1).fillna(0.0)
    d["q_atrpct_prev"] = d["q_atrpct"].shift(1)
    d["t_atrpct_prev"] = d["t_atrpct"].shift(1)
    d["q_ret_prev"] = d["q_c"].pct_change().shift(1)
    return d


def build_or(dates_unique, day_starts, day_ends, q, or_min):
    """OR high/low per day over first `or_min` minutes (bars 09:30..09:30+or_min-1)."""
    or_hi = np.full(len(dates_unique), np.nan)
    or_lo = np.full(len(dates_unique), np.nan)
    or_open = np.full(len(dates_unique), np.nan)
    lo_arr = q["low"].to_numpy()
    hi_arr = q["high"].to_numpy()
    op_arr = q["open"].to_numpy()
    for k, (s, e) in enumerate(zip(day_starts, day_ends)):
        j = min(s + or_min, e)
        if j > s:
            or_hi[k] = hi_arr[s:j].max()
            or_lo[k] = lo_arr[s:j].min()
            or_open[k] = op_arr[s]
    return or_hi, or_lo, or_open


def time_index(ts, hh, mm):
    return (ts.hour == hh) & (ts.minute == mm)


def orb_weights(
    ts, q, t, d, *,
    or_min=30,
    entry_mode="breakout",   # 'breakout' = close > OR high; 'first' = OR close > OR open at end of window
    buffer_bps=0.0,
    stop_mode="orlow",       # 'orlow', 'atr', 'fixed'
    stop_k=1.0,
    fixed_stop_pct=0.01,
    target_r=None,           # multiple of initial risk
    target_pct=None,         # fixed percent
    entry_cutoff=(15, 0),
    eod=(15, 54),
    regime=True,
    signal_sym="TQQQ",       # which symbol's OR/stop (trade that symbol)
    one_trade_per_day=True,
):
    n = len(ts)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0  # BIL default

    dates = ts.date
    # day boundaries
    change = np.r_[True, dates[1:] != dates[:-1]]
    day_starts = np.flatnonzero(change)
    day_ends = np.r_[day_starts[1:], n]
    uniq = dates[day_starts]

    sig = t if signal_sym == "TQQQ" else q
    sig_hi = sig["high"].to_numpy()
    sig_lo = sig["low"].to_numpy()
    sig_op = sig["open"].to_numpy()
    sig_cl = sig["close"].to_numpy()

    or_hi, or_lo, or_open = build_or(uniq, day_starts, day_ends, sig, or_min)
    reg = d["regime_prev"].reindex(uniq).to_numpy()
    atrp = (d["t_atrpct_prev"] if signal_sym == "TQQQ" else d["q_atrpct_prev"]).reindex(uniq).to_numpy()

    eod_mask = time_index(ts, *eod)
    cutoff_mask = (ts.hour * 60 + ts.minute) >= (entry_cutoff[0] * 60 + entry_cutoff[1])
    buf = buffer_bps / 1e4

    day_of_bar = np.repeat(np.arange(len(uniq)), day_ends - day_starts)

    for k in range(len(uniq)):
        s, e = day_starts[k], day_ends[k]
        ok = (reg[k] > 0.5) if regime else True
        if not ok or not np.isfinite(or_hi[k]):
            continue
        i0 = s + or_min
        if i0 >= e:
            continue

        state = 0  # 0 flat, 1 long
        entry_ref = np.nan
        stop = np.nan
        target = np.nan
        risk = np.nan
        traded_today = False

        for i in range(i0, e):
            if state == 0:
                if cutoff_mask[i] or (one_trade_per_day and traded_today):
                    continue
                if entry_mode == "breakout":
                    trig = sig_cl[i] > or_hi[k] * (1.0 + buf)
                else:  # 'first': enter at first bar after the OR window if OR closed up
                    trig = (i == i0) and (sig_cl[i - 1] >= or_open[k] * (1.0 + buf))
                if not trig:
                    continue
                state = 1
                traded_today = True
                entry_ref = sig_cl[i]
                if stop_mode == "orlow":
                    stop = or_lo[k]
                elif stop_mode == "atr":
                    stop = entry_ref - stop_k * atrp[k] * entry_ref
                else:
                    stop = entry_ref * (1.0 - fixed_stop_pct)
                risk = entry_ref - stop
                if not np.isfinite(risk) or risk <= 0:
                    state = 0
                    continue
                if target_r is not None:
                    target = entry_ref + target_r * risk
                elif target_pct is not None:
                    target = entry_ref * (1.0 + target_pct)
                else:
                    target = np.inf
                w[i, 0] = 0.0
                w[i, 1] = 1.0
                w[i, 2] = 0.0
                continue

            # in position at bar i (filled at this bar's open if entry signal was i-1)
            # stop / target checked on this bar's range; exit next open
            hit_stop = sig_lo[i] <= stop
            hit_tgt = sig_hi[i] >= target
            if hit_stop or hit_tgt or eod_mask[i]:
                state = 0
                w[i, 0] = 0.0
                w[i, 1] = 0.0
                w[i, 2] = 1.0
            else:
                w[i, 0] = 0.0
                w[i, 1] = 1.0
                w[i, 2] = 0.0

    return w


def evaluate(ts, opens, closes, w, label="", slip=1.0):
    out = {}
    for tag, start in (("10y", START10), ("5y", START5)):
        res = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(res, 252 * 390)
        i = bt.start_index(ts, start)
        b = bt.benchmark(closes[i:, 1], ts[i:], 252 * 390)
        # daily-resampled equity for comparable Sharpe/DD
        eqs = pd.Series(res["equity"], index=res["ts"])
        daily = eqs.groupby(eqs.index.date).last()
        dr = daily.pct_change().dropna()
        sh = float(dr.mean() / dr.std(ddof=0) * np.sqrt(252)) if dr.std() > 0 else 0.0
        peak = np.maximum.accumulate(daily.to_numpy())
        dd = float(-(daily.to_numpy() / peak - 1).min())
        out[tag] = dict(s, sharpe_daily=sh, dd_daily=dd)
        if tag == "10y":
            yr = bt.yearly(res["ts"], res["equity"], np.interp(
                np.arange(len(res["ts"])), np.arange(len(res["ts"])), closes[i:, 1]))
        else:
            yr5 = bt.yearly(res["ts"], res["equity"], np.interp(
                np.arange(len(res["ts"])), np.arange(len(res["ts"])), closes[i:, 1]))
    return out, yr, yr5


def fmt(tag, s):
    return (f"{tag}: CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:6.2f}% "
            f"(daily {s['dd_daily']*100:5.2f}%)  Sh {s['sharpe']:5.2f} (daily {s['sharpe_daily']:4.2f})  "
            f"fills {s['fills']:6d}  turn {s['turnover']:7.1f}x  exp {s['exposure']*100:4.1f}%")


if __name__ == "__main__":
    ts, opens, closes, q, t, b = load_all()
    d = daily_qqq(ts, q, t)
    print("days", len(d), "first", d.index[0], "last", d.index[-1])
    print("regime on fraction 2017+:", d.loc[d.index >= pd.Timestamp("2017-01-03").date(), "regime_prev"].mean())

    cfgs = [
        dict(or_min=30, entry_mode="breakout", stop_mode="orlow", target_r=None),
        dict(or_min=15, entry_mode="breakout", stop_mode="orlow", target_r=None),
        dict(or_min=5, entry_mode="breakout", stop_mode="orlow", target_r=None),
        dict(or_min=30, entry_mode="breakout", stop_mode="atr", stop_k=1.0, target_r=2.0),
        dict(or_min=5, entry_mode="first", stop_mode="orlow", target_r=10.0),
    ]
    for cfg in cfgs:
        w = orb_weights(ts, q, t, d, **cfg)
        out, yr, yr5 = evaluate(ts, opens, closes, w)
        print("\n", cfg)
        for tag in ("10y", "5y"):
            print("  " + fmt(tag, out[tag]))
