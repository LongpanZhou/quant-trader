import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
d = json.load(open(HERE / "winners_attrib.json"))
for g in ("ratio", "vol"):
    print("=====", g)
    keys = list(d[g])
    years = sorted(set().union(*[set(d[g][k]["yearly"]) for k in keys]))
    print("variant".ljust(28), " ".join(str(y).rjust(8) for y in years))
    for k in keys:
        row = []
        for y in years:
            v = d[g][k]["yearly"].get(str(y))
            row.append("     n/a" if v is None else f"{v*100:7.1f}%")
        print(k.ljust(28), " ".join(row))
