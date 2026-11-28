"""Verify the tuned strategy.py on DEV only: identical weights, fixed event study, cut test."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


S = load(HERE.parent / "strategy.py", "imr_new")
bt = S.bt
ts, o, c = bt.panel(("QQQ", "TQQQ", "BIL"), S.DEV_START, S.DEV_END, "1min")
assert ts[-1].date() <= pd.Timestamp(S.DEV_END).date()
out = {}
w, info = S.build_weights(ts, o, c)

# before-tune build_weights, loaded from the copy (fix its ROOT-relative import by reusing bt)
src = (HERE.parent / "_before_tune" / "strategy.py").read_text(encoding="utf-8")
ns = {"__name__": "imr_old", "__file__": str(HERE.parent / "strategy.py")}
exec(compile(src, "before_tune_strategy.py", "exec"), ns)
w_old, info_old = ns["build_weights"](ts, o, c)
out["weights_max_abs_diff_before_vs_after"] = float(np.abs(w - w_old).max())
out["event_dates_first5_after"] = info["event_dates"][:5]

rows = S.event_returns(ts, o, c, threshold=0.03)
bs = S.cluster_bootstrap(rows)
out["event_study_dev_fixed"] = {k: bs[k] for k in ("n_events", "n_clusters", "mean", "median", "win_rate", "p_mean_le_0", "ci95")}
out["event_dates_range"] = [rows[0][0], rows[-1][0]]

# cut tests: truncate the 1-minute arrays at the cut (bars that start before it)
for cut in ("2020-03-12 11:07", "2022-09-13 10:41"):
    ct = pd.Timestamp(cut, tz="America/New_York")
    m = int(np.searchsorted(ts, ct))
    wc, _ = S.build_weights(ts[:m], o[:m], c[:m])
    # last two bars before the cut may differ (end-of-data handling: w[-1] forced to BIL,
    # and the truncated final bar is treated as a session close)
    cmp_n = m - 2
    diff = int((np.abs(wc[:cmp_n] - w[:cmp_n]) > 0).any(axis=1).sum())
    out[f"cut_{cut}"] = {"bars_compared": cmp_n, "rows_differing": diff}

json.dump(out, open(HERE / "tune_verify.json", "w", newline="\n", encoding="utf-8"), indent=1)
print(json.dumps(out, indent=1))
