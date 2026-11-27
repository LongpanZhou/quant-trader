"""ORB exploration harness v2: continuous state machine, optional overnight hold."""
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

    return ts, opens, closes, prep("QQQ"), prep("TQQQ"), prep("BIL")


def daily_tables(ts, q, t):
    g = pd.DataFrame({
        "date": ts.date,
        "qo": q["open"].to_numpy(), "qh": q["high"].to_numpy(),
        "ql": q["low"].to_numpy(), "qc": q["close"].to_numpy(),
        "to": t["open"].to_numpy(), "th": t["high"].to_numpy(),
        "tl": t["low"].to_numpy(), "tc": t["close"].to_numpy(),
    })
    d = g.groupby("date").agg(
        qo=("qo", "first"), qh=("qh", "max"), ql=("ql", "min"), qc=("qc", "last"),
        to=("to", "first"), th=("th", "max"), tl=("tl", "min"), tc=("tc", "last"))
    for pre in ("q", "t"):
        pc = d[f"{pre}c"].shift(1)
        tr = pd.concat([d[f"{pre}h"] - d[f"{pre}l"],
                        (d[f"{pre}h"] - pc).abs(),
                        (d[f"{pre}l"] - pc).abs()], axis=1).max(axis=1)
        d[f"{pre}_atr14"] = tr.rolling(14).mean()
        d[f"{pre}_atrpct"] = d[f"{pre}_atr14"] / d[f"{pre}c"]
        d[f"{pre}_atrpct_prev"] = d[f"{pre}_atrpct"].shift(1)
    d["sma165"] = d["qc"].rolling(165).mean()
    d["regime"] = (d["qc"] > d["sma165"]).astype(float)
    d["regime_prev"] = d["regime"].shift(1).fillna(0.0)
    d["qc_ret"] = d["qc"].pct_change()
    return d


def day_arrays(ts, q):
    dates = ts.date
    starts = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    ends = np.r_[starts[1:], len(ts)]
    return dates, starts, ends


def orb_hl(ts, q, starts, ends, or_min):
    hi = q["high"].to_numpy()
    lo = q["low"].to_numpy()
    op = q["open"].to_numpy()
    cl = q["close"].to_numpy()
    n = len(starts)
    or_hi = np.full(n, np.nan)
    or_lo = np.full(n, np.nan)
    or_open = np.full(n, np.nan)
    or_close = np.full(n, np.nan)
    for k, (s, e) in enumerate(zip(starts, ends)):
        j = min(s + or_min, e)
        if j > s:
            or_hi[k] = hi[s:j].max()
            or_lo[k] = lo[s:j].min()
            or_open[k] = op[s]
            or_close[k] = cl[j - 1]
    return or_hi, or_lo, or_open, or_close


def make_weights(
    ts, q, t, d, *,
    or_min=30,
    buffer_bps=0.0,
    stop_mode="orlow",        # orlow | atr | fixed | none
    stop_k=1.0,
    fixed_stop_pct=0.01,
    target_mode="none",       # none | r | pct
    target_r=None,
    target_pct=None,
    intraday_only=True,       # exit at EOD
    overnight_rule="always",  # always | if_above_or | if_profit
    trail_mode="none",        # none | atr | orlow_prev
    trail_k=1.5,
    entry_cutoff=(15, 0),
    eod=(15, 54),
    use_regime=True,
    allow_same_day_reentry=False,
    max_hold_days=999,
):
    """Continuous ORB state machine. Long TQQQ on OR-high close breakout, else BIL."""
    n = len(ts)
    w = np.zeros((n, 3))
    w[:, 2] = 1.0

    dates, starts, ends = day_arrays(ts, q)
    uniq = dates[starts]
    or_hi, or_lo, or_open, or_close = orb_hl(ts, t, starts, ends, or_min)
    reg = d["regime_prev"].reindex(uniq).to_numpy()
    atrp = d["t_atrpct_prev"].reindex(uniq).to_numpy()

    day_of = np.repeat(np.arange(len(uniq)), ends - starts)
    eod_mask = (ts.hour == eod[0]) & (ts.minute == eod[1])
    cutoff = (ts.hour * 60 + ts.minute) >= (entry_cutoff[0] * 60 + entry_cutoff[1])
    buf = buffer_bps / 1e4

    pos = 0
    entry_i = -1
    entry_px = np.nan
    stop = np.nan
    target = np.inf
    hwm = np.nan
    days_held = 0
    traded_today = False
    prev_day = -1
    base_stop = np.nan

    for i in range(n):
        k = day_of[i]
        if k != prev_day:
            prev_day = k
            traded_today = False
            if pos == 1:
                days_held += 1
                if trail_mode == "orlow_daily" and np.isfinite(or_lo[k]):
                    stop = max(stop, or_lo[k]) if np.isfinite(stop) else or_lo[k]

        # ---------- in position during bar i ----------
        if pos == 1:
            hit_stop = np.isfinite(stop) and (t["low"].to_numpy()[i] <= stop)
            hit_tgt = np.isfinite(target) and (t["high"].to_numpy()[i] >= target)
            exit_now = hit_stop or hit_tgt

            if eod_mask[i]:
                if intraday_only:
                    exit_now = True
                elif overnight_rule == "if_above_or":
                    exit_now = exit_now or not (t["close"].to_numpy()[i] > or_hi[k])
                elif overnight_rule == "if_profit":
                    exit_now = exit_now or not (t["close"].to_numpy()[i] > entry_px)
                if days_held >= max_hold_days:
                    exit_now = True
                # regime turns off -> leave before the night
                if use_regime and reg[k] < 0.5:
                    exit_now = True

            if exit_now:
                w[i, 0] = 0.0
                w[i, 1] = 0.0
                w[i, 2] = 1.0
                pos = 0
                entry_i = -1
                entry_px = np.nan
                stop = np.nan
                days_held = 0
            else:
                w[i, 0] = 0.0
                w[i, 1] = 1.0
                w[i, 2] = 0.0
                # trailing stop update at this bar's close
                px = t["close"].to_numpy()[i]
                hwm = max(hwm, px)
                if trail_mode == "atr" and np.isfinite(atrp[k]):
                    tr = hwm * (1.0 - trail_k * atrp[k])
                    stop = max(stop, tr) if np.isfinite(stop) else tr
            continue

        # ---------- flat during bar i ----------
        can_enter = (not cutoff[i]) and (not (traded_today and not allow_same_day_reentry))
        if use_regime and reg[k] < 0.5:
            can_enter = False
        if can_enter and i >= starts[k] + or_min:
            px = t["close"].to_numpy()[i]
            trig = px > or_hi[k] * (1.0 + buf)
            if trig:
                w[i, 0] = 0.0
                w[i, 1] = 1.0
                w[i, 2] = 0.0
                pos = 1
                entry_i = i
                entry_px = px  # reference; real fill = next open
                traded_today = True
                days_held = 1
                if stop_mode == "orlow":
                    stop = or_lo[k]
                elif stop_mode == "atr":
                    stop = px - stop_k * atrp[k] * px
                elif stop_mode == "fixed":
                    stop = px * (1.0 - fixed_stop_pct)
                else:
                    stop = np.nan
                risk = px - stop if np.isfinite(stop) else np.nan
                if target_mode == "r" and np.isfinite(risk) and risk > 0:
                    target = px + target_r * risk
                elif target_mode == "pct":
                    target = px * (1.0 + target_pct)
                else:
                    target = np.inf
                hwm = px

    # post-pass: recompute entry px to the actual next-open fill for stop refs is
    # intentionally avoided; stops are anchored on the signal close (conservative
    # when the next open gaps up, the stop is farther away).
    return w


