# Exact specification — standalone two-stream risk parity

**Universe:** QQQ (1x equity), TQQQ (3x equity), BIL (T-bills). SPY is available as
a daily benchmark only; it is not used in the signal (0.99 correlated with QQQ,
so it adds no independent driver). No other asset has local 2016–2023 data yet.
**Decision frequency:** daily, at the last bar of the regular session (15:59 ET).
**Execution:** target set at bar *i*'s close, filled at bar *i+1*'s open; 2% band;
long-only; weights sum to ≤ 1; residual BIL.
**Marks:** 1-minute equity marks.
**Development period:** 2016-01-04 → 2023-12-29 only. Holdout is never touched by
this agent.

---

## 1. Daily features (QQQ adjusted closes)

For session day *d* (all known at the 15:59 close):

| Feature | Definition |
|---|---|
| `r1[d]` | `C[d]/C[d-1] - 1` |
| `r3[d]` | `C[d]/C[d-3] - 1` |
| `r5[d]` | `C[d]/C[d-5] - 1` |
| `vol10[d]` | population std of `r1` over the last 10 sessions, `d-9..d` |
| `vol60[d]` | population std of `r1` over the last 60 sessions, `d-59..d` |
| `vol_ratio[d]` | `vol10[d] / vol60[d]` |
| `q40[d]` | 40th percentile of `vol10` over the last 60 sessions, `d-59..d` (min 40 obs) |
| `sma10[d]` | mean QQQ close over `d-9..d` |
| `tq_close[d]` | TQQQ adjusted close |

No 100–250-day moving average of QQQ/TQQQ/SPY/NDX is used anywhere. The longest
lookback is 60 sessions (a volatility quantile, not a price gate).

## 2. Stream A — calm-regime QQQ carry

At the close of day *d*:

```
calm[d]  = vol10[d] < q40[d]
up5[d]   = r5[d] > 0
on_A[d]  = calm[d] and up5[d]
```

Target for day *d+1*:

- `on_A[d]` true  → **70% QQQ + 30% BIL**
- `on_A[d]` false → **100% BIL**

The 70/30 split is deliberate: the carry stream is a partial equity position so
the reversal stream can contribute risk budget without the portfolio becoming a
pure QQQ proxy. A 100%-QQQ variant is a pre-registered neighbour.

Holding period: regime-based, typically days to weeks. Exit is evaluated every
close and filled at the next open; there is no intraday stop in Stream A.

## 3. Stream B — panic-reversal TQQQ

### Entry (at close *d*, fill at *d+1* open)

```
panic[d] = (r3[d] <= -0.05) or (r1[d] <= -0.03 and vol_ratio[d] >= 1.5)
```

If flat, not in cooldown, and `panic[d]` is true → buy **100% TQQQ** at day
*d+1*'s open.

### Exit (evaluated at each close while holding; fill next open)

Exit on the first of:

1. **Recovery:** `QQQ close[d] > sma10[d]` (close back above the 10-day mean).
2. **Stop:** `TQQQ close[d] < entry_ref * (1 - 0.08)`, where `entry_ref` is the
   first TQQQ close after entry (the close on the entry fill day). This is a
   close-based stop; the fill is the next open. It is not an intraday stop.
3. **Time:** `held >= 3` sessions (the third held session's close triggers the
   exit).

After any exit, a **2-session cooldown** blocks re-entry. A new panic signal
during the cooldown is ignored.

Holding period: 1–3 sessions after the entry fill (minimum 1, maximum 3).
Stream B is in the market roughly 5–10% of sessions.

### Risk note

TQQQ can gap through the 8% stop. The stop is a risk reducer, not a guarantee;
the report must show the worst event and the gap exposure.

## 4. Allocation — inverse volatility

At the close of day *d*, using only data through *d*:

1. Compute each stream's standalone daily return series from its own target
   weights and close-to-close asset returns:
   `ret_j[d] = sum_s w_j[d-1, s] * (C_s[d]/C_s[d-1] - 1)`.
2. `sigma_j[d] = std(ret_j[d-20 .. d-1])` (20 observations, **shifted one day**;
   today's return is not used to size today's target). Minimum 10 observations.
