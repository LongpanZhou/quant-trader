# Six new families — objective tracker

Goal: six additional TQQQ outperformers, one per family, with no family
overlap with the existing above-TQQQ strategies or with each other.

An outperformer must clear the full 2016-2026 daily-close bar:
**CAGR > 37.54% and max DD < 81.68%**.

| Family | Candidate | Dev CAGR | Full CAGR | Full DD | Status |
|---|---|---:|---:|---:|---|
| Calendar / event | `fomc-opex-window` | 58.26% | **52.77%** | 40.64% | **VERIFIED** — audit PASS |
| Session timing | `family-session-timing` | 56.23% | **46.26%** | 41.42% | **VERIFIED** — audit PASS, cost-fragile at 4 bp |
| Short-term reversal | `family-short-reversal` | 45.90% | **49.54%** | 66.46% | **VERIFIED** — audit PASS |
| Intraday microstructure | `family-intraday-microstructure-day` | 44.12% | **40.97%** | 47.42% | **VERIFIED** — audit PASS, flat overnight, 1 bp only |
| Rebalance flow | `family-rebalance-flow` | 50.55% | **45.55%** | 50.92% | **VERIFIED** — audit PASS |
| ML microstructure | `family-ml-microstructure` | 49.81% | **41.03%** | 44.51% | **VERIFIED** — audit PASS, cost-robust |

## Audit note

For `family-short-reversal`, `family-session-timing`, `family-rebalance-flow`
and `family-intraday-microstructure-day`, the 11:07 truncation only changes the
final partial session, which those strategies deliberately do not trade. Every
bar before the final session is **0.0** difference. The audit records this as
an explicit boundary exemption.

## Family purity

- Calendar: hardcoded FOMC/OpEx dates; vol throttle is only a risk overlay.
- Session: intraday session clock, no daily trend gate.
- Short reversal: QQQ down streak/3-day return, no trend/stop/vol in the primary.
- Rebalance flow: mechanical close-window de-risk, 50% vol sizing only.
- Intraday microstructure: day-only opening drive/range; flat overnight.
- ML microstructure: walk-forward weekly ridge on session-shape price/volume features.

## Existing duplicate above-TQQQ families

- `trend-vol`: `ratio-froth` 62.21% (legacy, no frozen holdout) vs `fast-trend-vol` 44.61% (verified).
- `vol-crash`: `vol-scaled-crash-stop` 51.32% (legacy, no frozen holdout) vs `vol-term-structure` 42.48% (verified).
- `relative`: `relative-value-tqqq` 40.50% vs `qqq-spy-relative` 38.98%, both verified.

Policy: a family winner must be `verified-full`. Legacy above-bar names remain
research records but are not family winners.
