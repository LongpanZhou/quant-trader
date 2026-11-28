"""Participation exhaustion long -- standalone rebuild of `volume-orderflow`.

Idea (see hypothesis.md): a session that sells off *within the day* on
well-above-normal participation but closes in the upper half of its range has
absorbed the supply.  Buy TQQQ at the next open, hold 5 sessions, otherwise BIL.

This is NOT the round-1 strategy and does not contain it: there is no 165-day
QQQ regime, no 100-250-day moving average of any kind, no inherited stop and no
reused weight matrix.  The 165-day baseline appears only in `main()` as a
benchmark and correlation reference.

BACKTESTS ARE PAUSED (2026-11-26).  `main()` refuses to run without
`--authorized`; `build_weights()` is importable and side-effect free.

Run (only once the lead authorises):
    $env:PYTHONPATH = "C:\\Users\\27175\\AppData\\Local\\Temp\\opencode\\pylibs"
    python research/revisit/volume-orderflow/strategy.py --authorized
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

SYMS = ("QQQ", "TQQQ", "BIL")
DEV_START = "2016-01-04"
DEV_END = "2023-12-29"          # holdout 2024+ is never loaded here
BARS_1M = 252 * 390

# ---- primary parameters (fixed a priori; see spec.md section 4)
PARAMS = dict(
    rvol_hi=1.5,        # event: volume >= 1.5x the prior-20-session mean
    rvol_n=20,          # baseline window for rvol
    intraday_lo=-0.008, # event: QQQ open-to-close <= -0.8%
    clv_min=0.0,        # event: close in the upper half of the session range
    hold=5,             # sessions held after the signal
    size=1.0,           # fraction of equity in TQQQ while long
)


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_panel(start=DEV_START, end=DEV_END):
    """QQQ/TQQQ/BIL 1-minute panel plus high, low and volume.

    bt.panel returns opens and closes on the QQQ minute grid; the other four
    fields are aligned to the same grid here (ffill prices, zero-fill volume),
    which is the same convention `research/minute_marks.py` relies on.
    """
    ts, opens, closes = bt.panel(SYMS, start, end, "1min")
    n = len(ts)
    k = len(SYMS)
    highs = np.empty((n, k))
    lows = np.empty((n, k))
    vols = np.empty((n, k))
    for j, sym in enumerate(SYMS):
        df = bt.load_1m(sym)
        df = df[(df["ts"] >= ts[0]) & (df["ts"] < ts[-1] + pd.Timedelta(minutes=1))]
        f = df.set_index("ts").reindex(ts)
        highs[:, j] = f["high"].ffill().bfill().to_numpy()
        lows[:, j] = f["low"].ffill().bfill().to_numpy()
        vols[:, j] = f["volume"].fillna(0.0).to_numpy()
    return ts, opens, closes, highs, lows, vols


def sessions(ts):
    """Session boundaries indexed by bar (half days end at their last bar)."""
    dates = bt.session_dates(ts)
    first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
    last = np.r_[first[1:] - 1, len(ts) - 1]
    day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, len(ts)]))
    return dates, first, last, day_id


# --------------------------------------------------------------------------- #
# strategy
# --------------------------------------------------------------------------- #
def session_features(ts, opens, closes, highs, lows, vols, params=PARAMS):
    """Per-session QQQ aggregates and the event flag.  All inputs known at the
    session's last bar; `rvol` uses the prior `rvol_n` sessions only."""
    dates, first, last, _ = sessions(ts)
    nd = len(first)
    qo = opens[first, 0]
    qc = closes[last, 0]
    qh = np.array([highs[f:l + 1, 0].max() for f, l in zip(first, last)])
    ql = np.array([lows[f:l + 1, 0].min() for f, l in zip(first, last)])
    qv = np.array([vols[f:l + 1, 0].sum() for f, l in zip(first, last)])

    base = pd.Series(qv).rolling(params["rvol_n"], min_periods=params["rvol_n"]).mean()
    base = base.shift(1).to_numpy()                       # prior sessions only
    with np.errstate(invalid="ignore", divide="ignore"):
        rvol = np.where(base > 0, qv / base, np.nan)

    intraday = qc / qo - 1.0
    rng = qh - ql
    clv = np.where(rng > 0, ((qc - ql) - (qh - qc)) / np.where(rng > 0, rng, 1.0), 0.0)

    event = (np.isfinite(rvol) & (rvol >= params["rvol_hi"])
             & (intraday <= params["intraday_lo"])
             & (clv >= params["clv_min"]))
    feats = dict(q_open=qo, q_close=qc, q_high=qh, q_low=ql, q_vol=qv,
                 rvol=rvol, intraday=intraday, clv=clv, event=event)
    return dates, first, last, feats


def holding_flags(event, hold):
    """W[d] = 1 if session d is inside a holding window.

    A signal at session d opens at the open of d+1 and covers sessions
    d+1 .. d+hold.  A new signal while long extends the window.
    """
    nd = len(event)
    w = np.zeros(nd, dtype=float)
    long_until = -1
    for d in range(nd):
        if d <= long_until:
            w[d] = 1.0
        if event[d]:
            long_until = max(long_until, d + hold)
    return w


