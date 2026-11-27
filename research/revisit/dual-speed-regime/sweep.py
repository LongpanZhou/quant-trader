"""Step-3 variant sweep (development period only). Every variant is counted."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '.')
import strategy as S
bt = S.bt
ts, o, c = bt.panel(S.SYMS, S.DEV_START, S.DEV_END, "1min", warmup_days=500)
assert ts[-1] < pd.Timestamp("2023-12-30", tz="America/New_York")
dates, first, last, day_id = S.day_index(ts)
n = len(ts)
ends, bq, dof = S.bars_60m(c[:, 0], first, last)
_, bT, _ = S.bars_60m(c[:, 1], first, last)
cnt = np.bincount(dof, minlength=len(first))

def build(fast=10, slow=30, band=0.0, strong=0.003, atr_k=2.5, overnight=False,
          idle="bil", tiers=True, lag=0, warm=60):
    ef, es = S.ema(bq, fast), S.ema(bq, slow)
    sp = ef / es - 1.0
    if lag: sp = np.r_[np.full(lag, np.nan), sp[:-lag]]
    atr = S.atr14(bT)
    hold = np.zeros(n); j = 0; in_pos = False; high = np.nan
    for k, (f, l) in enumerate(zip(first, last)):
        nb = cnt[k]; stopped = False
        if not overnight: in_pos = False
        for m in range(nb):
            b = j + m; e = ends[b]; s = sp[b]; ct = bT[b]
            if overnight:
                hard = False; can = b >= warm and np.isfinite(s)
            else:
                hard = (e >= f + 359) or (m >= nb - 2)
                can = b >= warm and e <= f + 299 and not hard and np.isfinite(s)
            if in_pos:
                high = max(high, ct)
                stop = atr_k > 0 and np.isfinite(atr[b]) and ct < high - atr_k * atr[b]
                if hard or s < -band or stop:
                    if stop: stopped = True
                    in_pos = False
            elif can and not stopped and s > band:
                in_pos = True; high = ct
            size = 0.0
            if in_pos: size = (1.0 if s > strong else 0.5) if tiers else 1.0
            nxt = ends[b + 1] if (b + 1 < len(ends) and dof[b + 1] == k) else l + 1
            hold[e:nxt] = size
        j += nb
    w = np.zeros((n, 3)); w[:, 1] = hold
    if idle == "bil": w[:, 2] = 1 - hold
    return w

wb = S.baseline_165_for_correlation(ts, c, first, last, day_id)
rb = bt.run(ts, o, c, wb, S.DEV_START, 0.02, 1.0)
db = S.daily_returns(rb["equity"], rb["ts"])
SUB = [("2016-01-04", "2019-12-31"), ("2020-01-02", "2021-12-31"), ("2022-01-03", "2023-12-29")]

def evaluate(w):
    out = {}

    for slip in (1, 5, 10):
        r = bt.run(ts, o, c, w, S.DEV_START, 0.02, slip); s = bt.stats(r, S.BPY)
        out[slip] = s
        if slip == 1: r1 = r
    a = S.daily_returns(r1["equity"], r1["ts"])
    jn = pd.concat([a, db], axis=1, join="inner").dropna()
    out["corr"] = float(jn.iloc[:, 0].corr(jn.iloc[:, 1]))
    out["sub"] = [S.sub_period(r1, r1["ts"], x, y)["cagr"] for x, y in SUB]
    out["fy"] = out[1]["fills"] / out[1]["years"]
    out["expo"] = float(w[:, 1].mean())
    return out

def row(name, ev):
    s1, s5, s10 = ev[1], ev[5], ev[10]
    return (f"| {name} | {s1['cagr']*100:.2f}% / {s1['max_drawdown']*100:.1f}% / {s1['sharpe']:.2f} | "
            f"{s5['cagr']*100:.2f}% / {s5['sharpe']:.2f} | {s10['cagr']*100:.2f}% | {ev['corr']:.3f} | "
            f"{ev['fy']:.0f} | {ev['expo']:.2f} | " + " / ".join(f"{x*100:.1f}%" for x in ev["sub"]) + " |")

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "a"
    print("| variant | 1bp CAGR / DD / Sharpe | 5bp CAGR / Sharpe | 10bp CAGR | corr165 | fills/yr | avg TQQQ w | sub 16-19 / 20-21 / 22-23 |")
    print("|---|---|---|---|---|---|---|---|")
    V = []
    if which == "a":
        V = [("V0 current (intraday, BIL, tiers)", {}),
             ("V1 cash idle", dict(idle="cash")),
             ("V2 no tiers (100%)", dict(tiers=False)),
             ("V3 cash + no tiers", dict(idle="cash", tiers=False)),
             ("V4 cash + band 0.1%", dict(idle="cash", band=0.001)),
             ("V5 overnight hold (BIL, tiers)", dict(overnight=True)),
             ("V6 overnight, cash, no tiers", dict(overnight=True, idle="cash", tiers=False)),
             ("V7 overnight, BIL, no tiers", dict(overnight=True, tiers=False)),
             ("V8 overnight, BIL, no tiers, no ATR", dict(overnight=True, tiers=False, atr_k=0)),
             ("V9 overnight, BIL, tiers, no ATR", dict(overnight=True, atr_k=0)),
             ]
    else:
        exec(open(which).read())
    for name, kw in V:
        print(row(name, evaluate(build(**kw))), flush=True)
