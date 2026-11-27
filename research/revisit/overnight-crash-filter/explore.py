"""Dev-only exploration for the standalone overnight/first-hour rebuild.

Development window only: 2016-01-04 .. 2023-12-29. The panel is loaded with
end=2023-12-29 so the holdout cannot be inspected.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_START, DEV_END = "2016-01-04", "2023-12-29"
BARS = 252 * 390
pd.set_option("display.width", 240)


def load_dev():
    ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), DEV_START, DEV_END, "1min", warmup_days=0)
    return ts, o, c


class Days:
    def __init__(self, ts, o, c):
        self.ts, self.o, self.c = ts, o, c
        dates = bt.session_dates(ts)
        self.first = np.flatnonzero(np.r_[True, dates[1:] != dates[:-1]])
        self.last = np.r_[self.first[1:] - 1, len(dates) - 1]
        self.nd = len(self.first)
        self.ddates = dates[self.first]
        self.dclose = c[self.last]
        self.dopen = o[self.first]
        self.dc_now = c[np.maximum(self.last - 1, self.first)]
        self.day_id = np.repeat(np.arange(self.nd), np.diff(np.r_[self.first, len(ts)]))

    def vol(self, n=20, col=0, ann=True):
        d = self.dclose[:, col]
        r = np.r_[np.nan, np.log(d[1:] / d[:-1])]
        s = pd.Series(r).rolling(n).std(ddof=0).to_numpy()
        return s * (np.sqrt(252.0) if ann else 1.0)

    def sma_gate_165(self):
        """Benchmark only: the old 165-day QQQ gate (never used by the strategy)."""
        d = self.dclose[:, 0]
        sma = pd.Series(d).rolling(165).mean().to_numpy()
        g = np.zeros(self.nd, bool)
        g[1:] = d[:-1] > sma[:-1]
        return g

    def block(self, kind, m=60, col=1):
        out = np.full(self.nd, np.nan)
        for k in range(self.nd):
            f, l = self.first[k], self.last[k]
            if kind == "overnight":
                if k + 1 < self.nd:
                    out[k] = self.dopen[k + 1, col] / self.o[l, col] - 1.0
            elif kind == "firstm":
                if f + m <= l:
                    out[k] = self.o[f + m, col] / self.o[f, col] - 1.0
            elif kind == "session":
                out[k] = self.c[l, col] / self.o[f, col] - 1.0
        return out


def weights_from_positions(days, p_t, p_b):
    w = np.zeros((len(days.ts), 3))
    w[:-1, 1] = p_t[1:]
    w[:-1, 2] = p_b[1:]
    w[-1, 1] = p_t[-1]
    w[-1, 2] = p_b[-1]
    return w


def build(days, vol, m=60, vol_skip=None, vol_mid=None, mid_w=0.5,
          afternoon=False, bil=True):
    """TQQQ overnight + first m minutes; optional vol ladder and afternoon."""
    p_t = np.zeros(len(days.ts))
    p_b = np.zeros(len(days.ts))
    for k in range(days.nd):
        f, l = days.first[k], days.last[k]
        v = vol[k]
        finite = np.isfinite(v)
        if not finite:
            w_t = 0.0
        elif vol_skip is not None and v > vol_skip:
            w_t = 0.0
        elif vol_mid is not None and v > vol_mid:
            w_t = mid_w
        else:
            w_t = 1.0
        p_b[f:l + 1] = (1.0 - w_t) if bil else 0.0
        if w_t > 0:
            p_t[f:min(f + m, l + 1)] = w_t
            if afternoon:
                r = days.c[min(f + m - 1, l), 0] / days.o[f, 0] - 1.0
                if r >= 0:
                    p_t[min(f + m, l + 1):l] = w_t
            p_t[l] = w_t
        else:
            p_t[l] = 0.0
    return weights_from_positions(days, p_t, p_b)


def daily_returns(ts, eq):
    s = pd.Series(eq, index=ts)
    return s.groupby(s.index.date).last().pct_change().dropna()


def main():
    ts, o, c = load_dev()
    d = Days(ts, o, c)
    print(f"dev panel {ts[0]} .. {ts[-1]}  bars {len(ts):,}  sessions {d.nd}")
    vol = d.vol(20, 0)
    on = d.block("overnight")
    f30 = d.block("firstm", 30)
    f60 = d.block("firstm", 60)
    sess = d.block("session")

    print("\n=== block stats, dev ===")
    for name, x in (("overnight", on), ("first30", f30), ("first60", f60), ("session", sess)):
        x = x[np.isfinite(x)]
        print(f"  {name:10s} n={len(x):5d} mean {x.mean()*1e4:7.2f}bp "
              f"ann {(np.exp(np.log1p(x).mean()*252)-1)*100:7.2f}%  "
              f"t {x.mean()/x.std(ddof=1)*np.sqrt(len(x)):5.2f}")

    print("\n=== overnight / first60 / session by vol bucket ===")
    for lo_, hi_ in ((0, .12), (.12, .16), (.16, .20), (.20, .25), (.25, .30), (.30, .40), (.40, 9)):
        sel = (vol >= lo_) & (vol < hi_)
        row = []
        for name, x in (("on", on), ("f60", f60), ("sess", sess)):
            y = x[sel & np.isfinite(x)]
            row.append(f"{name} {y.mean()*1e4:7.2f}bp" if len(y) else f"{name} n/a")
        print(f"  vol {lo_*100:2.0f}-{hi_*100:2.0f}% n={int(sel.sum()):4d}  " + "  ".join(row))

    # benchmark daily returns: old 165d baseline (correlation reference only)
    g = d.sma_gate_165()
    p_t = np.zeros(len(ts)); p_b = np.zeros(len(ts))
    for k in range(d.nd):
        f, l = d.first[k], d.last[k]
        p_t[f:l + 1] = 1.0 if g[k] else 0.0
        p_b[f:l + 1] = 0.0 if g[k] else 1.0
    w_base = weights_from_positions(d, p_t, p_b)
    r_base = bt.run(ts, o, c, w_base, DEV_START, band=0.02, slippage_bps=1.0)
    rb = daily_returns(ts, r_base["equity"])

    variants = {
        "V0 overnight always": build(d, vol, m=0),
        "V1 overnight+f30 always": build(d, vol, m=30),
        "V2 overnight+f60 always": build(d, vol, m=60),
        "V3 f60 skip>35": build(d, vol, m=60, vol_skip=0.35),
        "V4 f60 skip>30": build(d, vol, m=60, vol_skip=0.30),
        "V5 f60 skip>25": build(d, vol, m=60, vol_skip=0.25),
        "V6 f60 skip>35 half>25": build(d, vol, m=60, vol_skip=0.35, vol_mid=0.25, mid_w=0.5),
        "V7 f60 skip>35 +pm": build(d, vol, m=60, vol_skip=0.35, afternoon=True),
        "V8 f30 skip>35": build(d, vol, m=30, vol_skip=0.35),
    }
    print("\n=== dev results, 1bp ===")
    rows = []
    for name, w in variants.items():
        r = bt.run(ts, o, c, w, DEV_START, band=0.02, slippage_bps=1.0)
        s = bt.stats(r, BARS)
        rd = daily_returns(ts, r["equity"])
        corr = rd.corr(rb)
        rows.append({"name": name, "cagr": s["cagr"] * 100, "dd": s["max_drawdown"] * 100,
                     "sharpe": s["sharpe"], "vol": s["volatility"] * 100,
                     "fills": s["fills"], "corr": corr})
        print(f"  {name:26s} CAGR {s['cagr']*100:6.2f}%  DD {s['max_drawdown']*100:5.2f}%  "
              f"Sh {s['sharpe']:4.2f}  vol {s['volatility']*100:5.2f}%  "
              f"fills {s['fills']:5,d}  corr {corr:5.2f}")
    print(pd.DataFrame(rows).to_string(index=False, float_format=lambda x: f"{x:6.3f}"))

    s = bt.stats(r_base, BARS)
    print(f"\n  165d baseline (correlation ref): CAGR {s['cagr']*100:.2f}%  DD {s['max_drawdown']*100:.2f}%  "
          f"vol {s['volatility']*100:.2f}%")
    print(f"  baseline daily-return sd {rb.std()*100:.3f}%  n={len(rb)}")
    w_t = variants["V3 f60 skip>35"]
    rt = daily_returns(ts, bt.run(ts, o, c, w_t, DEV_START, band=0.02, slippage_bps=1.0)["equity"])
    print(f"  V3 daily-return sd {rt.std()*100:.3f}%  corr {rt.corr(rb):.3f}")


if __name__ == "__main__":
    main()
