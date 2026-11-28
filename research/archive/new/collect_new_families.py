"""Read-only inventory of the new-family candidates."""
from __future__ import annotations

import json
from pathlib import Path

NEW = Path(__file__).resolve().parent

SKIP = {
    "family-session-timing", "family-short-reversal", "family-rebalance-flow",
    "family-intraday-microstructure-day", "family-ml-microstructure",
}


def load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def find_metric(obj, path=""):
    """Return the first dict with cagr/max_drawdown/sharpe and its path."""
    if isinstance(obj, dict):
        if all(k in obj for k in ("cagr", "max_drawdown", "sharpe")):
            return obj, path
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and path.count(".") < 5:
                got = find_metric(v, f"{path}.{k}" if path else k)
                if got:
                    return got
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, (dict, list)):
                got = find_metric(v, f"{path}[{i}]")
                if got:
                    return got
    return None


def main() -> None:
    rows = []
    for d in sorted(NEW.iterdir()):
        if not d.is_dir() or not d.name.startswith("family-") or d.name in SKIP:
            continue
        r = load(d / "result.json")
        h = load(d / "holdout.json")
        dev = None
        for candidate in (
            (((r.get("windows") or {}).get("dev") or {}).get("1bp")),
            ((r.get("dev") or {}).get("1bp")),
            r.get("dev"),
        ):
            if isinstance(candidate, dict) and "cagr" in candidate:
                dev = candidate
                break
        if dev is None:
            found = find_metric(r)
            dev = found[0] if found else None
        full = (((h.get("windows") or {}).get("full") or {}).get("daily")
                or ((h.get("windows") or {}).get("full") or {}).get("1bp")
                or {})
        rows.append({
            "slug": d.name,
            "files": all((d / f).exists() for f in ("HYPOTHESIS.md", "strategy.py", "result.json", "report.md")),
            "dev": dev or {},
            "full": full,
            "fills": (dev or {}).get("fills"),
            "full_fills": full.get("fills"),
        })

    print(f"{'slug':36s} {'files':5s} {'devCAGR':>8s} {'devDD':>7s} {'devSh':>6s} {'fills':>7s} {'fullCAGR':>8s} {'fullDD':>7s} {'fullF':>7s}")
    for x in rows:
        d, f = x["dev"], x["full"]
        def p(v):
            return "—" if v is None else f"{v*100:7.2f}%"
        def s(v):
            return "—" if v is None else f"{v:6.2f}"
        def n(v):
            return "—" if v is None else f"{v:7.0f}"
        print(f"{x['slug']:36s} {str(x['files']):5s} {p(d.get('cagr'))} {p(d.get('max_drawdown'))} "
              f"{s(d.get('sharpe'))} {n(x['fills'])} {p(f.get('cagr'))} {p(f.get('max_drawdown'))} {n(x['full_fills'])}")


if __name__ == "__main__":
    main()
