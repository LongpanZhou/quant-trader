"""Second standalone screen: short-term pullback + late-day flow, multi-day holds."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research"))
import bt

HERE = Path(__file__).resolve().parent
CACHE = HERE / "panel_dev.npz"
START = "2016-01-04"
z = np.load(CACHE)
ts = pd.DatetimeIndex(z["ts"]).tz_localize("UTC").tz_convert("America/New_York")
opens, closes = z["opens"], z["closes"]

dates = ts.normalize()
uniq = pd.DatetimeIndex(sorted(set(dates)))
sess = np.searchsorted(uniq.values, dates.values)
mins = (ts.hour * 60 + ts.minute) - (9 * 60 + 30)
n_sess, n = len(uniq), len(ts)
starts = np.searchsorted(sess, np.arange(n_sess), side="left")
ends = np.searchsorted(sess, np.arange(n_sess), side="right")

def last_close(col=0):
    out = np.full(n_sess, np.nan); ok = ends > starts
    out[ok] = closes[ends[ok] - 1, col]; return out

def at_minute(minute, col=0, use_open=False):
    out = np.full(n_sess, np.nan); sel = mins == minute
    arr = opens if use_open else closes
    out[sess[sel]] = arr[sel, col]; return out

qclose = last_close(0)
prev = pd.Series(qclose).shift(1).to_numpy()
q1459 = at_minute(329, 0)
q1529 = at_minute(359, 0)
flow = q1459 / prev - 1.0
# prior 20-day high, known at 14:59: max of closes through prior session
high20 = pd.Series(qclose).rolling(20).max().shift(1).to_numpy()
dd20 = q1459 / high20 - 1.0
# prior 20-day realized vol
sig20 = pd.Series(qclose).pct_change().rolling(20).std().shift(1).to_numpy()
sig_med = np.nanmedian(sig20)

s = pd.Series(qclose)
sma165 = s.rolling(165).mean().shift(1).to_numpy()
base_on = pd.Series(qclose).shift(1).to_numpy() > sma165

def all_bil():
    w = np.zeros((n, 3)); w[:, 2] = 1.0; return w
def all_tqqq():
    w = np.zeros((n, 3)); w[:, 1] = 1.0; return w
def set_bars(w, k, a_min, b_min, asset, frac=1.0):
    a, b = starts[k], ends[k]
    if b <= a: return
    m = mins[a:b]
    sel = (m >= a_min) & (m < b_min)
    if not sel.any(): return
    w[a:b][sel, :] = 0.0
    w[a:b][sel, asset] = frac

def baseline_weights():
    w = all_bil()
    for k in range(n_sess):
        if base_on[k]:
            a, b = starts[k], ends[k]
            w[a:b, 2] = 0.0; w[a:b, 1] = 1.0
    return w

def event_hold(signal, entry_min, hold_sessions):
    """Enter at entry_min (329=15:00, 388=15:59); hold H full sessions after.

    hold_sessions=0 means exit at the same session's close (15:59) for a
    15:00 entry, or at the next open for a 15:59 entry.
    """
    w = all_bil()
    holding = False
    exit_at = -1
    for k in range(n_sess):
        a, b = starts[k], ends[k]
        if not holding:
            if not signal[k]:
                continue
            if entry_min == 329:
                set_bars(w, k, 329, 389, 1)
            else:
                set_bars(w, k, 388, 389, 1)
            holding = True
            exit_at = k + hold_sessions
            if hold_sessions == 0:
                if entry_min == 329:
                    set_bars(w, k, 388, 390, 2)   # sell 15:59, stay BIL
                else:
                    set_bars(w, k, 389, 390, 2)   # sell next open
                holding = False
        else:
            w[a:b, :] = 0.0; w[a:b, 1] = 1.0
            if k >= exit_at:
                set_bars(w, k, 388, 390, 2)       # sell 15:59
                holding = False
    return w

def event_hold_until(signal, entry_min, exit_cond):
    """Enter on signal; exit at 15:59 of the first session where exit_cond is true."""
    w = all_bil()
    holding = False
    for k in range(n_sess):
        if not holding:
            if not signal[k]:
                continue
            if entry_min == 329:
                set_bars(w, k, 329, 389, 1)
            else:
                set_bars(w, k, 388, 389, 1)
            holding = True
        else:
            a, b = starts[k], ends[k]
            w[a:b, :] = 0.0; w[a:b, 1] = 1.0
            if exit_cond[k]:
                set_bars(w, k, 388, 389, 2)
                holding = False
    return w

def combine(sleeves):
    w = np.zeros((n, 3))
    for s in sleeves:
        w += s
    # if overlap, normalise to <=1
    tot = w.sum(axis=1)
    over = tot > 1.0
    w[over] /= tot[over, None]
    return w

cands, labels = [], []
def add(label, w):
    cands.append(w); labels.append(label)

add("baseline_165d", baseline_weights())
add("tqqq_bh", all_tqqq())

# short-term pullback + late-day rally, multi-day holds
for dd in [-0.02, -0.03, -0.05]:
    for th in [0.005, 0.01, 0.015]:
        for h in [0, 1, 3, 5]:
            sig = (dd20 < dd) & (flow > th)
            add(f"dd{abs(dd)*100:.0f}_rally{th*100:.1f}_h{h}", event_hold(sig, 329, h))
# hold until the 20-day drawdown recovers above -1%
for dd in [-0.03, -0.05]:
    for th in [0.01, 0.015]:
        sig = (dd20 < dd) & (flow > th)
        exit_cond = dd20 > -0.01
        add(f"dd{abs(dd)*100:.0f}_rally{th*100:.1f}_untilrec", event_hold_until(sig, 329, exit_cond))
# down-day late-day reversal, multi-day holds
for th in [0.01, 0.015, 0.02]:
    for h in [0, 1, 3, 5]:
        sig = (flow < -th)
        add(f"downrev{th*100:.1f}_h{h}", event_hold(sig, 388, h))
# flow-scaled last hour
w = all_bil()
for k in range(n_sess):
    f = flow[k]
    if np.isfinite(f) and f > 0:
        frac = min(1.0, f / 0.01)
        set_bars(w, k, 329, 388, 1, frac)
add("flow_scaled_hour", w)
# high-vol last hour
for th in [0.005, 0.01]:
    sig = (flow > th) & (sig20 > sig_med)
    add(f"hivol_rally{th*100:.1f}_h0", event_hold(sig, 329, 0))
# combined: up-day last hour + down-day overnight
up = event_hold((flow > 0.005), 329, 0)
dn = event_hold((flow < -0.01), 388, 0)
add("combo_up_hour_down_night", combine([up, dn]))

print("candidates", len(cands), flush=True)
res = bt.run_many(ts, opens, closes, cands, start=START, band=0.02, slippage_bps=1.0)
base_ret = None
print(f"{'label':34s} {'CAGR':>7s} {'DD':>6s} {'Sharpe':>6s} {'fils':>6s} {'corr':>6s}")
for lab, r in zip(labels, res):
    st = bt.stats(r, 252 * 390)
    eqd = np.full(n_sess, np.nan); ok = ends > starts
    eqd[ok] = r["equity"][ends[ok] - 1]
    ret = pd.Series(eqd).pct_change()
    if lab == "baseline_165d":
        base_ret = ret; corr = 1.0
    else:
        corr = ret.corr(base_ret)
    print(f"{lab:34s} {st['cagr']*100:7.2f} {st['max_drawdown']*100:6.2f} "
          f"{st['sharpe']:6.2f} {st['fills']:6d} {corr:6.3f}")
