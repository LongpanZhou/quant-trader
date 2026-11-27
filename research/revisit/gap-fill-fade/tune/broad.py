"""Neighbourhood + placebo for the broadened (no weak/stress filter) gap-fill short. Dev only."""
import numpy as np
from events import *

def rep(name, **kw):
    s = summ(run(**kw))
    sub = " ".join(f"{k}:{v[0]}/{v[1]:+.1f}" for k, v in s.get("sub", {}).items())
    print(f"{name:34s} n={s['n']:4d} mean={s.get('mean_bp', 0):+6.2f}bp t={s.get('t', 0):+5.2f} win={s.get('win', 0):.2f} p={s.get('p', 1):.3f} | {sub}")
    return s
B = dict(weak_on=False, stress=None)
for ghi in (0.0075, 0.009, 0.012, 0.015, 0.02, 0.03):
    rep(f"broad gap 0.1-{ghi*100:.2f}%", gap_hi=ghi, **B)
for glo in (0.0005, 0.0015, 0.0025):
    rep(f"broad gap {glo*100:.2f}-1.5%", gap_lo=glo, gap_hi=0.015, **B)
for ts_ in (660, 720):
    rep(f"broad 1.5% tstop {ts_}", gap_hi=0.015, tstop=ts_, **B)
for fl, cp in ((0.001, 0.01), (0.003, 0.02)):
    rep(f"broad 1.5% stop {fl}/{cp}", gap_hi=0.015, floor=fl, cap=cp, **B)
rep("broad 1.5% confirm<-0.1%", gap_hi=0.015, confirm=-0.001, **B)
rep("broad 1.5% no confirm", gap_hi=0.015, conf_on=False, **B)
rep("broad 1.5% at 2bp", gap_hi=0.015, slip=2, **B)
rep("broad 1.5% at 3bp", gap_hi=0.015, slip=3, **B)
rep("broad 1.5% at 5bp", gap_hi=0.015, slip=5, **B)
rep("broad 1.5% at 10bp", gap_hi=0.015, slip=10, **B)
rep("broad 1.5% weak on", gap_hi=0.015, weak_on=True, stress=None)
rep("broad 1.5% stress on", gap_hi=0.015, weak_on=False, stress=1.0)

# placebo: same exits, on random non-signal sessions (gap-ups +0.1..1.5% replaced by any session with c10>prior)
ev = run(gap_hi=0.015, **B)
ks = set(e[0] for e in ev)
# control: short at 10:01 on every session where QQQ 10:00 close is above prior close and r30<0, any gap (incl. negative)
rep("control: any gap, c10>pc & r30<0", gap_lo=-1, gap_hi=1, **B)
rep("control: gap down only", gap_lo=-1, gap_hi=-0.001, **B)
