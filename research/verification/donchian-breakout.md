# Verification: donchian-breakout

Command:

```powershell
cd C:\Users\27175\Desktop\quant-trader-research
$env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
python research\agents\donchian-breakout\strategy.py
```

Output (2026-11-25):

```text
bars 211,558  2016-01-04 09:30:00-05:00 .. 2026-10-23 15:55:00-04:00  regime on 78.2%

=== primary ===
10y: CAGR  46.36%  DD 59.79%  Sharpe 1.02  fills 65  turn 558.4x  TQQQ exposure 82.2%
5y: CAGR  37.46%  DD 40.82%  Sharpe 0.93  fills 33  turn 58.2x  TQQQ exposure 73.8%
pass vs TQQQ: both windows PASS (CAGR, DD, Sharpe)
```

## Look-ahead / execution check

- Entry: QQQ 5-minute close above the prior 55-bar high. The current bar is
  excluded from the channel (`rolling(55).max().shift(1)`).
- Daily regime: for every bar of day `d` except 15:55, use the regime through
  `d-1`; the 15:55 bar carries the regime through `d`, and its target fills at
  the next session's 09:30 open. This is causal.
- `bt.simulate` fills at the next bar open; no same-bar fills.
- 5 bp costs still pass: 10y 45.97% / 59.91%, 5y 37.09% / 40.82%.
- Execution lag of 1-2 bars degrades gracefully: 10y 45.69% / 44.82% CAGR.
- The 10y drawdown is a COVID crash plus a 2020-03-10 regime whipsaw; the 5y
  drawdown is the August 2024 gap. These are real risks, not data errors.

## Verdict

**PASS vs TQQQ** on both windows: higher CAGR and lower max drawdown.
It is a genuine 5-minute entry strategy: the entry decision is made on
5-minute QQQ bars, while the exit is the daily 165-day regime.

It does **not** strictly dominate the daily 165-day baseline: it earns +1.05 pp
10y CAGR / +2.85 pp 5y CAGR but runs +1.08 pp / +3.96 pp more drawdown.
