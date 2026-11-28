import sys
from pathlib import Path

ROOT = Path(r"C:\Users\27175\Desktop\quant-trader-research")
sys.path.insert(0, str(ROOT / "research"))
import web_runner as W

SLUGS = ["ratio-pairs", "time-of-day", "family-ml-microstructure",
         "ml-classifier", "ml-crash-overlay-winner", "family-regime-switch"]
for slug in SLUGS:
    try:
        out = W.run(slug, "2019-01-02", "2020-12-31", {}, 1.0)
        print(f"OK   {slug:34s} cagr={out['cagr']*100:7.2f}% "
              f"dd={out['max_drawdown']*100:7.2f}% sharpe={out['sharpe']:5.2f} "
              f"fills={out['fills']}")
    except Exception as exc:
        print(f"FAIL {slug:34s} {type(exc).__name__}: {str(exc)[:160]}")
