"""Check every holdout.json for fill/turnover partition and curve provenance.

Run after `run_holdout.py` has refreshed a strategy.  It does not load market
data and does not change any file.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np

NEW = Path(__file__).resolve().parent
CURVES = NEW / "curves"


def curve_stats(payload: dict) -> dict:
    vals = np.asarray(payload["values"], dtype=float)
    dates = payload["dates"]
    years = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 365.25
    peak = np.maximum.accumulate(vals)
    rets = np.diff(vals) / vals[:-1]
    return {
        "cagr": float((vals[-1] / vals[0]) ** (1 / years) - 1) if years > 0 else 0.0,
        "dd": float(-(vals / peak - 1).min()),
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() else 0.0,
    }


def main() -> None:
    errors: list[str] = []
    checked = 0
    for path in sorted(NEW.glob("*/holdout.json")):
        slug = path.parent.name
        d = json.loads(path.read_text(encoding="utf-8"))
        w = d.get("windows") or {}
        if not all(k in w for k in ("dev", "holdout", "full")):
            errors.append(f"{slug}: missing dev/holdout/full")
            continue
        try:
            dev = w["dev"]["1bp"]
            hold = w["holdout"]["1bp"]
            full = w["full"]["1bp"]
        except KeyError as exc:
            errors.append(f"{slug}: missing 1bp block {exc}")
            continue

        for name, block in (("dev", dev), ("holdout", hold), ("full", full)):
            eq = block.get("turnover_start_equity")
            notional = block.get("traded_notional")
            turnover = block.get("turnover")
            if not eq or notional is None or turnover is None:
                errors.append(f"{slug}: {name} lacks turnover denominator fields")
            elif abs(turnover - notional / eq) > 1e-10:
                errors.append(f"{slug}: {name} turnover != notional/start_equity")

        if full.get("fills") != dev.get("fills", 0) + hold.get("fills", 0):
            errors.append(
                f"{slug}: full fills {full.get('fills')} != "
                f"dev {dev.get('fills')} + holdout {hold.get('fills')}"
            )
        parted = dev.get("traded_notional", 0.0) + hold.get("traded_notional", 0.0)
        if abs(full.get("traded_notional", 0.0) - parted) > max(1e-3, 1e-9 * abs(parted)):
            errors.append(
                f"{slug}: full notional {full.get('traded_notional')} != "
                f"dev+holdout {parted}"
            )

        curve_path = CURVES / f"{slug}.json"
        if not curve_path.exists():
            errors.append(f"{slug}: missing curve {curve_path.name}")
        else:
            payload = json.loads(curve_path.read_text(encoding="utf-8"))
            if payload.get("dates") != d["daily_curve"]["dates"]:
                errors.append(f"{slug}: curve dates differ from holdout daily_curve")
            elif not np.allclose(payload.get("values"), d["daily_curve"]["values"],
                                 rtol=0.0, atol=1e-9):
                errors.append(f"{slug}: curve values differ from holdout daily_curve")
            else:
                cs = curve_stats(payload)
                fd = w["full"]["daily"]
                for field in ("cagr", "dd", "sharpe"):
                    stored = fd.get("max_drawdown") if field == "dd" else fd.get(field)
                    if stored is None or abs(cs[field] - stored) > 1e-8:
                        errors.append(f"{slug}: curve {field} != full daily metric")
        checked += 1

    print(f"checked {checked} holdout files")
    if errors:
        print("ERRORS")
        for err in errors:
            print(" -", err)
        raise SystemExit(1)
    print("OK: every holdout partitions cleanly and matches its curve")


if __name__ == "__main__":
    main()
