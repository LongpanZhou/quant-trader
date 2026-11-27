"""Tune diagnostics (2026-11-27), development period only (<= 2023-12-29).

    python research/revisit/ml-classifier/tune_diag.py

Prints exposure, leverage-matched mix, per-year table, gap decomposition,
cost drag, event/hit-rate stats and placebo controls for the frozen
strategy.py headline.  Nothing after 2023-12-29 is loaded.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import strategy as S  # noqa: E402
from strategy import bt, to_minutes  # noqa: E402

DEV0_FULL = "2016-01-04"


def daily_eq(r):
    s = pd.Series(r["equity"], index=r["ts"])
    return s.groupby(s.index.normalize()).last()


def run_daily_w(tsd, w, ts1, o1, c1, start, slip=1.0):
    w1 = to_minutes(tsd, w, ts1, "1D")
    r = bt.run(ts1, o1, c1, w1, start, band=S.BAND, slippage_bps=slip)
    return r, bt.stats(r, S.BARS_1M)


def fmt(s):
    return f"CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  Sh {s['sharpe']:.2f}"


def main():
    ts5, o5, c5 = bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "5min")
    tsd, od, cd = bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "1D")
    ts1, o1, c1 = bt.panel(S.SYMBOLS, S.DEV_START, S.DEV_END, "1min")
    assert tsd[-1] <= pd.Timestamp("2023-12-29", tz="America/New_York")
    feats = S.build_features(ts5, o5, c5, tsd, od, cd)
    w, info = S.build_weights(tsd, feats, od, cd)
    i0 = bt.start_index(tsd, S.TRADE_START)

    # ---------------- headline / both windows
    print("== headline")
    for start in (S.TRADE_START, DEV0_FULL):
        for slip in (1.0, 5.0, 10.0):
            r, s = run_daily_w(tsd, w, ts1, o1, c1, start, slip)
            print(f"  from {start} {slip:>4}bp: {fmt(s)}  fills {s['fills']}")
    for start in (S.TRADE_START, DEV0_FULL):
        for name, col in (("TQQQ", 1), ("QQQ", 0)):
            j = bt.start_index(ts1, start)
            b = bt.benchmark(c1[j:, col], ts1[j:], S.BARS_1M)
            print(f"  {name} from {start}: {fmt(b)}")

    # ---------------- exposure (held asset = target of previous close)
    held = np.argmax(w, axis=1)
    held_next = np.r_[2, held[:-1]]            # asset held during day i
    seg = held_next[i0:]
    names = {0: "QQQ", 1: "TQQQ", 2: "BIL"}
    print("== exposure (share of sessions, 2017-2023; daily weights -> equal minutes/session)")
    for a in (1, 0, 2):
        print(f"  {names[a]:5s} {np.mean(seg == a)*100:5.1f}%")
    lev = np.mean(np.where(seg == 1, 3.0, np.where(seg == 0, 1.0, 0.0)))
    print(f"  avg gross leverage (TQQQ=3x): {lev:.3f}  -> static TQQQ share {lev/3:.3f}")

    # ---------------- leverage-matched static mixes
    print("== leverage-matched static mixes (daily rebalanced, 1bp)")
    for label, wt in (("TQQQ x lev/3 + BIL", np.tile([0, lev / 3, 1 - lev / 3], (len(tsd), 1))),
                      ("QQQ x min(lev,1) + BIL", np.tile([min(lev, 1), 0, 1 - min(lev, 1)], (len(tsd), 1)))):
        # band=2% blocks tiny daily rebalances; that is how bt rebalances
        r, s = run_daily_w(tsd, wt, ts1, o1, c1, S.TRADE_START)
        print(f"  {label:24s} {fmt(s)}")

    # ---------------- per-year
    print("== per-year (1bp)")
    r, s = run_daily_w(tsd, w, ts1, o1, c1, S.TRADE_START)
    eq = daily_eq(r)
    j = bt.start_index(ts1, S.TRADE_START)
    bq = pd.Series(c1[j:, 0], index=ts1[j:]).groupby(ts1[j:].normalize()).last()
    bt3 = pd.Series(c1[j:, 1], index=ts1[j:]).groupby(ts1[j:].normalize()).last()
    rows = []
    for y in range(2017, 2024):
        m = eq.index.year == y
        def yr(x):
            xs = x[m]
            prev = x[x.index.year < y]
            base = prev.iloc[-1] if len(prev) else xs.iloc[0]
            return xs.iloc[-1] / base - 1
        rows.append((y, yr(eq), yr(bt3), yr(bq)))
        print(f"  {y}: strat {rows[-1][1]*100:7.1f}%  TQQQ {rows[-1][2]*100:7.1f}%  QQQ {rows[-1][3]*100:7.1f}%")
    r16, _ = run_daily_w(tsd, w, ts1, o1, c1, DEV0_FULL)

    # ---------------- gap decomposition on daily open->open returns
    print("== gap decomposition (daily open-to-open log returns, 2017-2023)")
    lo = np.log(od[1:] / od[:-1])              # return from open i to open i+1
    hold_day = held[:-1]                       # target at close i-1 is held open i -> open i+1 ... approx
    # target at close i fills at open i+1 and is held open i+1 -> open i+2
    hold = held[i0 - 1:-2]
    rt = lo[i0:, 1]; rq = lo[i0:, 0]; rb = lo[i0:, 2]
    rs = np.choose(hold, [rq, rt, rb])
    print(f"  total log: strat {rs.sum():.3f}  TQQQ {rt.sum():.3f}  QQQ {rq.sum():.3f}")
    for a in (1, 0, 2):
        m = hold == a
        print(f"  while in {names[a]:4s}: days {m.sum():4d}  TQQQ log {rt[m].sum():+.3f} "
              f"(mean {rt[m].mean()*1e4:+.1f}bp/d)  QQQ log {rq[m].sum():+.3f}  strat log {rs[m].sum():+.3f}")
    up = rt > 0
    print(f"  TQQQ up-days missed (not in TQQQ): {np.sum(up & (hold != 1))} of {up.sum()}; "
          f"log forgone on up-days {rt[up & (hold != 1)].sum():+.3f}; "
          f"log avoided on down-days {-rt[~up & (hold != 1)].sum():+.3f}")
    # top-20 TQQQ days
    big = np.argsort(rt)[-20:]; worst = np.argsort(rt)[:20]
    print(f"  best 20 TQQQ days held in TQQQ: {np.sum(hold[big] == 1)}; worst 20 held in TQQQ: {np.sum(hold[worst] == 1)}")

    # ---------------- costs
    yrs = (ts1[-1] - ts1[j]).days / 365.25
    print("== costs")
    print(f"  switches {info['switches']} total, {info['switches']/yrs:.1f}/yr; fills {s['fills']}; "
          f"turnover {s['turnover']:.1f} (x equity? see bt)")

    # ---------------- events / hit rate: TQQQ spells
    print("== TQQQ spells (core signal events)")
    spells = []
    k = i0
    hh = held[i0 - 1:]
    idx = np.arange(i0 - 1, len(held))
    cur = None
    for t in range(len(held) - 1):
        pass
    a = held
    starts = [i for i in range(i0, len(a) - 1) if a[i] == 1 and a[i - 1] != 1]
    for st in starts:
        en = st
        while en + 1 < len(a) and a[en + 1] == 1:
            en += 1
        # held from open st+1 to open en+2
        e2 = min(en + 2, len(od) - 1)
        rt_sp = np.log(od[e2, 1] / od[st + 1, 1])
        rb_sp = np.log(od[e2, 2] / od[st + 1, 2])
        rq_sp = np.log(od[e2, 0] / od[st + 1, 0])
        spells.append((st, en - st + 1, rt_sp, rb_sp, rq_sp))
    sp = np.array([(x[1], x[2], x[3], x[4]) for x in spells])
    print(f"  spells {len(sp)}, median len {np.median(sp[:,0]):.0f}d, hit (TQQQ>BIL) {np.mean(sp[:,1] > sp[:,2])*100:.0f}%, "
          f"mean log TQQQ {sp[:,1].mean():+.4f}")
    # bootstrap: random spells of the same lengths
    rng = np.random.default_rng(0)
    n_ok = len(od) - 2
    obs = sp[:, 1].sum()
    sims = []
    for _ in range(2000):
        tot = 0.0
        for L in sp[:, 0].astype(int):
            st = rng.integers(i0, n_ok - L - 1)
            tot += np.log(od[st + L + 1, 1] / od[st + 1, 1])
        sims.append(tot)
    sims = np.array(sims)
    print(f"  sum log TQQQ in spells {obs:+.3f}; random same-length spells mean {sims.mean():+.3f}; "
          f"p(random >= obs) = {np.mean(sims >= obs):.3f}")

    # ---------------- OOS regime ordering: forward 20d TQQQ by assigned asset (mapped asset, pre-confirmation)
    print("== OOS daily-state forward returns (next-day open-to-open TQQQ, by held state)")
    for a in (1, 0, 2):
        m = hold == a
        print(f"  state {names[a]:4s}: mean TQQQ next-day {rt[m].mean()*1e4:+.1f}bp, sd {rt[m].std()*1e4:.0f}bp, "
              f"sharpe-ish {rt[m].mean()/rt[m].std()*np.sqrt(252):+.2f}")

    # ---------------- placebo: random relabelling of states keeping run lengths (block shuffle)
    print("== placebo: circular shift of the held-asset path (keeps exposure & switch count)")
    vals = []
    seg_w = w[i0:]
    for sh in rng.integers(60, len(seg_w) - 60, size=60):
        wp = w.copy()
        wp[i0:] = np.roll(seg_w, sh, axis=0)
        _, sp_ = run_daily_w(tsd, wp, ts1, o1, c1, S.TRADE_START)
        vals.append((sp_["cagr"], sp_["max_drawdown"], sp_["sharpe"]))
    vals = np.array(vals)
    print(f"  shifted: CAGR mean {vals[:,0].mean()*100:.2f}% (5-95% {np.percentile(vals[:,0],5)*100:.2f}..{np.percentile(vals[:,0],95)*100:.2f}), "
          f"Sharpe mean {vals[:,2].mean():.2f}; p(shift CAGR >= actual) {np.mean(vals[:,0] >= s['cagr']):.3f}; "
          f"p(shift Sharpe >= actual) {np.mean(vals[:,2] >= s['sharpe']):.3f}")

    # ---------------- correlation
    wb = S.correlation_benchmark_weights(tsd, cd)
    rb, sb = run_daily_w(tsd, wb, ts1, o1, c1, S.TRADE_START)
    a_ = daily_eq(r).pct_change().dropna(); b_ = daily_eq(rb).pct_change().dropna()
    print(f"== corr vs 165d baseline {a_.corr(b_):.3f}; baseline {fmt(sb)}")


if __name__ == "__main__":
    main()