def build_weights(ts, opens, closes, highs, lows, volumes, params=None):
    """Return (weights, info).  weights[i] is set at bar i's close and fills at
    bar i+1's open, so the position *during* session s is written on the last
    bar of session s-1."""
    p = dict(PARAMS)
    if params:
        p.update(params)
    dates, first, last, day_id = sessions(ts)
    _, _, _, feats = session_features(ts, opens, closes, highs, lows, volumes, p)
    W = holding_flags(feats["event"], p["hold"])          # position during session d

    n = len(ts)
    w = np.zeros((n, 3))
    w1 = np.empty(n)
    w1[:] = W[day_id]                                     # default: today's state
    w1[last] = np.r_[W[1:], 0.0][day_id[last]]            # last bar -> next session
    w1 *= p["size"]
    w[:, 1] = w1
    w[:, 2] = 1.0 - w1

    info = {
        "params": {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in p.items()},
        "sessions": int(len(first)),
        "events": int(feats["event"].sum()),
        "event_dates": [str(d) for d in dates[first][feats["event"]]],
        "sessions_long": int(W.sum()),
        "exposure": float(W.mean()),
        "first_session": str(dates[0]),
        "last_session": str(dates[-1]),
    }
    return w, info


# --------------------------------------------------------------------------- #
# evaluation (only runs behind --authorized)
# --------------------------------------------------------------------------- #
def _daily_ret(res, ts):
    return bt.daily_last(res["equity"], ts).pct_change().dropna()


def _stats(res, ts):
    s = bt.stats(res, BARS_1M)
    keys = ("cagr", "max_drawdown", "sharpe", "sortino", "volatility",
            "exposure", "turnover")
    out = {k: float(s[k]) for k in keys}
    out["fills"] = int(s["fills"])
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--authorized" not in argv:
        print("BACKTESTS PAUSED (2026-11-26). Re-run with --authorized once the "
              "lead authorises the test. Nothing was simulated and no result.json "
              "was written.")
        return 0

    ts, op, cl, hi, lo, vol = load_panel()
    w, info = build_weights(ts, op, cl, hi, lo, vol)

    out = {
        "agent": "volume-orderflow",
        "original": "research/agents2/volume-orderflow",
        "status": "pending_test",
        "idea": "A heavy-volume intraday decline that closes in the upper half of "
                "its range marks absorbed supply, so TQQQ rises over the next "
                "five sessions.",
        "hypothesis": "Participation-conditioned supply climaxes forecast positive "
                      "five-session TQQQ returns after costs.",
        "universe": ["QQQ (signal)", "TQQQ (3x expression)", "BIL (cash)"],
        "frozen_commit": None,
        "windows": {"dev": {}, "holdout": None, "10y": None, "5y": None},
        "marks": "1m",
        "info": info,
    }

    for slip, tag in ((1.0, "1bp"), (5.0, "5bp"), (10.0, "10bp")):
        r = bt.run(ts, op, cl, w, DEV_START, band=0.02, slippage_bps=slip)
        out["windows"]["dev"][tag] = _stats(r, ts)

    # benchmarks and the correlation reference (never used as a gate)
    bench = {}
    for name, col in (("tqqq", 1), ("qqq", 0), ("bil", 2)):
        wb = np.zeros((len(ts), 3)); wb[:, col] = 1.0
        rb = bt.run(ts, op, cl, wb, DEV_START, band=0.02, slippage_bps=1.0)
        s = bt.stats(rb, BARS_1M)
        bench[name] = {"cagr": float(s["cagr"]), "max_drawdown": float(s["max_drawdown"]),
                       "sharpe": float(s["sharpe"])}
    base_w = np.zeros((len(ts), 3))
    # 165-day baseline: benchmark + correlation reference only
    _, first, last, day_id = sessions(ts)
    qc = cl[last, 0]
    sma = pd.Series(qc).rolling(165).mean().to_numpy()
    reg = np.zeros(len(qc), bool)
    reg[1:] = qc[:-1] > sma[:-1]
    on = reg[day_id]
    base_w[:, 1] = on; base_w[:, 2] = 1 - on
    rb = bt.run(ts, op, cl, base_w, DEV_START, band=0.02, slippage_bps=1.0)
    s = bt.stats(rb, BARS_1M)
    bench["baseline_165d"] = {"cagr": float(s["cagr"]),
                              "max_drawdown": float(s["max_drawdown"]),
                              "sharpe": float(s["sharpe"])}

    r_strat = bt.run(ts, op, cl, w, DEV_START, band=0.02, slippage_bps=1.0)
    d_s = _daily_ret(r_strat, ts)
    d_b = _daily_ret(rb, ts)
    j = d_s.index.intersection(d_b.index)
    rho = float(np.corrcoef(d_s.loc[j], d_b.loc[j])[0, 1])
    out["corr_vs_165d_baseline"] = rho
    out["max_corr_vs_other_rebuilds"] = None   # lead computes across rebuilds
    out["benchmarks"] = bench
    out["status"] = "pending_audit"

    (HERE / "result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"dev 1bp CAGR {out['windows']['dev']['1bp']['cagr']*100:.2f}%  "
          f"DD {out['windows']['dev']['1bp']['max_drawdown']*100:.2f}%  "
          f"events {info['events']}  corr_vs_base {rho:+.3f}")
    print("wrote", HERE / "result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
