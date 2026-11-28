"""Health audit for all strategies in LIBRARY.json, excluding the eight repairs."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
NEW = ROOT / "research" / "new"
REV = ROOT / "research" / "revisit"
LIB = json.loads((NEW / "LIBRARY.json").read_text(encoding="utf-8"))
ALL = json.loads((ROOT / "web" / "public" / "data" / "compare" / "all.json").read_text(encoding="utf-8"))
ALL_METRICS = {m["id"]: m for m in ALL["metrics"]}
REPAIRS = {
    "dynamic-leverage-throttle", "vol-kelly-overlay", "drawdown-regime",
    "gap-capitulation-reversal", "drawdown-stop-overlay", "gap-fill-fade",
    "stop-reentry-recovery", "volume-orderflow",
}


def dev_block(d: dict):
    for c in [
        ((d.get("windows") or {}).get("dev") or {}).get("1bp"),
        (d.get("dev") or {}).get("1bp"),
        (d.get("primary") or {}).get("1bp") if isinstance(d.get("primary"), dict) else None,
        (d.get("primary") or {}).get("dev", {}).get("1bp") if isinstance(d.get("primary"), dict) else None,
        d.get("dev_1bp"),
    ]:
        if isinstance(c, dict) and "cagr" in c:
            return c
    return {}


def full_block(h: dict):
    return ((h.get("windows") or {}).get("full") or {}).get("daily") or {}


def actual_exposure(*objs):
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        for key in ("info", "diagnostics", "params"):
            sub = obj.get(key)
            if isinstance(sub, dict):
                for k in ("exposure", "tqqq_exposure", "avg_tqqq_weight", "mean_weight"):
                    v = sub.get(k)
                    if isinstance(v, (int, float)) and 0 < v < 0.99:
                        return float(v)
        for k in ("exposure", "tqqq_exposure", "avg_tqqq_weight", "mean_weight"):
            v = obj.get(k)
            if isinstance(v, (int, float)) and 0 < v < 0.99:
                return float(v)
    return None


def curve_stats(slug: str):
    paths = [REV / "curves_full" / f"{slug}.json", NEW / "curves" / f"{slug}.json"]
    p = next((x for x in paths if x.exists()), None)
    if p is None:
        return {}, None
    d = json.loads(p.read_text(encoding="utf-8"))
    vals = np.asarray(d.get("values", []), dtype=float)
    dates = pd.to_datetime(d.get("dates", []))
    if len(vals) < 10 or len(vals) != len(dates):
        return {"curve": "bad"}, p
    rets = np.diff(vals) / vals[:-1]
    vol = float(np.std(rets) * math.sqrt(252))
    peak = np.maximum.accumulate(vals)
    dd = float(-(vals / peak - 1).min())
    return {"curve": "ok", "vol": vol, "dd": dd, "n": len(vals)}, p


rows = []
for rec in LIB["strategies"]:
    slug = rec["slug"]
    if slug in REPAIRS:
        continue
    source = rec.get("source", "")
    is_new = source.startswith("research/new/")
    if slug in ("ratio-froth", "vol-scaled-crash-stop"):
        base = NEW / slug
    elif is_new:
        base = NEW / slug
    else:
        base = REV / slug
    rp = base / "result.json"
    hp = NEW / slug / "holdout.json"
    d = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {}
    h = json.loads(hp.read_text(encoding="utf-8")) if hp.exists() else {}
    dev = dev_block(d)
    full = full_block(h) or rec.get("full") or {}
    exposure = actual_exposure(d, h)
    cs, curve_path = curve_stats(slug)
    fills = dev.get("fills")
    if fills is None:
        fills = ((h.get("windows") or {}).get("dev") or {}).get("1bp", {}).get("fills")
    cagr = dev.get("cagr")
    dd = dev.get("max_drawdown", dev.get("dd"))
    sharpe = dev.get("sharpe")
    flags = []
    if not rp.exists() and not full:
        flags.append("no-result")
    if is_new and not hp.exists() and not full:
        flags.append("no-holdout")
    if not (base / "strategy.py").exists():
        flags.append("no-code")
    if not (base / "report.md").exists():
        flags.append("no-report")
    if fills is not None and fills < 10:
        flags.append("dead-fills")
    elif fills is not None and fills < 30:
        flags.append("low-fills")
    if cagr is not None and cagr <= 0:
        flags.append("negative-edge")
    if sharpe is not None and sharpe < 0.3:
        flags.append("weak-sharpe")
    if exposure is not None and exposure < 0.05:
        flags.append("tiny-exposure")
    if cs.get("curve") == "bad":
        flags.append("bad-curve")
    if cs.get("curve") == "ok" and cs["vol"] < 0.05:
        flags.append("tiny-vol")
    if not full:
        flags.append("no-full")
    rows.append({
        "slug": slug, "family": rec.get("family"), "source": source,
        "dev_cagr": cagr, "dev_dd": dd, "dev_sharpe": sharpe,
        "fills": fills, "exposure": exposure,
        "full_cagr": full.get("cagr") if isinstance(full, dict) else None,
        "curve_vol": cs.get("vol"), "curve_n": cs.get("n"),
        "flags": flags,
    })

rows.sort(key=lambda r: (len(r["flags"]) == 0, r["fills"] if r["fills"] is not None else 999))
(NEW / "HEALTH_AUDIT.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

lines = ["# Portfolio health audit", "",
         "All library strategies except the eight under repair. Flags are diagnostics, not verdicts.", "",
         "| slug | family | dev CAGR | dev DD | Sharpe | fills | actual exposure | curve vol | flags |",
         "|---|---|---:|---:|---:|---:|---:|---:|---|"]
for r in rows:
    def f(x, pct=False):
        if x is None: return "—"
        return f"{x*100:.2f}%" if pct else f"{x:.2f}"
    lines.append(
        f"| `{r['slug']}` | {r['family']} | {f(r['dev_cagr'], True)} | {f(r['dev_dd'], True)} | "
        f"{f(r['dev_sharpe'])} | {r['fills'] if r['fills'] is not None else '—'} | "
        f"{f(r['exposure'], True)} | {f(r['curve_vol'], True)} | {', '.join(r['flags']) or 'ok'} |")
(NEW / "HEALTH_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

flagged = [r for r in rows if r["flags"]]
print(f"audited {len(rows)}, flagged {len(flagged)}, clean {len(rows)-len(flagged)}")
for r in flagged:
    print(f"{r['slug']:34s} fills={r['fills']} expo={r['exposure']} cagr={r['dev_cagr']} flags={r['flags']}")