3. `a_A[d] = (1/sigma_A) / (1/sigma_A + 1/sigma_B)`, clipped to **[0.20, 0.80]**;
   `a_B[d] = 1 - a_A[d]`. If either sigma is missing, `a_A = a_B = 0.5`.
4. Blend target for day *d+1*:
   `w_blend[d] = a_A[d] * w_A[d] + a_B[d] * w_B[d]`.

Because `w_A` is at most 70% QQQ and `w_B` is at most 100% TQQQ, the blend's
total equity exposure never exceeds 100%; residual is BIL. No leverage beyond
100% TQQQ, no shorts.

## 5. Parameters (centre) and ±1-step neighbourhood

| Parameter | Centre | −1 step | +1 step |
|---|---:|---:|---:|
| Carry vol lookback | 10 | 5 | 20 |
| Carry vol quantile window | 60 | 40 | 80 |
| Carry vol quantile | 0.40 | 0.30 | 0.50 |
| Carry momentum lookback | 5 | 3 | 10 |
| Carry QQQ weight | 0.70 | 0.50 | 1.00 |
| Reversal 3-day drop | −5.0% | −4.0% | −6.0% |
| Reversal 1-day drop | −3.0% | −2.5% | −3.5% |
| Reversal vol ratio | 1.5 | 1.3 | 1.8 |
| Reversal max hold | 3 | 2 | 5 |
| Reversal stop | 8% | 6% | 10% |
| Reversal cooldown | 2 | 1 | 3 |
| Allocation vol lookback | 20 | 15 | 30 |
| Allocation clip | [0.20, 0.80] | [0.15, 0.85] | [0.25, 0.75] |

The centre is chosen from the economic story, not from a fit: 10-day vol,
10/60-day calm percentile, 5-day momentum, 5% 3-day panic, 3-day hold, 20-day
risk estimate, 20/80 risk caps. The neighbourhood is reported in full; a
parameter is only accepted if the result is a plateau.

## 6. Evaluation plan (when the lead authorises the run)

- **Windows:** dev only (2016-01-04 → 2023-12-29). No official 10y/5y and no
  holdout; those overlap 2024–2026 and are the lead's job after freezing.
- **Costs:** 1 bp headline, 5 bp and 10 bp.
- **Metrics:** CAGR, max drawdown on 1-minute marks, Sharpe, Sortino, vol,
  exposure, fills, turnover.
- **Correlations:** blend vs 165-day baseline; each stream vs baseline; stream
  A vs stream B, on daily returns over dev.
- **Sub-periods:** 2016–2019, 2020–2021, 2022–2023.
- **Neighbourhood:** table of every ±1-step variant above at 1 bp (plus 5 bp for
  the centre).
- **Placebo:** 200 random-signal runs with the same on-share for A and the same
  event count/hold for B; report the percentile of the real dev Sharpe.
- **Event study:** Stream-B events count, mean 3-day forward TQQQ return,
  bootstrap p-value (10,000 resamples of event means) vs the unconditional
  3-day return.
- **Benchmarks:** TQQQ, QQQ, SPY buy-and-hold on dev; the original strategy's
  published 10y/5y numbers, clearly labelled as not dev-comparable.

## 7. Causality checklist

- Every daily feature at day *d* uses closes ≤ *d*.
- `q40`, `sma10`, `vol10`, `vol60` are rolling backward windows.
- The allocation `sigma` is shifted one day (uses returns through *d−1*).
- The target set at close *d* is `w_blend[d]` and is mapped by
  `minute_marks.to_minutes` so the last bar of day *d* carries it and the fill is
  at *d+1*'s open.
- Stream B's `entry_ref` is the first TQQQ close **after** the entry fill, never
  the signal-day close.
- No use of the 165-day SMA, the round-1 stop, or any old `build_weights`.

## 8. Known limitations before the run

- Only one equity factor is available locally; the strategy cannot diversify
  across bonds/gold/sectors. The "two streams" are two conditional exposures to
  the same factor, so a residual correlation with the baseline is expected.
- Stream B has few events (likely 30–60), so its edge will be statistically
  weak. The bootstrap and event count are mandatory.
- A close-based 8% stop cannot prevent overnight gaps in TQQQ.
- The 70% carry weight and the 20/80 clip are risk choices, not fitted values;
  the neighbourhood tests whether they matter.
