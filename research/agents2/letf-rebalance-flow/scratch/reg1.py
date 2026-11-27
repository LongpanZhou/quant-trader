"""Overnight reversal regressions and late-day vs day-move decomposition."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
df = pd.read_pickle(HERE / "daily2.pkl")

def ols_hac(y, X, lags=5):
    X = np.column_stack([np.ones(len(X)), X])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ beta
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    S = np.zeros((k, k))
    for l in range(lags + 1):
        w = 1.0 - l / (lags + 1)
        for t in range(l, n):
            u = np.outer(X[t] * e[t], X[t - l] * e[t - l])
            S += w * u
    # HAC (Newey-West) with t>=l only; symmetric handled by loop
    V = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.diag(V))
    return beta, beta / se, len(y)

df = df.dropna(subset=["on_next", "run", "late60"]).copy()
df["late60"] = df["late60"].fillna(0)
df["off"] = (~df["risk_on"]).astype(float)

print("Overnight return regressions (TQQQ, bp), HAC(5)")
for label, cols in [
    ("all: run", ["run"]),
    ("all: run + late60", ["run", "late60"]),
    ("all: run + late60 + off", ["run", "late60", "off"]),
    ("all: run + late60 + off + off*run + off*late60",
     ["run", "late60", "off", "offrun", "offlate"]),
]:
    d = df.copy()
    d["offrun"] = d["off"] * d["run"]
    d["offlate"] = d["off"] * d["late60"]
    y = d["on_next"].to_numpy() * 1e4
    X = d[cols].to_numpy()
    beta, t, n = ols_hac(y, X)
    terms = ", ".join(f"{c}={b:7.2f} (t={tt:5.2f})" for c, b, tt in zip(["const"] + cols, beta, t))
    print(f"  {label:55s} n={n} {terms}")

print("\nSame, but overnight measured 16:00->next 09:30 open; late60 is 15:00->15:58:59")
print("Subsamples:")
for lo, hi, tag in [("2017-01-03", "2019-12-31", "2017-19"),
                    ("2020-01-01", "2022-12-31", "2020-22"),
                    ("2023-01-01", "2026-10-23", "2023-26")]:
    d = df[(df.date >= pd.Timestamp(lo, tz="America/New_York")) & (df.date <= pd.Timestamp(hi, tz="America/New_York"))].copy()
    d["offrun"] = d["off"] * d["run"]
    d["offlate"] = d["off"] * d["late60"]
    y = d["on_next"].to_numpy() * 1e4
    X = d[["run", "late60", "off", "offrun", "offlate"]].to_numpy()
    beta, t, n = ols_hac(y, X)
    print(f"  {tag} n={n:4d} const={beta[0]:7.2f} run={beta[1]:7.2f}(t={t[1]:5.2f}) late={beta[2]:7.2f}(t={t[2]:5.2f}) "
          f"off={beta[3]:7.2f} offrun={beta[4]:7.2f}(t={t[4]:5.2f}) offlate={beta[5]:7.2f}(t={t[5]:5.2f})")

print("\nOvernight mean by regime x run60 x late60 sign (TQQQ bp)")
df["rsign"] = np.sign(df["run"])
df["lsign"] = np.sign(df["late60"].fillna(0))
for off in [0, 1]:
    for rs in [1, -1]:
        for ls in [1, -1]:
            m = (df["off"] == off) & (df["rsign"] == rs) & (df["lsign"] == ls)
            r = df.loc[m, "on_next"]
            print(f"  off={off} run{rs:+d} late{ls:+d} n={len(r):4d} on {r.mean()*1e4:8.2f}bp hit {(r>0).mean():.2f}")

print("\nIntraday late60 mean by regime x run bucket x late60 sign (TQQQ bp)")
for off in [0, 1]:
    sub = df[df["off"] == off]
    b = pd.cut(sub["run"]*100, [-99, -2, -1, 0, 1, 2, 3, 99])
    for lab, g in sub.groupby(b, observed=True):
        r = g["late60"]
        print(f"  off={off} run {str(lab):11s} n={len(g):4d} late60 {r.mean()*1e4:8.2f}bp med {r.median()*1e4:8.2f}")
