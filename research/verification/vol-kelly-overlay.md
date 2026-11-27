# Verification: vol-kelly-overlay

Command:

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents\vol-kelly-overlay\strategy.py
```

Output (2026-11-25):

```text
10y  candidate   CAGR  47.53%  DD 45.32%  Sharpe 1.06  fills 327  turnover 1013.7x
      at 5bp     CAGR  46.96%  DD 45.85%  Sharpe 1.05
      baseline    CAGR  45.31%  DD 58.71%  Sharpe 1.00
      TQQQ        CAGR  39.28%  DD 81.68%  Sharpe 0.83
      pass vs TQQQ True  pass vs baseline True

5y   candidate   CAGR  34.59%  DD 36.29%  Sharpe 0.88  fills 85  turnover 87.4x
      at 5bp     CAGR  34.09%  DD 36.39%  Sharpe 0.87
      baseline    CAGR  34.61%  DD 36.86%  Sharpe 0.88
      TQQQ        CAGR  13.88%  DD 81.68%  Sharpe 0.53
      pass vs TQQQ True  pass vs baseline False
```

## Look-ahead / execution check

- Signals use the daily QQQ close and the within-day 1-minute realized variance of
  TQQQ through 15:59. Both are known at the 16:00 close.
- `bt.simulate` fills at the **next day's open**. The strategy code does not
  shift fills into the same bar.
- The 165-day SMA has 500 calendar days of warmup before 2017-01-03.
- Weights are long-only and sum to 1; the 2% band blocks small rebalances but
  not full regime exits.
- Costs are charged on every fill; 5 bp still passes vs TQQQ.

## Caveat

This is a **daily-rebalanced** strategy. The 1-minute data is used for the
realized-variance estimate, not for intraday entry/exit. It passes the stated
TQQQ return/drawdown test in both windows, but it is not a pure minute-decision
strategy. The 9 other agents are testing true minute-decision variants.
