"""Batch 3: stop_prev grid with 1bp/5bp, plus de-risk variants."""
import engine2 as E
import numpy as np
import pandas as pd

ts, o, c, feats = E.load_cached()
rows = []
for x in (0.020, 0.0225, 0.025, 0.0275, 0.030, 0.0325, 0.035, 0.040):
    p = dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=x)
    out1, w = E.run_one(ts, o, c, feats, p, slip=1.0, verbose=False)
    out5, _ = E.run_one(ts, o, c, feats, p, slip=5.0, verbose=False)
    row = dict(stop=x)
    for k in ("10y", "5y"):
        row[f"{k}_cagr"] = out1[k]["stats"]["cagr"]
        row[f"{k}_dd"] = out1[k]["stats"]["max_drawdown"]
        row[f"{k}_sh"] = out1[k]["stats"]["sharpe"]
        row[f"{k}_cagr5"] = out5[k]["stats"]["cagr"]
        row[f"{k}_dd5"] = out5[k]["stats"]["max_drawdown"]
        row[f"{k}_fills"] = out1[k]["stats"]["fills"]
    rows.append(row)
    print(f"stop {x*100:4.2f}%  10y {row['10y_cagr']*100:6.2f}/{row['10y_dd']*100:5.2f} sh {row['10y_sh']:.2f}"
          f" | 5y {row['5y_cagr']*100:6.2f}/{row['5y_dd']*100:5.2f} sh {row['5y_sh']:.2f}"
          f" | 5bp 10y {row['10y_cagr5']*100:6.2f}/{row['10y_dd5']*100:5.2f}"
          f" 5y {row['5y_cagr5']*100:6.2f}/{row['5y_dd5']*100:5.2f} fills {row['10y_fills']}", flush=True)

# de-risk to 50% instead of full exit
print("\n--- de-risk to 0.5 instead of 0 ---")
for x in (0.015, 0.02, 0.025, 0.03):
    p = dict(signal="none", base=1.0, entry=0, exit=0, stop_prev=x, risk_off_w=0.5)
    out1, _ = E.run_one(ts, o, c, feats, p, slip=1.0, verbose=False)
    s10, s5 = out1["10y"]["stats"], out1["5y"]["stats"]
    print(f"stop {x*100:4.2f}% half 10y {s10['cagr']*100:6.2f}/{s10['max_drawdown']*100:5.2f}"
          f" | 5y {s5['cagr']*100:6.2f}/{s5['max_drawdown']*100:5.2f} fills {s10['fills']}", flush=True)
