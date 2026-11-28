"""Standalone late-day LETF-flow candidate screen, development period only.

No 165-day (or any 100-250 day) MA gate. No old base weights.
Dev: 2016-01-04 .. 2023-12-29.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research"))
import bt

CACHE = Path(__file__).resolve().parent / "panel_dev.npz"
START, END = "2016-01-04", "2023-12-29"

if CACHE.exists():
    z = np.load(CACHE)
    ts = pd.DatetimeIndex(z["ts"]).tz_localize("UTC").tz_convert("America/New_York")
    opens, closes = z["opens"], z["closes"]
else:
    ts, opens, closes = bt.panel(("QQQ", "TQQQ", "BIL"), START, END, "1min", warmup_days=0)
    np.savez_compressed(CACHE, ts=ts.tz_convert("UTC").tz_localize(None).astype("datetime64[ns]").asi8,
                        opens=opens, closes=closes)

dates = ts.normalize()
uniq = pd.DatetimeIndex(sorted(set(dates)))
sess = np.searchsorted(uniq.values, dates.values)
mins = (ts.hour * 60 + ts.minute) - (9 * 60 + 30)
n_sess, n = len(uniq), len(ts)
starts = np.searchsorted(sess, np.arange(n_sess), side="left")
ends = np.searchsorted(sess, np.arange(n_sess), side="right")
print("dev bars", n, "sessions", n_sess, uniq[0].date(), uniq[-1].date(), flush=True)

def last_close(col=0):
    out = np.full(n_sess, np.nan)
    ok = ends > starts
    out[ok] = closes[ends[ok] - 1, col]
    return out

def at_minute(minute, col=0, use_open=False):
    out = np.full(n_sess, np.nan)
    sel = mins == minute
    arr = opens if use_open else closes
    out[sess[sel]] = arr[sel, col]
    return out

qclose = last_close(0)
prev = pd.Series(qclose).shift(1).to_numpy()
q1459 = at_minute(329, 0)
q1529 = at_minute(359, 0)
q1558 = at_minute(388, 0)
q1500o = at_minute(330, 0, True)
q1530o = at_minute(360, 0, True)
tclose = last_close(1)
tprev = pd.Series(tclose).shift(1).to_numpy()
t1500o = at_minute(330, 1, True)
t1530o = at_minute(360, 1, True)
t1559o = at_minute(390, 1, True)  # does not exist; use next open later

flow = q1459 / prev - 1.0
last30 = q1529 / q1459 - 1.0
last60 = q1558 / q1459 - 1.0
day = qclose / prev - 1.0
# next session's 09:30 open for overnight marks
next_open = np.full(n_sess, np.nan)
next_open[:-1] = at_minute(0, 1, True)[1:]

# ------------------------------------------------------------------ baseline
s = pd.Series(qclose)
sma165 = s.rolling(165).mean().shift(1).to_numpy()
base_on = pd.Series(qclose).shift(1).to_numpy() > sma165

def all_bil():
    w = np.zeros((n, 3)); w[:, 2] = 1.0
    return w

def all_tqqq():
    w = np.zeros((n, 3)); w[:, 1] = 1.0
    return w

def set_range(w, k, a_min, b_min, asset):
    a, b = starts[k], ends[k]
    if b <= a:
        return
    m = mins[a:b]
    sel = (m >= a_min) & (m < b_min)
    if not sel.any():
        return
    w[a:b][sel, :] = 0.0
    w[a:b][sel, asset] = 1.0

def baseline_weights():
    w = all_bil()
    for k in range(n_sess):
        if base_on[k]:
            a, b = starts[k], ends[k]
            w[a:b, 2] = 0.0
            w[a:b, 1] = 1.0
    return w

# ------------------------------------------------------------------ candidates
def pure_last_hour(th):
    """Long TQQQ 15:00->15:59 only when flow > th; BIL otherwise."""
    w = all_bil()
    m = flow > th
    for k in np.where(m)[0]:
        set_range(w, k, 329, 388, 1)
    return w, m

def pure_last_hour_overnight(th):
    """Long 15:00 -> next open when flow > th."""
    w = all_bil()
    m = flow > th
    for k in np.where(m)[0]:
        set_range(w, k, 329, 389, 1)
        # last bar BIL -> sell at next open
        a, b = starts[k], ends[k]
        w[b - 1, :] = 0.0; w[b - 1, 2] = 1.0
    return w, m

def overnight_reversal_down(th):
    """Buy 15:59, sell next open, when flow < -th (down-day bounce)."""
    w = all_bil()
    m = flow < -th
    for k in np.where(m)[0]:
        a, b = starts[k], ends[k]
        # bar 388 buys at 15:59; bar 389 BIL sells next open
        ii = np.where(mins[a:b] == 388)[0]
        if len(ii):
            w[a + ii[0], :] = 0.0; w[a + ii[0], 1] = 1.0
        w[b - 1, :] = 0.0; w[b - 1, 2] = 1.0
    return w, m

def default_long_exit(th, horizon):
    """Default 100% TQQQ; on flow < -th go BIL.

    horizon='hour': flat 15:00->15:59 (re-enter 15:59)
    horizon='night': flat 15:00->next open
    horizon='day': flat 15:00->next session's close (re-enter following open)
    """
    w = all_tqqq()
    m = flow < -th
    for k in np.where(m)[0]:
        if horizon == "hour":
            set_range(w, k, 329, 388, 2)
        elif horizon == "night":
            set_range(w, k, 329, 389, 2)
        elif horizon == "day":
            set_range(w, k, 329, 389, 2)
            if k + 1 < n_sess:
                a, b = starts[k + 1], ends[k + 1]
                w[a:b, :] = 0.0; w[a:b, 2] = 1.0
    return w, m

def daily_flow_timing(sig, intraday=True):
    """Signal at session k decides session k+1; owns the whole position."""
    w = all_bil()
    if intraday:
        # buy at 09:31 of the next session, sell at 15:59, flat overnight
        for k in range(n_sess - 1):
            if not sig[k]:
                continue
            a, b = starts[k + 1], ends[k + 1]
            if b <= a:
                continue
            w[a:b, :] = 0.0
            w[a:b, 1] = 1.0
            ii = np.where(mins[a:b] == 388)[0]
            if len(ii):
                w[a + ii[0], :] = 0.0
                w[a + ii[0], 2] = 1.0
            w[b - 1, :] = 0.0
            w[b - 1, 2] = 1.0
    else:
        # hold from next open to the following open; last bar is the next signal
        for k in range(n_sess - 1):
            a, b = starts[k + 1], ends[k + 1]
            if b <= a:
                continue
            if sig[k]:
                w[a:b, :] = 0.0
                w[a:b, 1] = 1.0
            # last bar determines the position after this session
            w[b - 1, :] = 0.0
            if k + 1 < n_sess and sig[k + 1]:
                w[b - 1, 1] = 1.0
            else:
                w[b - 1, 2] = 1.0
    return w, sig

# Build batch
cands = []
labels = []
def add(label, w, m=None):
    cands.append(w); labels.append(label)
    return w

base = baseline_weights()
add("baseline_165d", base)
add("tqqq_bh", all_tqqq())
for th in [0.0, 0.005, 0.01, 0.015, 0.02]:
    w, m = pure_last_hour(th); add(f"pure_hour_flow>{th*100:.1f}%", w)
for th in [0.0, 0.01, 0.015]:
    w, m = pure_last_hour_overnight(th); add(f"pure_hour_night_flow>{th*100:.1f}%", w)
for th in [0.005, 0.01, 0.015, 0.02]:
    w, m = overnight_reversal_down(th); add(f"overnight_rev_flow<-{th*100:.1f}%", w)
for th in [0.01, 0.015, 0.02, 0.025, 0.03]:
    for h in ["hour", "night", "day"]:
        w, m = default_long_exit(th, h); add(f"deflong_exit_{h}_flow<-{th*100:.1f}%", w)
for sig_name, sig in [("flow>0", flow > 0), ("flow>0.5", flow > 0.005),
                      ("last60>0", last60 > 0), ("day>0", day > 0)]:
    for intra in [True, False]:
        w, m = daily_flow_timing(sig, intra)
        add(f"daily_{'intra' if intra else '24h'}_{sig_name}", w)

print("candidates", len(cands), flush=True)
res = bt.run_many(ts, opens, closes, cands, start=START, band=0.02, slippage_bps=1.0)
print(f"{'label':38s} {'CAGR':>7s} {'DD':>6s} {'Sharpe':>6s} {'fils':>6s} {'corr':>6s}")
base_eq = None
base_ret = None
for lab, r in zip(labels, res):
    st = bt.stats(r, 252 * 390)
    dts, eq = None, None
    # daily marks
    eqd = np.full(n_sess, np.nan)
    eqd[sess] = r["equity"]
    # use last bar per session
    eqd = np.full(n_sess, np.nan)
    ok = ends > starts
    eqd[ok] = r["equity"][ends[ok] - 1]
    ret = pd.Series(eqd).pct_change()
    if lab == "baseline_165d":
        base_ret = ret
        corr = 1.0
    else:
        corr = ret.corr(base_ret)
    print(f"{lab:38s} {st['cagr']*100:7.2f} {st['max_drawdown']*100:6.2f} "
          f"{st['sharpe']:6.2f} {st['fills']:6d} {corr:6.3f}")
