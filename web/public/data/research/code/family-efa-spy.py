"""efa_spy low-overlap external family."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ext_alt

def build_weights(ts, opens, closes):
    return ext_alt.make_weights(ts, opens, closes, "efa_spy")

if __name__ == "__main__":
    ext_alt.run_main("efa_spy")
