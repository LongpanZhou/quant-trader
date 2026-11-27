"""Add event-study and grouped negative-result sections to result.json."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
r = json.loads((HERE / "result.json").read_text())
s1 = json.loads((HERE / "sweep1.json").read_text())

same_day = {k: v for k, v in s1.items() if k.startswith(("vwap", "ema", "qqqma"))}
overnight = {k: v for k, v in s1.items() if k.startswith(("overnight", "nextday"))}
r["same_day_reentry"] = same_day
r["overnight_reentry"] = overnight
r.pop("same_day", None)
r.pop("overnight", None)

r["event_study"] = {
    "n_stop_events_full_sample": 160,
    "n_stop_events_test_window_base": 153,
    "n_stop_events_test_window_combo": 143,
    "stop_to_close": {"mean": -0.00387, "median": -0.00329, "share_negative": 0.550},
    "stop_to_next_open": {"mean": -0.00461, "median": -0.00383, "share_negative": 0.538},
    "reclaims_after_stop": {
        "tqqq_vwap": {"n": 67, "share": 0.419, "mean_minute": 214,
                      "to_close_mean": -0.00236, "to_next_mean": -0.00813},
        "tqqq_ema5": {"n": 149, "share": 0.931, "mean_minute": 169,
                      "to_close_mean": -0.00507, "to_next_mean": -0.00544},
        "tqqq_ema15": {"n": 129, "share": 0.806, "mean_minute": 238,
                       "to_close_mean": -0.00373, "to_next_mean": -0.00517},
        "qqq_ma20": {"n": 5, "share": 0.031, "mean_minute": 276,
                     "to_close_mean": 0.00235, "to_next_mean": -0.00330},
    },
    "close_recovery_share": {"above_stop_level": 0.419, "above_vwap": 0.194, "above_open": 0.056},
    "next_day_open_to_close": {"weak_close_mean": 0.00726, "recovered_close_mean": 0.00481,
                               "n_weak": 93, "n_recovered": 67},
    "overnight_after_stop": {"close_above_stop_level_mean": -0.00329,
                             "close_below_stop_level_mean": 0.00009,
                             "close_above_vwap_mean": -0.01298,
                             "close_below_vwap_mean": 0.00148},
    "fixed_time_reentry_to_close": {"10:00": -0.00450, "10:30": -0.00556,
                                    "12:00": -0.00357, "14:00": -0.00410,
                                    "15:00": -0.00198, "15:30": -0.00364},
}

(HERE / "result.json").write_text(json.dumps(r, indent=2))
print("patched", list(r.keys()))
