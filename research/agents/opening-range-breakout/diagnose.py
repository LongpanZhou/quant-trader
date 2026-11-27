"""Diagnostics for a chosen ORB config: equity path, drawdowns, trades."""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research")
sys.path.insert(0, "research/agents/opening-range-breakout")
import bt
import explore2 as e


def trade_log(ts, t, w, opens):
    """Reconstruct round trips from weight changes (next-open fills)."""
    tt = w[:, 1]
    trades = []
    i = 0
    n = len(ts)
    inpos = False
    entry_i = None
    for i in range(n - 1):
        if not inpos and tt[i] > 0 and w[i, 2] < 0.5:
            inpos = True
            entry_i = i + 1
            entry_px = opens[i + 1, 1]
        elif inpos and tt[i] == 0:
            exit_px = opens[i + 1, 1]
            trades.append((ts[entry_i], entry_px, ts[i + 1], exit_px,
                           exit_px / entry_px - 1, (ts[i + 1] - ts[entry_i]).total_seconds() / 86400))
            inpos = False
    if inpos:
        trades.append((ts[entry_i], opens[entry_i, 1], ts[-1], opens[-1, 1],
                       opens[-1, 1] / opens[entry_i, 1] - 1, (ts[-1] - ts[entry_i]).total_seconds() / 86400))
    return pd.DataFrame(trades, columns=["entry", "entry_px", "exit", "exit_px", "ret", "days"])


def main():
    ts, opens, closes, q, t, b = e.load_all()
    d = e.daily_tables(ts, q, t)
    cfg = dict(or_min=30, intraday_only=False, stop_mode="orlow")
    w = e.make_weights(ts, q, t, d, **cfg)
    out, yr = e.evaluate(ts, opens, closes, w)
    print(cfg)
    for tag in ("10y", "5y"):
        s = out[tag]
        print(e.fmt(tag, s))
        print("   bench CAGR %.2f%% DD %.2f%%" % (s["bench"]["cagr"] * 100, s["bench"]["max_drawdown"] * 100))
    print("\nyearly:")
    for y, v in yr["10y"].items():
        print(f"  {y}: strat {v['strategy']*100:7.2f}%  bench {v['benchmark']*100:7.2f}%")

    res = bt.run(ts, opens, closes, w, e.START10, band=0.02, slippage_bps=1.0)
    eq = pd.Series(res["equity"], index=res["ts"])
    daily = eq.groupby(eq.index.date).last()
    print("\nfirst/last daily equity", daily.iloc[0], daily.iloc[-1])
    # drawdown episodes
    peak = daily.cummax()
    dd = daily / peak - 1
    print("\nworst 10 daily drawdown troughs:")
    for dt, v in dd.nsmallest(5).items():
        print(f"  {dt} {v*100:.2f}%")
    # max dd window
    trough = dd.idxmin()
    peak_date = daily.loc[:trough].idxmax()
    print("max DD", peak_date, "->", trough, f"{dd.min()*100:.2f}%")

    tr = trade_log(ts, t, w, opens)
    tr = tr[tr["entry"] >= pd.Timestamp(e.START10, tz="America/New_York")]
    print(f"\ntrades {len(tr)}  winrate {(tr['ret']>0).mean()*100:.1f}%  avg {tr['ret'].mean()*100:+.2f}%  "
          f"median {tr['ret'].median()*100:+.2f}%  avg days {tr['days'].mean():.1f}")
    print(tr.head(12).to_string())
    print("\nexposure by year (fraction of minutes in TQQQ):")
    longs = pd.Series(w[:, 1] > 0, index=ts)
    print((longs.groupby(longs.index.year).mean() * 100).round(1))


if __name__ == "__main__":
    main()
