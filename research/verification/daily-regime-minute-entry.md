# Verification: daily-regime-minute-entry

Command:

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents\daily-regime-minute-entry\strategy.py
```

Output (2026-11-25):

```text
10y: CAGR 58.80%  DD 44.56%  Sharpe 1.24  fills 657  end $9,304,768
5y:  CAGR 49.88%  DD 33.49%  Sharpe 1.16  fills 337  end $754,799
```

Cost sensitivity from `result.json`:

| Costs | 10y CAGR | 10y DD | 5y CAGR | 5y DD |
|---|---:|---:|---:|---:|
| 1 bp | 58.80% | 44.56% | 49.88% | 33.49% |
| 5 bp | 54.60% | 47.08% | 45.89% | 34.13% |
| 10 bp | 49.50% | 50.06% | 41.05% | 34.93% |

TQQQ benchmark: 39.28% / 81.68% (10y), 13.47% / 81.68% (5y).
Daily 165-day baseline: 45.31% / 58.71% (10y), 34.61% / 36.86% (5y).

## Look-ahead / execution check

- Regime: prior day's QQQ close vs the 165-day SMA through that prior close.
- MA20 arm gate: MA through the prior close.
- Stop: QQQ's 09:30 first-minute close vs the MA20 gate; if armed, a TQQQ
  close 4% below the session open sets the next minute's target to BIL.
- Weights are set at bar `i` close and filled at bar `i+1` open. The stop's
  trigger bar and fill bar are distinct.
- 1-minute marks use 1,057,023 bars; daily marks are shown as a robustness
  check (10y DD 41.62% vs 44.56%).
- 10 bp costs still pass both windows.

## Caveat

The 10y edge over the daily baseline is partly 2020-weighted: 2020 returns
+183.9% vs TQQQ +104.1%, while 2017-19 and 2023-26 contribute less. The
strategy is still a genuine minute stop overlay: the only minute decision is
the rare stop-out, not continuous intraday trading.
