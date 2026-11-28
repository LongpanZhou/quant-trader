"""retail sector family."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ext_sector

def build_weights(ts, opens, closes):
    return ext_sector.make_weights(ts, opens, closes, "retail")

if __name__ == "__main__":
    ext_sector.run_main("retail")
