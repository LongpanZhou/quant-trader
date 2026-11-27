"""Run the full rebuild data pipeline.

Examples
--------
Development runs + development curves + uniform website data:
    python research/revisit/run_all.py --dev --export

Holdout for the four survivors (run once, after the dev freeze):
    python research/revisit/run_all.py --holdout

The per-strategy runners remain `research/revisit/<slug>/strategy.py`.
`capture_curves.py` runs the same frozen code and saves the development
`curves/<slug>.json`. The website's uniform 2016-2026 chart uses
`curves_full/<slug>.json`, which is captured separately with
`research/capture_full.py` / `research/full_missing.py` so that the dev slice
can be matched against the frozen `result.json`.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PY = sys.executable
CAPTURE = ROOT / "research" / "capture_curves.py"
TIMINGS = HERE / "run_all_timings.json"   # last wall time per slug, for scheduling

# slug: (extra argv, extra environment)
RUNS = {
    "daily-regime-minute-entry": ([], {}),
    "donchian-breakout": (["--dev"], {}),
    "drawdown-regime": (["--run"], {}),
    "drawdown-stop-overlay": ([], {}),
    "dual-speed-regime": ([], {}),
    "dynamic-leverage-throttle": (["--authorised"], {}),
    "ensemble-signals": (["--run"], {}),
    "event-risk-overlay": ([], {}),
    "gap-capitulation-reversal": ([], {}),
    "gap-fill-fade": ([], {"REVISIT_RUN": "1"}),
    "intraday-mean-reversion": ([], {}),
    "intraday-momentum": ([], {}),
    "intraday-seasonality": ([], {}),
    "letf-rebalance-flow": ([], {}),
    "ml-classifier": ([], {}),
    "ml-crash-overlay-winner": ([], {}),
    "opening-range-breakout": ([], {}),
    "overnight-crash-filter": ([], {}),
    "ratio-pairs": ([], {}),
    "risk-parity-hrp": ([], {}),
    "stop-reentry-recovery": ([], {}),
    "time-of-day": ([], {"REVISIT_DEV_ONLY": "1"}),
    "vol-kelly-overlay": ([], {}),
    "vol-scaled-crash-stop": ([], {}),
    "volume-orderflow": (["--authorized"], {}),
    "winner-ensemble-blend": ([], {}),
}


def run(cmd: list[str], env_extra: dict[str, str], log: Path) -> int:
    env = os.environ.copy()
    env.update(env_extra)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=fh,
                              stderr=subprocess.STDOUT)
    return proc.returncode


def load_timings() -> dict[str, float]:
    try:
        return json.loads(TIMINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def run_strategies(slugs: list[str], jobs: int) -> list[str]:
    """Run each strategy in its own process, `jobs` at a time, slowest first.

    The strategies are independent, so the wall time is roughly the slowest
    one instead of the sum. Each child's engine threads are capped so the
    processes share the cores instead of oversubscribing them.
    """
    timings = load_timings()
    slugs = sorted(slugs, key=lambda s: -timings.get(s, 1e9))  # unknown first
    threads = str(max(1, (os.cpu_count() or 1) // jobs))
    failures: list[str] = []

    def one(slug: str) -> tuple[str, int, float]:
        flags, env_extra = RUNS[slug]
        env = {"BT_THREADS": threads, "PYTHONIOENCODING": "utf-8", **env_extra}
        t0 = time.perf_counter()
        code = run([PY, str(CAPTURE), slug, *flags], env, HERE / slug / "run_all.log")
        return slug, code, time.perf_counter() - t0

    t_all = time.perf_counter()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(one, s) for s in slugs]
        for done, fut in enumerate(as_completed(futures), 1):
            slug, code, secs = fut.result()
            status = "ok" if code == 0 else f"FAILED exit {code} (see {slug}/run_all.log)"
            print(f"[{done:2d}/{len(slugs)}] {slug:28s} {secs:6.1f}s  {status}", flush=True)
            if code:
                failures.append(slug)
            else:
                timings[slug] = round(secs, 1)
    TIMINGS.write_text(json.dumps(timings, indent=1, sort_keys=True), encoding="utf-8")
    print(f"strategies: {time.perf_counter() - t_all:.1f}s wall with {jobs} jobs", flush=True)
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true", help="run all 26 dev backtests")
    ap.add_argument("--curves", action="store_true",
                    help="capture the development curves in research/revisit/curves/")
    ap.add_argument("--holdout", action="store_true",
                    help="run the one-shot holdout for the four survivors")
    ap.add_argument("--export", action="store_true",
                    help="rebuild the uniform 2016-2026 website data, library and catalog")
    ap.add_argument("--only", default="", help="comma list of slugs")
    ap.add_argument("--jobs", type=int, default=max(1, min(8, (os.cpu_count() or 2) // 2)),
                    help="strategies run in parallel (default: half the cores, max 8)")
    args = ap.parse_args()

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    failures = []

    if args.dev or args.curves:
        slugs = [s for s in RUNS if not only or s in only]
        failures += run_strategies(slugs, max(1, args.jobs))

    if args.holdout:
        print("=== holdout (four survivors) ===", flush=True)
        code = run([PY, str(HERE / "run_holdout.py")], {},
                   HERE / "holdout_run.log")
        if code:
            failures.append("holdout")
            print(f"  FAILED exit {code}", flush=True)
        else:
            print("  ok", flush=True)

    if args.export:
        # The website compares every strategy on the uniform 2016-2026 window.
        # `export_compare_all.py` is the old 2017-2023 exporter and must not be
        # used here: it would overwrite the full-period All-strategies data.
        print("=== export All-strategies data (2016-2026) ===", flush=True)
        steps = [
            ("export", ROOT / "research" / "export_compare_full.py", "export_compare_full.log"),
            ("export-library", ROOT / "research" / "export_research_rebuild.py", "export_library.log"),
            ("export-detail", ROOT / "research" / "export_research_detail.py", "export_detail.log"),
            ("export-catalog", ROOT / "research" / "export_web_catalog.py", "export_catalog.log"),
        ]
        for name, script, log_name in steps:
            code = run([PY, str(script)], {}, HERE / log_name)
            if code:
                failures.append(name)
                print(f"  {name}: FAILED exit {code}", flush=True)
                break
            print(f"  {name}: ok", flush=True)

    if failures:
        print("FAILURES:", ", ".join(failures))
        return 1
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