def evaluate(ts, opens, closes, w, slip=1.0):
    out = {}
    yearly = {}
    for tag, start in (("10y", START10), ("5y", START5)):
        res = bt.run(ts, opens, closes, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(res, 252 * 390)
        i = bt.start_index(ts, start)
        b = bt.benchmark(closes[i:, 1], ts[i:], 252 * 390)
        eqs = pd.Series(res["equity"], index=res["ts"])
        daily = eqs.groupby(eqs.index.date).last()
        dr = daily.pct_change().dropna()
        sh = float(dr.mean() / dr.std(ddof=0) * np.sqrt(252)) if dr.std() > 0 else 0.0
        peak = np.maximum.accumulate(daily.to_numpy())
        dd = float(-(daily.to_numpy() / peak - 1).min())
        out[tag] = dict(s, sharpe_daily=sh, dd_daily=dd, bench=b)
        yearly[tag] = bt.yearly(res["ts"], res["equity"],
                                closes[i:bt.start_index(ts, start) + len(res["ts"]), 1])
    return out, yearly


def fmt(tag, s):
    return (f"{tag}: CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:6.2f}% "
            f"(daily {s['dd_daily']*100:5.2f}%)  Sh {s['sharpe']:5.2f} (daily {s['sharpe_daily']:4.2f})  "
            f"fills {s['fills']:5d}  turn {s['turnover']:6.1f}x")


if __name__ == "__main__":
    ts, opens, closes, q, t, b = load_all()
    d = daily_tables(ts, q, t)

    cfgs = [
        ("A intraday OR30", dict(or_min=30, intraday_only=True, stop_mode="orlow")),
        ("B swing OR30", dict(or_min=30, intraday_only=False, stop_mode="orlow")),
        ("C swing OR30 trail2", dict(or_min=30, intraday_only=False, stop_mode="orlow",
                                     trail_mode="atr", trail_k=2.0)),
        ("D swing OR30 trail3", dict(or_min=30, intraday_only=False, stop_mode="orlow",
                                     trail_mode="atr", trail_k=3.0)),
        ("E swing OR30 trail4", dict(or_min=30, intraday_only=False, stop_mode="orlow",
                                     trail_mode="atr", trail_k=4.0)),
        ("F swing OR30 orlow_daily", dict(or_min=30, intraday_only=False, stop_mode="orlow",
                                          trail_mode="orlow_daily")),
        ("G swing OR15 trail3", dict(or_min=15, intraday_only=False, stop_mode="orlow",
                                     trail_mode="atr", trail_k=3.0)),
        ("H swing OR5 trail3", dict(or_min=5, intraday_only=False, stop_mode="orlow",
                                    trail_mode="atr", trail_k=3.0)),
    ]
    for name, cfg in cfgs:
        w = make_weights(ts, q, t, d, **cfg)
        out, yr = evaluate(ts, opens, closes, w)
        print(f"\n{name}  {cfg}")
        print("  " + fmt("10y", out["10y"]))
        print("  " + fmt("5y", out["5y"]))
