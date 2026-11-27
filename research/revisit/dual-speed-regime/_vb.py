V = []
for nm, base in (("ON", dict(overnight=True, idle="cash", tiers=False)), ("ID", dict(idle="cash"))):
    for f in (8, 10, 12):
        for s in (24, 30, 36):
            V.append((f"{nm} fast {f} slow {s}", dict(base, fast=f, slow=s)))
    for a in (2.0, 3.0):
        V.append((f"{nm} atr {a}", dict(base, atr_k=a)))
    V.append((f"{nm} lag-1 placebo", dict(base, lag=1)))
V.append(("ID strong 0.2%", dict(idle="cash", strong=0.002)))
V.append(("ID strong 0.4%", dict(idle="cash", strong=0.004)))
