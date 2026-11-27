"""Delete generated caches, profiles and ad-hoc run logs only.

Never deletes research results, curves, reports, data, source or web assets.
"""
from pathlib import Path
import shutil

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
SKIP = {".git", "node_modules", ".next", "data"}

CACHE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SUFFIXES = {".pyc", ".prof"}
TEMP_NAMES = {
    "__full_tmp.py",
    "result_before_opt.json",
    "result_pre_vector.json",
    "result_dev_backup.json",
}
LOG_NAMES = {
    "capture.log", "capture_full.log", "dev_run.log", "opt_run.log",
    "run_all.log", "vector_run.log", "stress_run.log", "final_check.log",
    "holdout_run.log", "lookahead.log", "reproduce.log", "verify_curves.log",
    "winner_profile.log", "compare_agents.log", "compare_all.log",
    "compare_full.log", "export_compare_original.log", "full_direct.log",
    "full_missing.log", "cleanup_audit.log",
}

removed_dirs = 0
removed_files = 0
for p in list(ROOT.rglob("*")):
    if any(part in SKIP for part in p.parts):
        continue
    if p.is_dir() and p.name in CACHE_DIRS:
        shutil.rmtree(p, ignore_errors=True)
        removed_dirs += 1
    elif p.is_file() and (p.suffix in SUFFIXES or p.name in TEMP_NAMES or p.name in LOG_NAMES):
        p.unlink(missing_ok=True)
        removed_files += 1

# explicit web build log
(ROOT / "web" / "build.log").unlink(missing_ok=True)

print(f"removed {removed_dirs} cache dirs and {removed_files} generated files")
