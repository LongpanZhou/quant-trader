"""Verification: truncation (no-look-ahead) test, exposure, filter diagnostics."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402


def main():
    ts, o, h, lo, c, v = lab.load_panel()
    d = lab.Days(ts, o, c)
    g2 = d.gate(band=0.02)

    kw = dict(base="signal", m=60, gate=g2, vol_max=0.35, stop=0.04, signal_thr=-0.005)
    w_full = lab.build_weights(d, **kw)

    print("=== truncation test (weights must be unchanged by future data) ===")
    cuts = [300, 800, 1400, 1900, 2300, 2600]
    for cut in cuts:
        k = int(d.last[cut]) + 1
        d2 = lab.Days(ts[:k], o[:k], c[:k])
        w2 = lab.build_weights(d2, **{**kw, "gate": d2.gate(band=0.02)})
        # compare all weights except the last bar of the truncated panel
        same = np.array_equal(w2[:-1], w_full[:k - 1])
        md = np.max(np.abs(w2[:-1] - w_full[:k - 1]))
        print(f"  cut day {cut} ({str(d.ddates[cut])}): identical={same}  maxdiff={md:.1e}")
        assert same, "look-ahead detected"

    print("\n=== weight sanity ===")
    print("  max row sum", w_full.sum(1).max(), " min", w_full.min(),
          " any short", (w_full < -1e-12).any())
    on = w_full[:, 1] > 0
    bil = w_full[:, 2] > 0
    print(f"  bars in TQQQ {on.mean()*100:.1f}%  BIL {bil.mean()*100:.1f}%  overlap {(on&bil).sum()}")

    print("\n=== vol-filter diagnostics (10y) ===")
    i10 = np.searchsorted(d.ddates, np.datetime64(lab.START10))
    vol = d.vol(20, 0)
    lo_ = d.dclose[:, 0]
    hi10 = pd.Series(lo_).rolling(10).max().to_numpy()
    for vm in (0.30, 0.35, 0.40):
        sel = (vol > vm) & g2
        sel10 = sel[i10:]
        print(f"  vol>{vm:.2f}: {sel10.sum()} regime-on nights skipped of {g2[i10:].sum()} "
              f"({sel10.sum()/max(g2[i10:].sum(),1)*100:.1f}%)")

    print("\n=== per-year skipped nights (vol>0.35) ===")
    yr = np.array([x.year for x in d.ddates])
    sel = (vol > 0.35) & g2
    for y in sorted(set(yr[i10:])):
        m = (yr == y) & (np.arange(d.nd) >= i10)
        print(f"  {y}: skipped {int((sel & m).sum()):3d} / regime-on {int((g2 & m).sum()):3d}")

    print("\n=== trade composition of the primary (10y) ===")
    # count transitions by time of day
    w = w_full
    ch = np.any(w[1:] != w[:-1], axis=1)
    idx = np.flatnonzero(ch) + 1
    times = pd.Series(ts[idx]).dt.strftime("%H:%M")
    print(times.value_counts().head(12).to_string())


if __name__ == "__main__":
    main()
