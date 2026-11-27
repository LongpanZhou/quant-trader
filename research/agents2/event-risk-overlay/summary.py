import json
from pathlib import Path

r = json.load(open(Path(__file__).parent / "result.json"))
print("EVENT STUDY (risk-on sessions, bp)")
for k, v in r["event_study"].items():
    if k.startswith("_"):
        print(k, v)
        continue
    print(f"{k:5s} n={v['n_risk_on']:3d} c2c {v['tqqq_c2c_bp']:7.1f} c2o {v['tqqq_c2o_bp']:6.1f} "
          f"o2c {v['tqqq_o2c_bp']:7.1f} qqq_o2c {v['qqq_o2c_bp']:6.1f} swap {v['swap_gain_bp']:6.1f} "
          f"t={v['swap_gain_t']:5.2f} hit {v['swap_hit_rate']*100:3.0f}% non_o2c {v['non_event_o2c_bp']:6.1f}")

print("\nvariant           cost  10y CAGR/DD(1m) dailydd   5y CAGR/DD(1m) dailydd  Sh10  fills  roll3y")
for name in ["baseline"] + list(r["variants"]):
    v = r["baseline"] if name == "baseline" else r["variants"][name]
    for c in ["1bp", "5bp", "10bp"]:
        a = v["costs"][c]["10y"]
        b = v["costs"][c]["5y"]
        print(f"{name:17s} {c:4s} {a['cagr']*100:6.2f}/{a['max_drawdown']*100:5.2f} {a['max_drawdown_daily']*100:7.2f}   "
              f"{b['cagr']*100:6.2f}/{b['max_drawdown']*100:5.2f} {b['max_drawdown_daily']*100:6.2f}  "
              f"{a['sharpe']:5.2f} {a['fills']:5d}  {v.get('rolling3y_wins_both', '-')}/{v.get('rolling3y_n', '-')}")

print("\nDD dates (1bp):")
for name in ["baseline"] + list(r["variants"]):
    v = r["baseline"] if name == "baseline" else r["variants"][name]
    a = v["costs"]["1bp"]["10y"]
    b = v["costs"]["1bp"]["5y"]
    print(f"  {name:17s} 10y {a['dd_peak']}->{a['dd_trough']}   5y {b['dd_peak']}->{b['dd_trough']}")

print("\nYEARLY (1bp, 10y window)")
names = ["baseline"] + list(r["variants"])
print("year " + "".join(f"{n[:13]:>14s}" for n in names))
for y in sorted(r["baseline"]["yearly"], key=int):
    print(y + " " + "".join(f"{(r['baseline'] if n=='baseline' else r['variants'][n])['yearly'][y]*100:13.1f}%" for n in names))

print("\nPASS flags (strict dominance vs winner)")
for name in r["variants"]:
    for k, v in r["variants"][name]["pass"].items():
        print(f"  {name:17s} {k:9s} dcagr {v['cagr_diff_pp']:+6.2f}pp  dDD {v['dd_diff_pp']:+6.2f}pp  "
              f"dominance {v['strict_dominance']}  beatsTQQQ {v['beats_tqqq']}")

print("\nROLLING 3Y")
for name in ["baseline"] + list(r["variants"]):
    v = r["baseline"] if name == "baseline" else r["variants"][name]
    r3 = v["rolling3y"]
    print(f"  {name:17s} n={len(r3):2d} meanCAGR {sum(x['cagr'] for x in r3)/len(r3)*100:5.1f}% "
          f"worstDD {max(x['max_drawdown'] for x in r3)*100:5.1f}% wins {v.get('rolling3y_wins_both','-')}")
