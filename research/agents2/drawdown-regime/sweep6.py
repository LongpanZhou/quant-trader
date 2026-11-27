"""Sweep 6: forward returns by drawdown bucket; entry-side recovery filters;
base-stop interaction with the conditional tight stop."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ddlib as L


def fwd_table(dctx, closes):
    first, last = dctx["first"], dctx["last"]
    tq = closes[last, 1]
    qq = closes[last, 0]
    dd = dctx["dd_prev"]
    reg = dctx["reg"]
    buckets = [(0.0, -0.03), (-0.03, -0.05), (-0.05, -0.08),
               (-0.08, -0.12), (-0.12, -0.20), (-0.20, -1.0)]
    print(f"{'bucket':>14} {'n':>5} {'fwd5 TQQQ':>10} {'hit':>5} "
          f"{'fwd20 TQQQ':>11} {'hit':>5} {'fwd20 QQQ':>10}")
    for lo, hi in buckets:
        m = reg & (dd <= lo) & (dd > hi) if hi > -1 else reg & (dd <= lo)
        rows5, rows20 = [], []
        idx = np.flatnonzero(m)
        for k in idx:
            if k + 5 < len(tq):
                rows5.append(tq[k + 5] / tq[k] - 1)
            if k + 20 < len(tq):
                rows20.append(tq[k + 20] / tq[k] - 1)
        a5, a20 = np.array(rows5), np.array(rows20)
        q20 = np.array([qq[k + 20] / qq[k] - 1 for k in idx if k + 20 < len(qq)])
        print(f"{lo*100:6.1f}..{hi*100:6.1f} {len(idx):5d} {a5.mean()*100:9.2f}% "
              f"{(a5>0).mean()*100:4.0f}% {a20.mean()*100:10.2f}% "
              f"{(a20>0).mean()*100:4.0f}% {q20.mean()*100:9.2f}%")
    print("\ndd<=-8% while regime ON, forward TQQQ:")
    m = reg & (dd <= -0.08)
    print(f"  n={m.sum()}  fwd5 {np.mean([tq[k+5]/tq[k]-1 for k in np.flatnonzero(m) if k+5<len(tq)])*100:.2f}%"
          f"  fwd20 {np.mean([tq[k+20]/tq[k]-1 for k in np.flatnonzero(m) if k+20<len(tq)])*100:.2f}%")


def entry_filter(ts, opens, closes, dctx, rec_thr, sma_n=165):
    """Only hold TQQQ on a fresh regime flip if QQQ is within rec_thr of its
    52w high; once in, normal regime rules apply."""
    first, last = dctx["first"], dctx["last"]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    hold = np.zeros(n)
    in_pos = False
    blocked = False
    for k, (f, l) in enumerate(zip(first, last)):
        if not dctx["reg"][k]:
            in_pos = False
            blocked = False
            continue
        if not in_pos:
            if blocked:
                if dctx["dd_prev"][k] >= -rec_thr:
                    blocked = False
            elif dctx["dd_prev"][k] <= -rec_thr:
                blocked = True
            if blocked:
                continue
            in_pos = True
        armed = bool(np.isfinite(dctx["arm_ma20"][k])
                     and qqq_close[f] < dctx["arm_ma20"][k] * 1.01)
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq_close[i] < base * 0.96:
                on = False
            hold[i] = 1.0 if on else 0.0
        in_pos = on  # stop exits -> next session needs a fresh entry check
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1 - hold
    return w


def cond_stop(ts, opens, closes, dctx, dd_thr, stop2, base_stop):
    first, last = dctx["first"], dctx["last"]
    n = len(ts)
    qqq_close, tqqq_close = closes[:, 0], closes[:, 1]
    hold = np.zeros(n)
    for k, (f, l) in enumerate(zip(first, last)):
        if not dctx["reg"][k]:
            continue
        stop = stop2 if dctx["dd_prev"][k] <= -dd_thr else base_stop
        armed = bool(np.isfinite(dctx["arm_ma20"][k])
                     and qqq_close[f] < dctx["arm_ma20"][k] * 1.01)
        base = opens[f, 1]
        on = True
        for i in range(f, l + 1):
            if on and armed and tqqq_close[i] < base * (1 - stop):
                on = False
            hold[i] = 1.0 if on else 0.0
    w = np.zeros((n, 3))
    w[:, 1] = hold
    w[:, 2] = 1 - hold
    return w


def main():
    ts, opens, closes = L.load_panel()
    dctx = L.daily_context(ts, closes)

    print("== forward returns by drawdown bucket (regime ON sessions) ==")
    fwd_table(dctx, closes)

    print("\n== entry-side recovery filter (block fresh entries while dd < -X) ==")
    for rec in (0.02, 0.03, 0.05, 0.08, 0.10, 0.15):
        w = entry_filter(ts, opens, closes, dctx, rec)
        L.fmt(f"entry needs dd>-{rec:.0%}", L.summary(ts, opens, closes, w))

    print("\n== conditional stop: base-stop interaction at dd<=-8% ==")
    for base in (0.035, 0.04, 0.05, 0.06):
        for rel in (0.4, 0.5, 0.6):
            s2 = base * rel
            w = cond_stop(ts, opens, closes, dctx, 0.08, s2, base)
            L.fmt(f"base{base:.1%} x{rel:.1f}={s2:.1%}", L.summary(ts, opens, closes, w))
        print()


if __name__ == "__main__":
    main()
