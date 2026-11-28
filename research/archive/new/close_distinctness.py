import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
sys.path.insert(0, str(ROOT / "research" / "new"))
import bt
import run_holdout as R

WINNERS = ["ratio-froth", "vol-scaled-crash-stop", "relative-value-tqqq",
           "fomc-opex-window", "family-session-timing", "family-short-reversal",
           "family-rebalance-flow", "family-intraday-microstructure-day"]

allj = json.loads((ROOT / "web/public/data/compare/all.json").read_text())
curves = {s["id"]: pd.Series(s["values"], index=pd.to_datetime(allj["dates"]))
          for s in allj["series"]}
print("series ids:", [k for k in curves if "tqqq" in k.lower() or "qqq" in k.lower() or "bench" in k.lower()][:10])
print("total series", len(curves))

# TQQQ benchmark: find the buy-and-hold TQQQ curve by CAGR near 37.5 and name
cands = []
for k, v in curves.items():
    r = v.pct_change().dropna()
    if len(r) < 1000:
        continue
    cagr = (v.iloc[-1] / v.iloc[0]) ** (252 / len(v)) - 1
    cands.append((abs(cagr - 0.375), k, cagr))
cands.sort()
print("closest to TQQQ 37.5%:", [(k, round(c, 3)) for _, k, c in cands[:5]])
tqqq_id = cands[0][1]
print("using", tqqq_id)

close = curves["family-close-location"].pct_change().dropna()
tqqq = curves[tqqq_id].pct_change().reindex(close.index)


def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + [x.to_numpy() for x in X])
    b = np.linalg.lstsq(X, y.to_numpy(), rcond=None)[0]
    e = y.to_numpy() - X @ b
    s2 = e @ e / max(1, len(y) - X.shape[1])
    cov = s2 * np.linalg.inv(X.T @ X)
    t = b / np.sqrt(np.diag(cov))
    r2 = 1 - (e @ e) / ((y.to_numpy() - y.mean()) ** 2).sum()
    return b, t, e, r2


b, t, resid, r2 = ols(close, [tqqq])
print(f"close on TQQQ: beta={b[1]:.3f} alpha_ann={b[0]*252*100:.2f}% "
      f"alpha_t={t[0]:.2f} R2={r2:.3f}")

resid_s = pd.Series(resid, index=close.index)
print("residual corr with winners (after removing TQQQ beta):")
for w in WINNERS:
    wr = curves[w].pct_change().reindex(close.index)
    df = pd.concat([close, tqqq, wr], axis=1, join="inner").dropna()
    y = df.iloc[:, 0]
    x = df.iloc[:, 1]
    bb, _, ee, _ = ols(y, [x])
    rw = pd.Series(ee, index=df.index)
    # residualize winner the same way
    b2, _, e2, _ = ols(df.iloc[:, 2], [x])
    rw2 = pd.Series(e2, index=df.index)
    print(f"  {w:34s} raw={np.corrcoef(y, df.iloc[:,2])[0,1]:.3f} "
          f"resid={np.corrcoef(rw, rw2)[0,1]:.3f}")

# multi-factor regression on all winners
X = [curves[w].pct_change().reindex(close.index) for w in WINNERS]
df = pd.concat([close, tqqq] + X, axis=1, join="inner").dropna()
y = df.iloc[:, 0]
mf = [df.iloc[:, 2 + i] for i in range(len(WINNERS))]
b, t, e, r2 = ols(y, mf)
print(f"close on 8 winners: alpha_ann={b[0]*252*100:.2f}% alpha_t={t[0]:.2f} R2={r2:.3f}")

# conditional returns using cached states
states = dict(np.load(ROOT / "research/new/_full_states.npz", allow_pickle=True))
ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), R.START, R.END, "1min", warmup_days=0)
_, _, last = bt.day_bounds(ts)
sess_dates = pd.to_datetime(pd.Index(ts).normalize().unique())
if sess_dates.tz is not None:
    sess_dates = sess_dates.tz_localize(None)
# states are per session, aligned to unique days
for w in ("family-short-reversal", "ratio-froth"):
    st = states[w]
    if len(st) != len(sess_dates):
        print("state length mismatch", w, len(st), len(sess_dates))
        continue
    sr = pd.Series(st, index=sess_dates).reindex(close.index).fillna(False).astype(bool)
    on = close[sr]
    off = close[~sr]
    print(f"{w}: on_n={len(on)} on_mean={on.mean()*1e4:.2f}bp on_ann={on.mean()*252*100:.1f}% | "
          f"off_n={len(off)} off_mean={off.mean()*1e4:.2f}bp off_ann={off.mean()*252*100:.1f}%")
