"""lowvol replacement family."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ext_style

def build_weights(ts, opens, closes):
    return ext_style.make_weights(ts, opens, closes, "lowvol")

if __name__ == "__main__":
    ext_style.run_main("lowvol")
