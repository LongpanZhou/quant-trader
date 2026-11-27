import json

r = json.load(open("research/agents2/stop-reentry-recovery/result.json"))
for n in ("base", "combo"):
    for lab in ("10y", "5y"):
        x = r["variants"][n][lab]
        print(n, lab, "total", round(x["total_return"] * 100, 2), "end", round(x["ending_equity"]),
              "bench", round(x["benchmark"]["cagr"] * 100, 2), round(x["benchmark"]["max_drawdown"] * 100, 2))
print("keys", list(r.keys()))
print("pass", r["pass"])
print("event keys", list(r["event_study"].keys()))
print("overnight keys", list(r["overnight_reentry"].keys()))
