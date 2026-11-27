"""Variant 5: stop-level neighborhood, regime-weakness gate, 5bp, daily-mark DD."""
import numpy as np
import pandas as pd

import strat_lib as sl
import bt

A = sl.load_arrays()
ts, dates, first, last = A["ts"], A["dates"], A["first"], A["last"]
oc, oo, oh = A["closes"], A["opens"], A["highs"]
reg, dc, sma, _, _, _ = sl.daily_regime(ts, oc[:, 0], 165)
n = len(ts)
c = oc[:, 1]
qc = oc[:, 0]
# QQQ vs its SMA level (prev close) per minute
day_sma = np.r_[np.nan, sma[:-1]]
day_id = np.repeat(np.arange(len(first)), np.diff(np.r_[first, n]))
lvl = day_sma[day_id]
ratio = qc / lvl


def make_weights(hold):
    w = np.zeros((n, 3))
    w[:, 1] = hold.astype(float)
    w[:, 2] = 1.0 - w[:, 1]
    return w


def stop_rule(x=0.04, gate=None, reenter="never", vwap_too=False):
    """gate: None or max QQQ/SMA ratio for the stop to be armed."""
    hold = np.zeros(n, bool)
    vwap = sl.session_vwap(oh[:, 1], A["lows"][:, 1], c, A["vols"][:, 1], dates, first, last)
    for f, l in zip(first, last):
        state = bool(reg[f])
        stopped = False
        base = oo[f, 1]
        armed = True if gate is None else (ratio[f] < gate)
        for i in range(f, l + 1):
            trig = armed and state and c[i] < base * (1 - x)
            if vwap_too and state and armed and c[i] < vwap[i] and c[i] < base * (1 - x / 2):
                trig = True
            if trig:
                state = False
                stopped = True
            if stopped and reenter == "vwap" and reg[i] and c[i] > vwap[i]:
                state = True
                stopped = False
            hold[i] = state
        if reg[l] and reenter == "close":
            hold[l - 1:l + 1] = True
    return hold


def metrics(hold, slip=1.0):
    w = make_weights(hold)
    res = {}
    for start in (sl.START10, sl.START5):
        r = bt.run(ts, A["opens"], oc, w, start, band=0.02, slippage_bps=slip)
        s = bt.stats(r, 252 * 390)
        i = bt.start_index(ts, start)
        # daily-mark DD
        eq = pd.Series(r["equity"], index=ts[i:])
        deq = eq.groupby(eq.index.date).last().to_numpy()
        peak = np.maximum.accumulate(deq)
        ddd = float(-(deq / peak - 1).min())
        s["dd_daily"] = ddd
        res[start] = s
    return res


def line(name, hold, slip=1.0):
    m = metrics(hold, slip)
    a, b = m[sl.START10], m[sl.START5]
    print(f"{name:30s} 10y {a['cagr']*100:6.2f}%/{a['max_drawdown']*100:5.2f}% (d{a['dd_daily']*100:5.2f}%) sh{a['sharpe']:4.2f} f{a['fills']:5d} | "
          f"5y {b['cagr']*100:6.2f}%/{b['max_drawdown']*100:5.2f}% (d{b['dd_daily']*100:5.2f}%) sh{b['sharpe']:4.2f}")
    return m


print("== stop neighborhood (no gate, out overnight) ==")
for x in (0.025, 0.03, 0.035, 0.04, 0.045, 0.05, 0.06):
    line(f"stop{x*100:.1f}%", stop_rule(x))

print("\n== with QQQ/SMA gate ==")
for gate in (1.0, 1.01, 1.02, 1.03, 1.05):
    line(f"stop4 gate {gate:.2f}", stop_rule(0.04, gate=gate))

print("\n== 5bp ==")
line("stop4 5bp", stop_rule(0.04), slip=5.0)
line("stop4 gate1.02 5bp", stop_rule(0.04, gate=1.02), slip=5.0)

print("\n== vwap-assisted stop ==")
line("stop4+vwap", stop_rule(0.04, gate=1.02, vwap_too=True))
line("stop4 re-vwap", stop_rule(0.04, reenter="vwap"))
line("stop4 re-close", stop_rule(0.04, reenter="close"))
