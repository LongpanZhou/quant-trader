import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
payload = json.loads((ROOT / "web/public/data/compare/all.json").read_text())
dates = pd.to_datetime(payload["dates"])
frame = pd.DataFrame(
    {series["id"]: series["values"] for series in payload["series"]},
    index=dates,
).ffill().dropna()
returns = frame.pct_change().dropna()

corr = returns.corr()
ids = list(corr.columns)
pairs = [(ids[i], ids[j], corr.iloc[i, j]) for i in range(len(ids)) for j in range(i + 1, len(ids))]
values = np.array([p[2] for p in pairs])
print(f"strategies: {len(ids)}  daily observations: {len(returns)}")
print(f"average pairwise daily-return correlation: {values.mean():.3f}")
print(f"minimum / maximum: {values.min():.3f} / {values.max():.3f}")
print("\nclosest pairs:")
for a, b, c in sorted(pairs, key=lambda x: -x[2])[:8]:
    print(f"  {a:14s} {b:14s} {c:.3f}")
print("\nleast similar pairs:")
for a, b, c in sorted(pairs, key=lambda x: x[2])[:8]:
    print(f"  {a:14s} {b:14s} {c:.3f}")

print("\ncorrelation with round-1 winner a1:")
for key in ids:
    if key != "a1":
        print(f"  {key:14s} {corr.loc[key, 'a1']:.3f}")

print("\nannualized tracking error vs a1:")
for key in ids:
    if key != "a1":
        diff = returns[key] - returns["a1"]
        print(f"  {key:14s} {diff.std() * np.sqrt(252):.3f}")

base = ["tqqq", "a1", "a4", "a8", "a17", "a21", "a23"]
base = [x for x in base if x in returns.columns]
bcorr = returns[base].corr().values
bpairs = bcorr[np.triu_indices(len(base), 1)]
print(f"\nbase strategies (no blends): {len(base)}")
print(f"  average pairwise correlation: {bpairs.mean():.3f}")
for label, cols in (("all 10", ids), ("base 7", base)):
    c = returns[cols].corr().values
    eig = np.linalg.eigvalsh(c)
    print(f"  {label}: first principal component explains {eig[-1]/eig.sum()*100:.1f}% of variance")

