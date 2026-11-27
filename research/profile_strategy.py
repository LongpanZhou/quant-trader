"""Profile one rebuild strategy and print the top CPU functions.

Usage:
    python research/profile_strategy.py daily-regime-minute-entry
    python research/profile_strategy.py vol-scaled-crash-stop --top 30
"""
from __future__ import annotations

import argparse
import pstats
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("extra", nargs=argparse.REMAINDER)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    script = ROOT / "research" / "revisit" / args.slug / "strategy.py"
    if not script.exists():
        raise SystemExit(f"missing {script}")
    out = script.parent / "profile.prof"
    cmd = [sys.executable, "-m", "cProfile", "-o", str(out), str(script), *args.extra]
    print("running:", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)
    stats = pstats.Stats(str(out))
    print(f"\ntotal {stats.total_tt:.3f}s  calls {stats.total_calls:,}")
    print("\n--- cumulative ---")
    stats.sort_stats("cumtime").print_stats(args.top)
    print("\n--- internal time ---")
    stats.sort_stats("tottime").print_stats(min(args.top, 15))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
