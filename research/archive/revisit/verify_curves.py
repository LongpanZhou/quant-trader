"""Verify captured daily curves against each strategy's dev result.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
HERE = ROOT / "research" / "revisit"
CURVES = HERE / "curves"


def main():
    rows = []
    for path in sorted(CURVES.glob("*.json")):
        slug = path.stem
        curve = json.loads(path.read_text())
        result = json.loads((HERE / slug / "result.json").read_text())
        stored = result["windows"]["dev"]["1bp"]
        dates, values = curve["dates"], curve["values"]
        ok = (len(dates) == len(values) and len(dates) > 100
              and dates == sorted(dates) and all(isinstance(v, (int, float)) for v in values))
        years = (int(dates[-1][:4]) - int(dates[0][:4])) + (
            (int(dates[-1][5:7]) - int(dates[0][5:7])) / 12.0
        )
        cagr = (values[-1] / values[0]) ** (1 / years) - 1 if years > 0 else float("nan")
        peak, mdd = values[0], 0.0
        for v in values:
            peak = max(peak, v)
            mdd = max(mdd, 1 - v / peak)
        rows.append((slug, ok, cagr, stored["cagr"], mdd, stored["max_drawdown"],
                     dates[0], dates[-1]))
    print(f"{'slug':30s} ok  curveCAGR  resultCAGR  dCAGR   curveDD  resultDD  dDD")
    for slug, ok, cagr, rcagr, mdd, rdd, d0, d1 in rows:
        print(f"{slug:30s} {str(ok):4s} {cagr*100:8.2f}% {rcagr*100:9.2f}% "
              f"{(cagr-rcagr)*100:6.2f}pp {mdd*100:7.2f}% {rdd*100:8.2f}% "
              f"{(mdd-rdd)*100:6.2f}pp  {d0}..{d1}")
    print(f"\n{len(rows)} curve files")


if __name__ == "__main__":
    main()
