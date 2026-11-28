"""Step 1: spec vs code checks (dev only)."""
from common import *

ts, o, c = load()
sig = S.load_daily_signal()
uniq, sess, starts, ends = sessions(ts)
dates = pd.DatetimeIndex(sig.index)
dev_daily = dates[(dates >= DEV0) & (dates <= DEV1)]
print("1m sessions", len(uniq), "daily dev dates", len(dev_daily))
print("1m sessions missing from daily:", list(uniq.difference(dates))[:10])
print("daily dev dates missing from 1m:", list(dev_daily.difference(uniq))[:10])
# bars per session
nb = ends - starts
print("sessions with !=390 bars:", int((nb != 390).sum()), " (<390:", int((nb < 390).sum()), ")")
print("half-days (210 bars):", int((nb == 210).sum()))
# session last-bar time
last_t = pd.DatetimeIndex(ts[ends - 1]).strftime("%H:%M")
print("last-bar times:", pd.Series(last_t).value_counts().to_dict())

# cross-check the yahoo QQQ daily return vs the 1m QQQ close-to-close
q1 = pd.Series(c[ends - 1, 0], index=uniq)
qd = sig["qqq"].reindex(uniq)
r1 = q1.pct_change(); rd = qd.pct_change()
diff = (r1 - rd).abs()
print("QQQ daily ret 1m vs yahoo: median abs diff %.2e, >10bp: %d" % (diff.median(), (diff > 1e-3).sum()))

w, info = S.build_weights(ts, o, c)
wd = info["w_daily"]
z = info["z"]
in_dev = (dates >= DEV0) & (dates <= DEV1)
fire = (z < S.Z_ENTRY) & np.isfinite(z)
print("signals total (whole file)", info["n_signals"], " in dev:", int((fire & in_dev).sum()))
# entries = transitions BIL->TQQQ in daily targets within dev
dv = wd[in_dev, 1]
ent = np.flatnonzero(np.diff(np.r_[0, dv]) > 0)
print("entries in dev", len(ent))
# run lengths (sessions held = target days set to TQQQ)
runs = []
k = 0
for x in dv:
    if x > 0: k += 1
    elif k: runs.append(k); k = 0
print("target-run lengths:", pd.Series(runs).value_counts().to_dict())
# signals ignored while holding / on exit day
held_sig = 0
for t in np.flatnonzero(fire & in_dev):
    if wd[t, 1] == 1 and t > 0 and wd[t - 1, 1] == 1:
        held_sig += 1
print("signals ignored because a position was open:", held_sig)
exit_day_sig = int(sum(1 for t in np.flatnonzero(fire & in_dev) if wd[t, 1] == 0))
print("signals on an exit day (target BIL although z fired):", exit_day_sig)
# minute weights sanity
print("weights finite", np.isfinite(w).all(), "min", w.min(), "rowsum max", w.sum(1).max())
# check fill timing: minute weight changes only at last bar of a session
chg = np.flatnonzero(np.any(np.diff(w, axis=0) != 0, axis=1))  # change between i and i+1 -> set at i+1
is_last = np.zeros(len(ts), bool); is_last[ends - 1] = True
print("weight changes not on a session's last bar:", int((~is_last[chg + 1]).sum()))
# z uses rolling std through t-1 (no inclusion)
r = sig["rel"]; t0 = 100
manual = r.iloc[t0] / r.iloc[t0 - 20:t0].std()
print("z manual vs code", manual, sig["z"].iloc[t0])
# exposure
i = bt.start_index(ts, DEV0)
print("fraction of minutes TQQQ target:", w[i:, 1].mean(), " BIL:", w[i:, 2].mean())
