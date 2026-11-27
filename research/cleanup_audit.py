from pathlib import Path

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
SKIP = {"node_modules", ".next", ".git", "data"}

patterns = ["__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"]
suffixes = {".pyc", ".prof", ".log", ".tmp"}
names = {"__full_tmp.py", "result_before_opt.json", "result_pre_vector.json",
         "result_dev_backup.json"}

rows = []
for p in ROOT.rglob("*"):
    if any(part in SKIP for part in p.parts):
        continue
    if p.name in patterns or p.suffix in suffixes or p.name in names:
        size = 0 if p.is_dir() else p.stat().st_size
        rows.append((str(p.relative_to(ROOT)), "dir" if p.is_dir() else "file", size))

rows.sort()
print(f"candidates: {len(rows)}")
for path, kind, size in rows:
    print(f"{kind:4s} {size/1024:10.1f} KB  {path}")
print(f"total files: {sum(1 for _,k,_ in rows if k=='file')}  dirs: {sum(1 for _,k,_ in rows if k=='dir')}")
