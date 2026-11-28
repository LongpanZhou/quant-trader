"""Step 2: diagnose the gap to TQQQ (dev only)."""
from common import *

ts, o, c = load()
i0 = bt.start_index(ts, DEV0)
uniq, sess, starts, ends = sessions(ts)
w, info = S.build_weights(ts, o, c)
sig = S.load_daily_signal().reindex(uniq)
wd = pd.DataFrame(info["w_daily"], index=info["dates"]).reindex(uniq)

r = {bp: bt.run(ts, o, c, w, DEV0, 0.02, bp) for bp in (1, 5, 10)}
for bp in r: print(f"{bp}bp", st(r[bp]))
s1 = bt.stats(r[1], BARS)
print("turnover x/yr", s1["turnover"] / s1["years"], "fills/yr", s1["fills"] / s1["years"])

# exposure
tq = w[:, 1].mean(); bil = w[:, 2].mean()
print(f"\nEXPOSURE minutes TQQQ {tq:.3f} QQQ 0 BIL {bil:.3f} short 0; avg gross lev {3*tq:.3f}")

# leverage-matched static mix
ws = np.zeros_like(w); ws[:, 1] = tq; ws[:, 2] = 1 - tq
rs = bt.run(ts, o, c, ws, DEV0, 0.02, 1)
print("static %.1f%% TQQQ / BIL mix:" % (100 * tq), st(rs))
for f in (0.15, 0.30):
    ws2 = np.zeros_like(w); ws2[:, 1] = f; ws2[:, 2] = 1 - f
    print(f"  static {f:.0%} TQQQ:", st(bt.run(ts, o, c, ws2, DEV0, 0.02, 1)))

# benchmarks / per-year
dr = daily_ret(ts, r[1]["equity"])
cl = pd.DataFrame(c[ends - 1], index=uniq, columns=["QQQ", "TQQQ", "BIL"])
bret = cl.pct_change(); bret.iloc[0] = cl.iloc[0] / pd.Series(o[starts[0]], index=cl.columns) - 1
mix = daily_ret(ts, rs["equity"])
base = bt.run(ts, o, c, baseline_w(ts), DEV0, 0.02, 1)
bdr = daily_ret(ts, base["equity"])
print("\nYEAR   strat   TQQQ    QQQ   static-mix  165d-base")
for y in range(2016, 2024):
    m = dr.index.year == y
    print(y, " ".join(f"{(1+x[m]).prod()-1:7.1%}" for x in (dr, bret.TQQQ, bret.QQQ, mix, bdr)))
print("corr vs 165d baseline (daily)", dr.corr(bdr), "  static mix corr", mix.corr(bdr))

# where the gap comes from: TQQQ log return in vs out of position
held = wd[1].shift(1).fillna(0).to_numpy() > 0   # position held during day t (set at t-1 close)
lt = np.log1p(bret.TQQQ.to_numpy())
print(f"\nGAP: days held {held.mean():.1%}; TQQQ log-ret on held days {lt[held].sum():+.2f}, "
      f"on idle days {lt[~held].sum():+.2f} (total {lt.sum():+.2f})")
print(f"  mean TQQQ daily ret held {np.mean(np.expm1(lt[held]))*1e4:.1f} bp vs idle {np.mean(np.expm1(lt[~held]))*1e4:.1f} bp")
up = bret.TQQQ.to_numpy() > 0.03
print(f"  big up days (>3% TQQQ): {up.sum()}, captured {(up & held).sum()} ({(up&held).sum()/up.sum():.0%})")
dn = bret.TQQQ.to_numpy() < -0.03
print(f"  big down days (<-3%): {dn.sum()}, held {(dn & held).sum()} ({(dn&held).sum()/dn.sum():.0%})")
# overnight vs intraday split on held days (entry at open so first day = intraday only)
# trade-level
ent = np.flatnonzero(np.diff(np.r_[0, held.astype(int)]) > 0)
tr = []
for e in ent:
    x = e + 3
    if x >= len(uniq): break
    px_in = o[starts[e], 1]; px_out = o[starts[x], 1]
    tr.append(px_out / px_in - 1)
tr = np.array(tr)
# unconditional 3-session open-to-open TQQQ return
oo = o[starts, 1]; unc = oo[3:] / oo[:-3] - 1
print(f"\nEVENTS: {len(tr)} trades, hit rate {np.mean(tr>0):.1%}, mean {tr.mean():.2%}, median {np.median(tr):.2%}")
print(f"  unconditional 3-session TQQQ open-open: mean {unc.mean():.2%}, hit {np.mean(unc>0):.1%}")
rng = np.random.default_rng(0)
bs = np.array([rng.choice(tr, len(tr)).mean() for _ in range(5000)])
print(f"  bootstrap P(mean trade <= unconditional mean): {(bs <= unc.mean()).mean():.3f}")
print(f"  worst 5 trades {np.sort(tr)[:5]}; best 5 {np.sort(tr)[-5:]}")
# relative reversal: next-3-day rel(QQQ-SPY) after the signal
rel = sig["rel"].to_numpy(); z = sig["z"].to_numpy()
fire = np.flatnonzero((z < S.Z_ENTRY) & np.isfinite(z))
fwd = np.array([rel[t+1:t+4].sum() for t in fire if t + 4 < len(rel)])
allf = np.array([rel[t+1:t+4].sum() for t in range(25, len(rel) - 4)])
print(f"  next-3d QQQ-SPY rel after signal {fwd.mean()*1e4:+.1f} bp (n={len(fwd)}, t={fwd.mean()/fwd.std()*np.sqrt(len(fwd)):.2f}), unconditional {allf.mean()*1e4:+.1f} bp")
# predictive regression: next 3-session TQQQ open->open (t+1 open..t+4 open) on z, HAC(3)
y = np.full(len(uniq), np.nan); y[:-4] = oo[4:] / oo[1:-3] - 1
m = np.isfinite(y) & np.isfinite(z)
X = np.c_[np.ones(m.sum()), z[m]]; Y = y[m]
b = np.linalg.lstsq(X, Y, rcond=None)[0]; e = Y - X @ b
L = 3; S0 = (X * e[:, None]).T @ (X * e[:, None])
for l in range(1, L + 1):
    G = (X[l:] * e[l:, None]).T @ (X[:-l] * e[:-l, None]); S0 += (1 - l / (L + 1)) * (G + G.T)
XtXi = np.linalg.inv(X.T @ X); V = XtXi @ S0 @ XtXi
print(f"  regression fwd3 TQQQ on z: beta {b[1]*1e4:+.1f} bp/unit, HAC t {b[1]/np.sqrt(V[1,1]):.2f}")
# signal conditioning: what is QQQ doing on signal days?
qd = bret.QQQ.to_numpy()
fd = [t for t in fire if t < len(qd)]
print(f"  QQQ return on signal days: mean {np.mean(qd[fd]):.2%}, share down {np.mean(qd[fd]<0):.0%}")
# costs
for bp in (1, 5, 10):
    print(f"COST {bp}bp: CAGR {bt.stats(r[bp], BARS)['cagr']:.2%}")
# sub-periods
for a, b_ in ((2016, 2019), (2020, 2021), (2022, 2023)):
    print(f"SUB {a}-{b_}: strat {sub_cagr(ts, r[1]['equity'], a, b_):.2%}  static {sub_cagr(ts, rs['equity'], a, b_):.2%}")
