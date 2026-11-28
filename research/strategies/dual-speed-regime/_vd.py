V = []
base = dict(overnight=True, idle="cash", tiers=True)
for f in (8, 10, 12):
    for s in (24, 30, 36):
        if (f, s) != (10, 30): V.append((f"ONT fast {f} slow {s}", dict(base, fast=f, slow=s)))
for a in (2.0, 3.0): V.append((f"ONT atr {a}", dict(base, atr_k=a)))
for st in (0.002, 0.004): V.append((f"ONT strong {st*100:.1f}%", dict(base, strong=st)))
V.append(("ONT lag-1 placebo", dict(base, lag=1)))
V.append(("ONT lag-6 placebo (one session)", dict(base, lag=6)))
