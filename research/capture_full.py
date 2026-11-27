"""Capture full 2016-2026 equity curves for a rebuild.

Runs the strategy's own main() with its development end date temporarily
extended to the full archive end, then matches the development slice of each
captured run to the frozen dev result and saves the full daily curve.

Freeze selection:
  default       use the current <slug>/result.json and strategy.py
  --freeze-pre  use <slug>/_before_tune/{strategy.py,result.json}, i.e. the
                pre-registered curve, instead of the post-tune variant
  --force       allow overwriting an existing curve whose dev freeze differs
                from the selected result by more than 2 pp
"""
from __future__ import annotations

import json
import hashlib
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
import bt  # noqa: E402

DEV_END = "2023-12-29"
FULL_END = "2026-10-23"
slug = sys.argv[1]
flags = sys.argv[2:]
force = "--force" in flags
freeze_pre = "--freeze-pre" in flags
flags = [f for f in flags if f not in ("--force", "--freeze-pre")]
base = ROOT / "research" / "revisit" / slug
path = base / "strategy.py"
backup = base / "result.json"
tmp = base / "__full_tmp.py"
out = ROOT / "research" / "revisit" / "curves_full" / f"{slug}.json"
out.parent.mkdir(parents=True, exist_ok=True)

stored_path = (base / "_before_tune" / "result.json") if freeze_pre else backup
stored = json.loads(stored_path.read_text())["windows"]["dev"]["1bp"]
backup_dev = base / "result_dev_backup.json"
backup_dev.write_bytes(backup.read_bytes())
source_path = path
if freeze_pre:
    pre_source = base / "_before_tune" / "strategy.py"
    if pre_source.exists():
        source_path = pre_source
    else:
        print(f"WARN {slug}: no _before_tune/strategy.py; using current source")
source_bytes = source_path.read_bytes()
source_sha = hashlib.sha256(source_bytes).hexdigest()
result_sha = hashlib.sha256(stored_path.read_bytes()).hexdigest()
source = source_bytes.decode("utf-8")
# Normalise mixed / lone-CR line endings before writing the temporary source.
# A file edited by different tools can contain \r\n, \n and lone \r; Python's
# tokenizer then reports line numbers and indentation that do not match the
# editor, which is what produced the spurious "__full_tmp.py line 587".
source = source.replace("\r\n", "\n").replace("\r", "\n")

