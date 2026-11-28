"""Build the lab parameter schema from the actual Python strategy modules."""
from __future__ import annotations

import dataclasses
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
import web_runner as W  # noqa: E402

REBUILD = ROOT / "web/public/data/research/rebuild.json"
OUT = ROOT / "web/public/data/research/params.json"
SPECIAL = {"ratio-pairs", "time-of-day"}


def humanize(key: str) -> str:
    return key.replace("_", " ").strip().capitalize()


def field_type(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "text"
    return "text"


def scalar(value):
    return value if isinstance(value, (bool, int, float, str)) else None


def fields_from_params(d: dict, editable: bool) -> list[dict]:
    out = []
    for key, value in d.items():
        v = scalar(value)
        if v is None:
            continue
        out.append({"key": key, "label": humanize(key), "type": field_type(v),
                    "default": v, "editable": editable})
    return out


def fields_from_dataclass(cls, editable: bool) -> list[dict]:
    out = []
    for f in dataclasses.fields(cls):
        if f.default is not dataclasses.MISSING:
            value = f.default
        elif f.default_factory is not dataclasses.MISSING:  # type: ignore[comparison-overlap]
            try:
                value = f.default_factory()
            except Exception:
                continue
        else:
            continue
        v = scalar(value)
        if v is None:
            continue
        out.append({"key": f.name, "label": humanize(f.name), "type": field_type(v),
                    "default": v, "editable": editable})
    return out


def editable_keys(mod) -> set[str]:
    try:
        sig = inspect.signature(mod.build_weights)
    except Exception:
        return set()
    return set(sig.parameters)


def main() -> None:
    rows = json.loads(REBUILD.read_text(encoding="utf-8"))["strategies"]
    out = {}
    for row in rows:
        slug = row["slug"]
        try:
            mod = W.load(slug)
        except Exception as exc:
            print("SKIP", slug, type(exc).__name__, str(exc)[:80])
            out[slug] = {"fields": []}
            continue
        keys = editable_keys(mod)
        fields = []
        if isinstance(getattr(mod, "PARAMS", None), dict):
            fields = fields_from_params(mod.PARAMS, "params" in keys)
        elif hasattr(mod, "Params") and dataclasses.is_dataclass(mod.Params):
            fields = fields_from_dataclass(mod.Params, slug in SPECIAL)
        if not fields:
            p = ROOT / "research" / "strategies" / slug / "result.json"
            if p.exists():
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    params = d.get("params")
                    if isinstance(params, dict):
                        fields = fields_from_params(params, False)
                except Exception:
                    pass
        # allow direct keyword parameters (e.g. fomc_off, hold, clv_thr)
        for f in fields:
            if f["key"] in keys and f["key"] != "params":
                f["editable"] = True
        out[slug] = {"fields": fields}
        print(f"{slug:38s} fields={len(fields):2d} editable={sum(1 for f in fields if f['editable'])}")
    OUT.write_text(json.dumps({"strategies": out}, indent=1), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