# Refuse to silently replace a curve that belongs to a different freeze.  The
# 8 pre-tune curves must not be overwritten by the current post-tune result
# unless the caller explicitly asks for it.
if out.exists() and not force:
    try:
        prev = json.loads(out.read_text(encoding="utf-8"))
        prev_dev = prev.get("dev_result") or {}
        if "cagr" not in prev_dev:
            s = pd.Series(prev["values"], index=pd.to_datetime(prev["dates"]))
            s = s[s.index <= pd.Timestamp(DEV_END)]
            years = (s.index[-1] - s.index[0]).days / 365.25
            prev_dev = {"cagr": float((s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1)}
        if abs(prev_dev.get("cagr", stored["cagr"]) - stored["cagr"]) > 0.02:
            print(f"REFUSE {slug}: existing curve dev {prev_dev['cagr']:.2%} != "
                  f"stored {stored['cagr']:.2%}; use --force to adopt the current "
                  f"result or --freeze-pre to regenerate the pre-tune freeze.")
            raise SystemExit(3)
    except (OSError, ValueError, KeyError):
        pass

# Some strategies use more than one development-end literal: an exclusive end
# (2023-12-30) and/or a monthly-refit schedule (2023-12-01).  Replacing only
# the main end date silently freezes a model or truncates the curve, so map
# all three forms used by the rebuilds.
FULL_DATES = {
    '"2023-12-29"': '"2026-10-23"',
    '"2023-12-30"': '"2026-10-24"',
    '"2023-12-01"': '"2026-10-01"',
    "'2023-12-29'": "'2026-10-23'",
    "'2023-12-30'": "'2026-10-24'",
    "'2023-12-01'": "'2026-10-01'",
}
for old, new in FULL_DATES.items():
    source = source.replace(old, new)
tmp.write_text(source, encoding="utf-8")

# A cached development panel can silently pin a full-period run to 2016-2023
# (the `vol-scaled-crash-stop` result bug).  Caches are regenerable, so drop
# the known panel caches before the temporary strategy runs.
for cache_name in ("dev_panel.npz", "panel_cache.npz"):
    (base / cache_name).unlink(missing_ok=True)
for cache in base.glob("*_panel_cache.npz"):
    cache.unlink(missing_ok=True)

captured = []
orig_run, orig_sim, orig_many = bt.run, bt.simulate, bt.run_many


def run(*a, **k):
    r = orig_run(*a, **k)
    captured.append(r)
    return r


def sim(*a, **k):
    r = orig_sim(*a, **k)
    captured.append(r)
    return r


def many(*a, **k):
    rs = orig_many(*a, **k)
    captured.extend(rs)
    return rs


bt.run, bt.simulate, bt.run_many = run, sim, many
sys.argv = [str(tmp)] + flags
try:
    runpy.run_path(str(tmp), run_name="__main__")
except SystemExit as e:
    print("SystemExit", e)
except Exception as e:
    print("main error", type(e).__name__, e)
finally:
    # restore the frozen development result
    if backup_dev.exists():
        backup_dev.replace(backup)
    tmp.unlink(missing_ok=True)

# Include the whole DEV_END session: a bare timestamp at 00:00 excludes the
# final 09:30-15:59 bars and makes strategies that measure through the close
# fail the dev-slice match.
cut = pd.Timestamp(DEV_END, tz="America/New_York") + pd.Timedelta(days=1)
match = None
for r in captured:
    try:
        ts = pd.DatetimeIndex(r["ts"])
        mask = ts <= cut
        if mask.sum() < 100:
            continue
        rr = {k: (np.asarray(v)[mask] if isinstance(v, (list, np.ndarray)) else v)
              for k, v in r.items()}
        rr["ts"] = ts[mask]
        s = bt.stats(rr, 252 * 390)
    except Exception:
        continue
    if (abs(s["cagr"] - stored["cagr"]) < 5e-4
            and abs(s["max_drawdown"] - stored["max_drawdown"]) < 5e-4):
        match = r
        break

if match is None:
    print("NO MATCH", slug, "captured", len(captured))
    raise SystemExit(2)

eq = pd.Series(match["equity"], index=pd.DatetimeIndex(match["ts"]))
daily = eq.groupby(eq.index.date).last()
daily.index = pd.to_datetime(daily.index)
daily = daily / daily.iloc[0] * 100.0


def daily_stats(daily: pd.Series, start: str) -> dict:
    """Daily-close metrics; the chart uses the same marks, not 1-minute bars."""
    s = daily[daily.index >= pd.Timestamp(start)]
    eq = s.to_numpy(dtype=float)
    years = (s.index[-1] - s.index[0]).days / 365.25
    peak = np.maximum.accumulate(eq)
    rets = np.diff(eq) / eq[:-1]
    return {
        "cagr": float((eq[-1] / eq[0]) ** (1 / years) - 1) if years > 0 else 0.0,
        "max_drawdown": float(-(eq / peak - 1).min()),
        "sharpe": float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() else 0.0,
        "start": str(s.index[0].date()),
        "end": str(s.index[-1].date()),
        "days": int(len(s)),
        "marks": "daily_close",
    }


out.write_text(json.dumps({
    "slug": slug,
    "source_sha256": source_sha,
    "result_sha256": result_sha,
    "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
    "dev_end": DEV_END,
    "full_end": FULL_END,
    "dates": [str(d.date()) for d in daily.index],
    "values": [float(v) for v in daily.to_numpy()],
    "metrics": {
        "full": daily_stats(daily, "2016-01-04"),
        "10y": daily_stats(daily, "2017-01-03"),
        "5y": daily_stats(daily, "2021-10-25"),
    },
    "dev_result": stored,
}), encoding="utf-8")
print("WROTE", out, len(daily), "days", daily.index[0], daily.index[-1],
      "last", round(float(daily.iloc[-1]), 1))
