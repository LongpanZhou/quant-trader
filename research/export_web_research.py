r"""Export the individual research-strategy pages.

Creates:
  web/public/data/research/strategies.json
  web/public/research/<slug>.md   (a copy of each available agent report)

Run from the repo root:
    $env:PYTHONPATH = "C:\Users\27175\AppData\Local\Temp\opencode\pylibs"
    python research/export_web_research.py
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "public" / "data" / "research" / "strategies.json"
REPORT_OUT = ROOT / "web" / "public" / "research"
CODE_OUT = ROOT / "web" / "public" / "research" / "code"

CODE_OVERRIDES = {
    "ratio-first-blend": ROOT / "research" / "verification" / "blend_ratio.py",
    "ratio-volume-blend": ROOT / "research" / "verification" / "blend_ratio.py",
    "first-volume-blend": ROOT / "research" / "verification" / "blend_17_23.py",
}

# --------------------------------------------------------------------------- #
# Reusable paper references
# --------------------------------------------------------------------------- #
FABER = ("Faber (2007) · A Quantitative Approach to Tactical Asset Allocation", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461")
GAYED = ("Gayed & Bilello (2016) · Leverage for the Long Run", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2741701")
MOREIRA = ("Moreira & Muir (2017) · Volatility-Managed Portfolios", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431")
CEDERBURG = ("Cederburg et al. (2020) · On the Performance of Volatility-Managed Portfolios", "https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X")
ZARATTINI_ANT = ("Zarattini & Antonacci (2024) · A Century of Profitable Industry Trends", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4857230")
GAO = ("Gao, Han, Li & Zhou (2018) · Market Intraday Momentum", "https://doi.org/10.1016/j.jfineco.2018.05.009")
LOU = ("Lou, Polk & Skouras (2019) · A Tug of War: Overnight vs Intraday", "https://doi.org/10.1016/j.jfineco.2019.03.011")
BALTUSSEN = ("Baltussen et al. (2021) · Intraday Momentum", "https://doi.org/10.1016/j.jfineco.2021.04.029")
CHENG = ("Cheng & Madhavan (2009) · The Dynamics of Leveraged ETF Returns", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1393995")
CLIFF = ("Cliff, Cooper & Gulen (2008) · Like Night and Day", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081")
AVELLANEDA = ("Avellaneda & Zhang (2010) · Path-Dependence of Leveraged ETF Returns", "https://epubs.siam.org/doi/10.1137/090760805")
BRUNNERMEIER = ("Brunnermeier & Sannikov (2014) · A Macroeconomic Model with a Financial Sector", "https://www.aeaweb.org/articles?id=10.1257/aer.104.2.379")
BAILEY = ("Bailey et al. · The Probability of Backtest Overfitting", "https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf")
ARNOTT = ("Arnott, Harvey & Markowitz (2019) · A Backtest Is Not a Strategy", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3275654")
LOPEZ_HRP = ("López de Prado (2016) · Building Diversified Portfolios that Outperform Out-of-Sample", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678")
ZARATTINI_ORB = ("Zarattini & Aziz (2023) · Can Day Trading Really Be Profitable?", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622")
ZARATTINI_IM = ("Zarattini, Barbon & Aziz (2024) · Beat the Market: Intraday Momentum", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284")
TURTLE = ("The Original Turtle Trading Rules", "https://www.originalturtles.org/rules.htm")
CONNORS = ("QuantifiedStrategies · RSI(2) Mean Reversion", "https://www.quantifiedstrategies.com/rsi-2-strategy/")
VWAP = ("Scanz · VWAP Trading Strategy", "https://scanz.com/vwap-trading-strategy")
OPEX = ("Quantpedia · Option Expiration Week Effect", "https://quantpedia.com/strategies/option-expiration-week-effect")
NYFED512 = ("NY Fed Staff Report 512 · The Pre-FOMC Announcement Drift", "https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf")
MAN_VOL = ("Man Group · The Impact of Volatility Targeting", "https://www.man.com/insights/the-impact-of-volatility-targeting")
ATR = ("Quant Arenas · Chandelier / ATR Exit", "https://quantarenas.com/strategy/trend-17-chandelier-exit")
STOP_STUDY = ("Cesar Alvarez · Stop-Loss Studies", "https://bettersystemtrader.com/037-cesar-alvarez-studies-stop-losses")
LETF_REBAL = ("ETF.com · One Bad Day in a Leveraged QQQ ETF", "https://www.etf.com/sections/equity/one-bad-day-levered-qqq-etf-case-study")
LENKEY = ("Lenkey (2024) · Leveraged ETF Rebalancing and Late-Day Flow", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4710812")
LLORENTE = ("Llorente et al. (2002) · Volume and Information", "https://doi.org/10.1111/0022-1082.00280")
NEWFOUND = ("Newfound (2020) · Ensembles and Rebalancing", "https://blog.thinknewfound.com/2020/02/ensembles-and-rebalancing")
DEMIGUEL = ("DeMiguel, Garlappi & Uppal (2009) · Optimal Versus Naive Diversification", "https://doi.org/10.1093/rfs/hhm075")
ASNESS = ("Asness, Frazzini & Pedersen (2012) · Leverage Aversion and Risk Parity", "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2149341")
GAP_STRATEGY = ("QuantifiedStrategies · Gap Reversal", "https://www.quantifiedstrategies.com/gap-reversal-trading-strategy/")
FINLAB_DECAY = ("FinLab · Leveraged ETF Decay", "https://finlab.finance/en/blog/leveraged-etf-decay")
ELM_NIGHT = ("Haghani, Ragulin & Dewey · Night Moves: Overnight Drift", "https://elmwealth.com/wp-content/uploads/2026/04/Elm-Night-Moves-Overnight-Drift.pdf")

# --------------------------------------------------------------------------- #
# Curated metadata
# --------------------------------------------------------------------------- #
M = {
    "daily-regime-minute-entry": dict(
        name="Armed 4% minute stop", group="Round 1", status="Verified",
        tagline="QQQ 165-day regime with a rare, armed 4% intraday crash stop.",
        summary="Hold TQQQ while QQQ is above its 165-day SMA. On weak days, arm a 4% stop from the session open only when QQQ is near/below its 20-day MA; a trigger moves the book to BIL for the rest of the day and night.",
        rules=["QQQ prior close > 165-day SMA → TQQQ, else BIL.",
               "Arm the stop when QQQ's first minute is below MA20 × 1.01.",
               "If armed and TQQQ closes 4% below the session open, exit at the next minute's open and stay out until the next session."],
        papers=[FABER, GAYED, FINLAB_DECAY, LOU, ELM_NIGHT],
        verdict="Round-1 winner. Strictly beats TQQQ on both windows and passes at 10 bp; 27/27 rolling 3-year windows have lower drawdown than TQQQ.",
        curve="a1", metrics=(0.5880, 0.4456, 0.4988, 0.3349),
    ),
    "opening-range-breakout": dict(
        name="Opening-range breakout", group="Round 1", status="Verified",
        tagline="A 30-minute opening range, held overnight while the QQQ regime is on.",
        summary="Take a 30-minute TQQQ opening range, buy the first close above it after 10:00, stop at the range low, and hold overnight while QQQ is above its 165-day SMA.",
        rules=["Opening range: 09:30–09:59 on TQQQ.",
               "Enter on the first 1m close above the range high after 10:00.",
               "Stop at the range low; exit when the daily regime turns off; BIL otherwise."],
        papers=[ZARATTINI_ORB, ZARATTINI_IM, FABER, GAYED],
        verdict="Passes vs TQQQ on both windows; the pure intraday version fails because TQQQ's drift is mostly overnight.",
        curve=None, metrics=(0.4898, 0.4855, 0.3408, 0.4217),
    ),
    "intraday-mean-reversion": dict(
        name="Intraday mean reversion", group="Round 1", status="Verified",
        tagline="A 3% QQQ capitulation stop with next-session re-entry.",
        summary="Every pure intraday RSI/Bollinger/VWAP mean-reversion variant failed after costs. What survived was a 3% QQQ intraday stop that steps aside, then re-enters at the next open in a bull regime.",
        rules=["Risk-on: QQQ above its 165-day SMA.",
               "If QQQ closes 3% below the prior close intraday, sell TQQQ at the next bar and stay BIL for the session.",
               "Re-enter at the next 09:30 open if the regime is still on."],
        papers=[CONNORS, LOU, FABER, CHENG],
        verdict="Passes at 20 bp; the drawdown cut is structural, but the return lift is crash-episode dependent.",
        curve=None, metrics=(0.5096, 0.4483, 0.3550, 0.3629),
    ),
    "intraday-momentum": dict(
        name="First-hour momentum", group="Round 1", status="Verified",
        tagline="Overnight drift plus a first-hour filter for the afternoon.",
        summary="Hold TQQQ overnight and through the first hour while the QQQ regime is on. In the afternoon, hold TQQQ only if the QQQ first-hour return is non-negative.",
        rules=["QQQ prior close > 165-day SMA → risk-on.",
               "Hold TQQQ from 15:59 to 10:30.",
               "At 10:29 compute the QQQ first-hour return; hold the afternoon only if it is ≥ 0."],
        papers=[GAO, BALTUSSEN, LOU, CHENG, ELM_NIGHT],
        verdict="Strong round-1 result: 55.63% / 44.89% (10y) and 46.36% / 32.64% (5y). Fails the daily baseline at 5 bp on the 10y.",
        curve="a4", metrics=(0.5563, 0.4489, 0.4636, 0.3264),
    ),
    "drawdown-stop-overlay": dict(
        name="Drawdown threshold stop", group="Round 1", status="Verified",
        tagline="Exit at the exact 165-day SMA threshold and wait for a new 10-day high.",
        summary="The daily SMA rule is whipsawed in March 2020. This variant exits intraday when QQQ first trades through the exact 165-day SMA threshold and refuses to re-enter on the weak bounce.",
        rules=["Hold TQQQ while QQQ is above its 165-day SMA.",
               "Exit when QQQ trades through 0.995 × the exact SMA threshold.",
               "Re-enter on the next regime cross or a new 10-day TQQQ high."],
        papers=[FABER, FINLAB_DECAY, ATR, STOP_STUDY],
        verdict="Beats TQQQ on both windows; 10y improvement is concentrated in the March 2020 whipsaw, and the 5y drawdown is worse than the daily baseline.",
        curve=None, metrics=(0.4689, 0.4532, 0.3240, 0.4296),
    ),
    "donchian-breakout": dict(
        name="5m Donchian breakout", group="Round 1", status="Verified",
        tagline="A 5-minute 55-bar breakout entry, gated by the daily QQQ regime.",
        summary="Buy a new 55-bar high on QQQ 5-minute bars while QQQ is above its 165-day SMA; let the daily regime be the exit and hold TQQQ overnight.",
        rules=["QQQ 5m close > prior 55-bar high.",
               "Daily gate: QQQ close > 165-day SMA.",
               "Exit when the daily regime turns off; BIL otherwise."],
        papers=[TURTLE, FABER, GAYED],
        verdict="Passes vs TQQQ, but its 10y drawdown is higher than the daily baseline; classic Turtle exits fail on minute bars.",
        curve=None, metrics=(0.4636, 0.5979, 0.3746, 0.4082),
    ),
    "ml-classifier": dict(
        name="ML risk-off overlay", group="Round 1", status="Verified",
        tagline="A walk-forward logistic overlay on the daily trend.",
        summary="Three L2 logistic models predict TQQQ-vs-BIL over 5/10/20 days from 38 causal features. A low trailing rank moves the book to BIL; otherwise the daily regime decides.",
        rules=["Base: QQQ 165-day SMA → TQQQ/BIL.",
               "Train on a 750-day rolling window, annual retrain, purge h+1.",
               "If the average probability rank < 0.20, hold BIL for the next day."],
        papers=[BAILEY, ARNOTT, LOPEZ_HRP, ZARATTINI_ANT],
        verdict="Highest headline return, but the 30/60-minute classifier failed out of sample; the passing version makes daily decisions, not minute decisions.",
        curve=None, metrics=(0.7495, 0.4048, 0.5129, 0.3320),
    ),
    "ensemble-signals": dict(
        name="Ensemble crash vote", group="Round 1", status="Verified",
        tagline="Trend gate + volatility budget + a same-session crash vote.",
        summary="A daily QQQ trend gate and a 20-day volatility budget decide the default position. A same-session vote from a 60-minute EMA, 30-minute momentum and RSI(14) can only reduce risk.",
        rules=["Default: QQQ > 165-day SMA and vol ≤ 1/3 → TQQQ, else BIL.",
               "Crash vote: if QQQ is ≥3% below the prior close, sell if the vote sum ≤ −2.",
               "All fills next bar open."],
        papers=[FABER, MOREIRA, ZARATTINI_ANT, GAO, LOU],
        verdict="54.73% / 39.91% (10y) and 40.79% / 34.93% (5y); a solid ensemble but not the leader.",
        curve="a8", metrics=(0.5473, 0.3991, 0.4079, 0.3493),
    ),
    "time-of-day": dict(
        name="Overnight + first 30m", group="Round 1", status="Verified",
        tagline="Hold TQQQ only from 15:59 to 10:01 the next morning.",
        summary="The overnight block carries most of TQQQ's return, while the last 30 minutes are the worst block of the day. The strategy holds TQQQ from 15:59 to 10:01 and is in cash otherwise.",
        rules=["QQQ 165-day SMA with a 2% hysteresis band.",
               "Enter TQQQ at 15:59; exit at 10:01 the next session.",
               "Cash otherwise; no BIL leg."],
        papers=[CLIFF, LOU, GAO, ELM_NIGHT],
        verdict="Passes at 1 bp but fails at 5 bp; two fills a day are the binding constraint.",
        curve=None, metrics=(0.4923, 0.4266, 0.2889, 0.3454),
    ),
    "vol-kelly-overlay": dict(
        name="Volatility ladder", group="Round 1", status="Verified",
        tagline="A 1-minute realized-vol ladder from TQQQ to QQQ.",
        summary="Stay in TQQQ below 65% annualized 1-minute realized vol, shift linearly into QQQ between 65% and 95%, and hold QQQ above 95%. A mild crash throttle moves 5% to BIL.",
        rules=["QQQ 165-day SMA regime.",
               "20-day realized vol from 1-minute TQQQ returns.",
               "TQQQ below 65%, QQQ above 95%, linear in between."],
        papers=[MOREIRA, CEDERBURG, MAN_VOL, ZARATTINI_ANT],
        verdict="Passes vs TQQQ; daily-rebalanced, so it is not a pure minute-decision strategy. The 10y edge is concentrated in 2020.",
        curve=None, metrics=(0.4753, 0.4532, 0.3459, 0.3629),
    ),
    "winner-ensemble-blend": dict(
        name="Winner/ensemble 75/25", group="Round 2", status="Alternative",
        tagline="A 75% winner + 25% ensemble blend.",
        summary="Blend the round-1 winner with the ensemble. The 75/25 mix is the only headline blend that meets the lower-drawdown / comparable-return rule at 1, 5 and 10 bp.",
        rules=["75% capital in the round-1 winner.",
               "25% capital in the ensemble crash-vote strategy.",
               "Rebalance with the 2% band."],
        papers=[NEWFOUND, DEMIGUEL, ASNESS],
        verdict="Meets the lower-DD rule but not strict dominance; 5y CAGR is 1.96 pp below the winner.",
        curve=None, metrics=(0.5842, 0.4118, 0.4792, 0.3233),
    ),
    "vol-scaled-crash-stop": dict(
        name="ATR-scaled stop", group="Round 2", status="Alternative",
        tagline="Tighten the stop in calm markets, cap it at 4%.",
        summary="Replace the fixed 4% stop with clip(0.70 × ATR14, 2.5%, 4%). In calm markets the stop tightens; in stress it never widens beyond the round-1 4%.",
        rules=["Base: round-1 winner.",
               "Stop distance = clip(0.70 × ATR14, 2.5%, 4%).",
               "One-sided: never wider than 4%."],
        papers=[ATR, STOP_STUDY, MOREIRA],
        verdict="Strict 10y dominance; the 5y drawdown is mathematically identical to the winner. The 4% cap is the important part.",
        curve=None, metrics=(0.6260, 0.4094, 0.5488, 0.3349),
    ),
    "dual-speed-regime": dict(
        name="Dual-speed regime", group="Round 2", status="Alternative",
        tagline="165-day slow gate plus an armed 60-minute EMA filter.",
        summary="Keep the 165-day QQQ gate for the overnight position. When QQQ is weak at the open, a fresh 60-minute EMA(40) down-cross exits the intraday position; an up-cross re-enters.",
        rules=["Slow gate: QQQ > 165-day SMA.",
               "Fast filter: 60-minute EMA(40) crossover.",
               "Fast filter only acts when QQQ's first minute is below MA20 × 1.01."],
        papers=[FABER, GAYED, ZARATTINI_ANT],
        verdict="70.11% / 42.91% (10y) and 61.78% / 25.88% (5y). Higher 10y CAGR than the ratio leader, but a worse 10y drawdown.",
        curve=None, metrics=(0.7011, 0.4291, 0.6178, 0.2588),
    ),
    "event-risk-overlay": dict(
        name="OpEx de-risk", group="Round 2", status="Alternative",
        tagline="Step aside on OpEx Friday; optionally add FOMC.",
        summary="The event study found a large negative intraday drift on OpEx Fridays. On risk-on sessions, sell TQQQ at 09:31 and re-enter at 15:59; the OpEx+FOMC variant also de-risks FOMC days.",
        rules=["Risk-on session.",
               "OpEx third Friday: TQQQ → BIL from 09:31 to 15:59.",
               "Optional FOMC leg; do not de-risk the overnight."],
        papers=[OPEX, NYFED512, LENKEY],
        verdict="Strict 10y dominance at 1/5/10 bp; the 5y drawdown is worse than the winner. OpEx was selected after seeing the other event families, so treat it as a research candidate.",
        curve=None, metrics=(0.6706, 0.4065, 0.5383, 0.3588),
    ),
    "gap-capitulation-reversal": dict(
        name="Gap capitulation", group="Round 2", status="Negative",
        tagline="Cross-overnight capitulation bounce — real, but not incremental.",
        summary="A QQQ close ≤ −2% or a −3% intraday low is followed by a strong next-session bounce in a bull regime. But the winner's stop already captures it; the standalone event strategy is not investable.",
        rules=["Bull regime only.",
               "Event: QQQ ≤ −2% close or −3% intraday low.",
               "Buy TQQQ at the next open; the standalone test holds one day."],
        papers=[GAP_STRATEGY, LOU, CLIFF],
        verdict="Clean negative. The event is statistically real (t ≈ 2.0–2.4) but redundant with the winner's stop-and-re-enter.",
        curve=None, metrics=(0.0774, 0.2122, 0.0795, 0.0820),
    ),
    "stop-reentry-recovery": dict(
        name="Gradual stop re-entry", group="Round 2", status="Verified",
        tagline="Re-enter gradually after the 4% stop instead of staying out.",
        summary="After the stop, if the stop-day close is above the stop level, re-enter 100% at 09:31 with a 2% stop. If it closes below, re-enter 50% and restore 100% after a clean session.",
        rules=["Base: round-1 winner.",
               "Stop-day close above stop → 100% re-entry with 2% stop.",
               "Stop-day close below stop → 50% re-entry; restore 100% next clean session."],
        papers=[VWAP, STOP_STUDY, FABER],
        verdict="Strict dominance vs the winner at 1/5/10 bp; the drawdown cut is robust, but the CAGR edge is not statistically strong.",
        curve=None, metrics=(0.6103, 0.3992, 0.5157, 0.2996),
    ),
    "overnight-crash-filter": dict(
        name="First-hour + crash filter", group="Round 2", status="Verified",
        tagline="Overnight + first hour, with a 35% vol crash filter.",
        summary="Hold TQQQ from 15:59 to 10:30 while QQQ is above its 165-day SMA. Skip the overnight when QQQ 20-day vol > 35%; hold the afternoon only if the first-hour return ≥ −0.5%.",
        rules=["QQQ 165-day regime with a 2% band.",
               "TQQQ 15:59 → 10:30; skip if 20-day vol > 35%.",
               "Afternoon only if QQQ first-hour return ≥ −0.5%; 4% stop."],
        papers=[CLIFF, LOU, GAO, FINLAB_DECAY, ELM_NIGHT],
        verdict="67.47% / 36.52% (10y) and 51.55% / 35.92% (5y). Strong 10y; the 5y drawdown is 2.4 pp worse than the round-1 winner.",
        curve="a17", metrics=(0.6747, 0.3652, 0.5155, 0.3592),
    ),
    "ml-crash-overlay-winner": dict(
        name="ML crash overlay", group="Round 2", status="Fragile",
        tagline="A walk-forward 20-day crash classifier on the winner.",
        summary="A logistic model estimates P(TQQQ 20-session return < −15%) from 34 causal 1m-derived features. If the trailing rank is ≥ 0.90, the next session is BIL.",
        rules=["Base: round-1 winner.",
               "750-session rolling logistic, annual retrain, 21-session purge.",
               "Rank ≥ 0.90 → BIL for the next session."],
        papers=[BAILEY, ARNOTT, LOPEZ_HRP],
        verdict="Headline 72.24% / 41.50% (10y) and 53.10% / 31.67% (5y), but OOS AUC is near 0.50 and the edge is concentrated in 2020/2026. Do not treat it as confirmed.",
        curve=None, metrics=(0.7224, 0.4150, 0.5310, 0.3167),
    ),
    "dynamic-leverage-throttle": dict(
        name="Dynamic leverage", group="Round 2", status="Alternative",
        tagline="30% TQQQ core + 70% 65%-vol-target sleeve.",
        summary="Keep a 30% permanent TQQQ core and run a 70% sleeve at a 65% volatility target, with BIL as the residual. The winner's armed 4% minute stop is applied on top.",
        rules=["30% TQQQ core.",
               "70% sleeve: 65% annualized vol target, 20-day lookback.",
               "Residual BIL; winner's 4% minute stop."],
        papers=[MOREIRA, CEDERBURG, MAN_VOL, ASNESS],
        verdict="5y strict dominance; 10y CAGR is 1.75 pp below the winner with 3.24 pp less drawdown. Calmar improves.",
        curve=None, metrics=(0.5705, 0.4132, 0.5012, 0.3016),
    ),
    "letf-rebalance-flow": dict(
        name="Late-rally overlay", group="Round 2", status="Fragile",
        tagline="Buy the last hour of a risk-off rally; exit before the close.",
        summary="On risk-off sessions where QQQ is up more than 1.5% by 14:59, buy TQQQ at 15:00 and sell at 15:59. The overnight after those rallies is negative on average.",
        rules=["Risk-off: QQQ ≤ 165-day SMA.",
               "At 14:59, run60 = QQQ / prior close − 1 > +1.5%.",
               "Buy TQQQ 15:00, sell 15:59; BIL overnight."],
        papers=[LETF_REBAL, LENKEY, CHENG],
        verdict="67.92% / 41.50% (10y) and 59.44% / 33.49% (5y); the threshold surface is broad, but entry-time falsification shows the effect is afternoon continuation, not uniquely a last-hour flow.",
        curve=None, metrics=(0.6792, 0.4150, 0.5944, 0.3349),
    ),
    "ratio-pairs": dict(
        name="Ratio froth", group="Round 2", status="Leader",
        tagline="Hold QQQ instead of TQQQ when the leverage ratio is extremely extended.",
        summary="The TQQQ/QQQ ratio records both how far QQQ has run and how cheap the leverage was. When its log extension above the 200-day MA exceeds 0.18, hold QQQ instead of TQQQ; otherwise run the round-1 winner.",
        rules=["Base: round-1 winner.",
               "ext = log((TQQQ/QQQ) / 200-day MA).",
               "If prior ext > 0.18, hold QQQ for the next session; the 4% stop stays active."],
        papers=[AVELLANEDA, BRUNNERMEIER, CHENG, FINLAB_DECAY],
        verdict="Current leader: 69.50% / 39.11% (10y) and 63.74% / 26.85% (5y); 27/27 rolling 3-year windows beat TQQQ on both return and drawdown. It is a fat-tail crash hedge, not stable daily alpha.",
        curve="a21", metrics=(0.6950, 0.3911, 0.6374, 0.2685),
    ),
    "intraday-seasonality": dict(
        name="Late-day de-risk", group="Round 2", status="Verified",
        tagline="Step aside for 30 minutes when a risk-on day is down 1% at 15:00.",
        summary="On risk-on sessions where QQQ is more than 1% below its 09:30 open at 15:00, sell TQQQ at 15:01 and buy back at 15:30. The rest of the time run the winner.",
        rules=["Risk-on session.",
               "At 15:00, QQQ ≤ −1% vs the 09:30 open.",
               "TQQQ → BIL 15:01–15:30; then resume the winner's overnight hold."],
        papers=[GAO, LENKEY, LETF_REBAL],
        verdict="61.35% / 44.18% (10y) and 53.46% / 33.50% (5y). Beats the winner at 1 bp on 10y, but the 5y drawdown is flat and the edge is ~zero at 5 bp.",
        curve=None, metrics=(0.6135, 0.4418, 0.5346, 0.3350),
    ),
    "volume-orderflow": dict(
        name="Volume-armed stop", group="Round 2", status="Verified",
        tagline="Honour the 4% stop only when participation is at least normal.",
        summary="The stop is armed by the MA20 gate or by relative volume > 1.5, but it is honoured only when relative volume is > 1.0. In quiet tape, a 4% dip is less likely to be a real crash.",
        rules=["Base: round-1 winner.",
               "rvol = cumulative QQQ volume / prior-20-day same-time mean.",
               "Stop armed if (QQQ < MA20 × 1.01 or rvol > 1.5) and rvol > 1.0."],
        papers=[LLORENTE, GAO, LOU, CHENG],
        verdict="65.90% / 42.49% (10y) and 53.17% / 28.64% (5y); strictly dominates the round-1 winner at 1/5/10 bp. The 5y drawdown gain is one suppressed stop event — treat it as event-dependent.",
        curve="a23", metrics=(0.6590, 0.4249, 0.5317, 0.2864),
    ),
    "risk-parity-hrp": dict(
        name="Risk-parity vol target", group="Round 2", status="Alternative",
        tagline="A 70% volatility target with a TQQQ cap.",
        summary="Size TQQQ at min(1, 0.70 / 20-day vol), put the remainder in QQQ, and send stop proceeds to BIL. HRP itself collapses to BIL because QQQ/TQQQ correlation is 0.9995.",
        rules=["QQQ 165-day regime.",
               "TQQQ weight = min(1, 0.70 / σ_TQQQ,20d).",
               "Remainder QQQ; stop proceeds BIL."],
        papers=[LOPEZ_HRP, MOREIRA, ASNESS],
        verdict="56.99% / 42.28% (10y) and 50.06% / 30.50% (5y); 5y strict dominance at 1 bp, but 5/10 bp costs were not measured. Not promotable.",
        curve=None, metrics=(0.5699, 0.4228, 0.5006, 0.3050),
    ),
    "drawdown-regime": dict(
        name="Drawdown regime", group="Round 2", status="Alternative",
        tagline="Halve the stop when QQQ is already 8% below its high.",
        summary="De-risking on drawdown alone fails: forward returns rise with drawdown, and the 165-day SMA already moves to BIL. The one survivor halves the minute stop from 4% to 2% when QQQ is ≥8% below its high.",
        rules=["Base: round-1 winner.",
               "If QQQ is ≥8% below its 52-week high, use a 2% stop instead of 4%.",
               "Other drawdown thresholds were rejected."],
        papers=[FABER, MOREIRA, CEDERBURG],
        verdict="61.57% / 40.34% (10y) and 51.75% / 31.63% (5y); strict dominance, but the return edge is statistically weak (bootstrap p ≈ 0.26).",
        curve=None, metrics=(0.6157, 0.4034, 0.5175, 0.3163),
    ),
    "gap-fill-fade": dict(
        name="Gap-up fade", group="Round 2", status="Verified",
        tagline="Fade small gap-ups when the tape is weak; re-enter before the close.",
        summary="Standalone gap strategies fail. As an overlay, when the winner's stop is armed and QQQ gaps +0.15% to +0.50%, sell TQQQ at 09:31, hold BIL to the close, and re-enter at 15:59 unless TQQQ closed 4% below the open.",
        rules=["Risk-on; winner's stop is armed.",
               "QQQ gap between +0.15% and +0.50%.",
               "TQQQ → BIL 09:31–15:59; re-enter at 15:59 unless stopped."],
        papers=[GAP_STRATEGY, LOU, CLIFF],
        verdict="65.17% / 39.02% (10y) and 54.92% / 30.99% (5y); strict dominance at 1/5 bp, but the 5y pass is fragile at different arm gates.",
        curve=None, metrics=(0.6517, 0.3902, 0.5492, 0.3099),
    ),
    # Blends / portfolio constructions
    "ratio-first-blend": dict(
        name="Ratio + first-hour", group="Blend", status="Blend",
        tagline="50% ratio-froth sleeve + 50% first-hour sleeve.",
        summary="A fixed 50/50 blend of the two strongest round-2 sleeves. It has the best 10-year CAGR in the project and a lower 10-year drawdown than the ratio sleeve alone.",
        rules=["50% ratio-froth strategy.",
               "50% first-hour + volatility-filter strategy.",
               "2% rebalance band."],
        papers=[AVELLANEDA, GAO, LOU, NEWFOUND],
        verdict="69.95% / 36.16% (10y) and 58.47% / 29.72% (5y). Best 10y CAGR; the 5y return is lower than ratio alone.",
        curve="ratio+first", metrics=(0.6995, 0.3616, 0.5847, 0.2972),
    ),
    "first-volume-blend": dict(
        name="First-hour + volume", group="Blend", status="Blend",
        tagline="50% first-hour sleeve + 50% volume-armed stop.",
        summary="A fixed 50/50 blend of the first-hour and volume-stop sleeves. It has the lowest 10-year drawdown among the high-return blends.",
        rules=["50% first-hour + crash-filter strategy.",
               "50% volume-armed stop strategy.",
               "2% rebalance band."],
        papers=[CLIFF, LLORENTE, NEWFOUND],
        verdict="67.83% / 35.63% (10y) and 53.10% / 32.02% (5y). Good balance, but lower 5y CAGR than ratio alone.",
        curve="first+volume", metrics=(0.6783, 0.3563, 0.5310, 0.3202),
    ),
    "ratio-volume-blend": dict(
        name="Ratio + volume", group="Blend", status="Blend",
        tagline="50% ratio-froth sleeve + 50% volume-armed stop.",
        summary="A fixed 50/50 blend of the ratio-froth and volume-stop sleeves. It is highly correlated with ratio alone and does not improve the 5-year drawdown.",
        rules=["50% ratio-froth strategy.",
               "50% volume-armed stop strategy.",
               "2% rebalance band."],
        papers=[AVELLANEDA, LLORENTE, NEWFOUND],
        verdict="68.14% / 40.80% (10y) and 58.69% / 27.74% (5y); not better than ratio alone.",
        curve="ratio+volume", metrics=(0.6814, 0.4080, 0.5869, 0.2774),
    ),
}

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def extract_links(text: str):
    found = []
    for label, url in re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", text):
        found.append((label.strip(), url.strip()))
    for url in re.findall(r"(?<!\()(https?://[^\s)>\"']+)", text):
        url = url.rstrip(".,;:)")
        if url not in {u for _, u in found}:
            found.append((url.split("/")[2].replace("www.", ""), url))
    return found


def find_report(slug: str):
    for base in (ROOT / "research" / "agents", ROOT / "research" / "agents2"):
        path = base / slug / "report.md"
        if path.exists():
            return path
    return None


def find_code(slug: str):
    for base in (ROOT / "research" / "agents", ROOT / "research" / "agents2"):
        path = base / slug / "strategy.py"
        if path.exists():
            return path
    return CODE_OVERRIDES.get(slug)


def load_audit(slug: str):
    for base in (ROOT / "research" / "agents", ROOT / "research" / "agents2"):
        path = base / slug / "web_audit.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
    return None


def main():
    REPORT_OUT.mkdir(parents=True, exist_ok=True)
    CODE_OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for slug, meta in M.items():
        report = find_report(slug)
        report_url = None
        if report:
            shutil.copyfile(report, REPORT_OUT / f"{slug}.md")
            report_url = f"/research/{slug}.md"
            text = report.read_text(encoding="utf-8", errors="replace")
            links = extract_links(text)
        else:
            links = []

        code = find_code(slug)
        code_url = None
        if code and code.exists():
            shutil.copyfile(code, CODE_OUT / f"{slug}.py")
            code_url = f"/research/code/{slug}.py"

        audit = load_audit(slug)
        provenance = audit.get("sources", []) if audit else []
        rejected = audit.get("rejected_sources", []) if audit else []
        corrections = audit.get("corrections", []) if audit else []

        papers = list(meta.get("papers", []))
        seen = {url for _, url in papers}
        for label, url in links:
            if url in seen:
                continue
            if len(papers) >= 9:
                break
            if any(bad in url for bad in ("localhost", "opencode", "127.0.0.1")):
                continue
            papers.append((label[:90], url))
            seen.add(url)
        for source in provenance:
            url = source.get("url")
            if url and url not in seen:
                papers.append((str(source.get("source", "Source"))[:90], url))
                seen.add(url)

        base_rules = meta["rules"]
        rules = audit.get("rules") if audit and audit.get("rules") else base_rules
        decision = (
            (audit.get("decision_process") if audit else None)
            or (audit.get("decision") if audit else None)
            or meta.get("decision")
            or (
                "Each session the strategy evaluates these checks in order: "
                + " ".join(f"({i + 1}) {rule}" for i, rule in enumerate(rules))
                + " Signals use only data through the current bar; the resulting target is filled "
                "at the next bar's open. A position is held until a later check changes it."
            )
        )
        c10, d10, c5, d5 = meta["metrics"]
        m = audit.get("metrics", {}) if audit else {}

        def metric(key: str, fallback):
            value = m.get(key)
            return fallback if value is None else float(value)

        metrics = {
            "cagr10": metric("cagr10", c10),
            "dd10": metric("dd10", d10),
            "cagr5": metric("cagr5", c5),
            "dd5": metric("dd5", d5),
        }
        for key in ("cagr10_5bp", "dd10_5bp", "cagr5_5bp", "dd5_5bp"):
            value = m.get(key)
            if value is not None:
                metrics[key] = float(value)

        status = (audit.get("status") if audit else None) or meta["status"]
        if status == "Leader" and slug != "ratio-pairs":
            status = "Verified"

        records.append({
            "slug": slug,
            "name": (audit.get("name") if audit else None) or meta["name"],
            "group": meta["group"],
            "status": status,
            "tagline": (audit.get("tagline") if audit else None) or meta["tagline"],
            "summary": (audit.get("summary") if audit else None) or meta["summary"],
            "decision": decision,
            "rules": rules,
            "verdict": (audit.get("verdict") if audit else None) or meta["verdict"],
            "metrics": metrics,
            "papers": [{"label": label, "url": url} for label, url in papers],
            "provenance": provenance,
            "rejectedSources": rejected,
            "corrections": corrections,
            "reportUrl": report_url,
            "codeUrl": code_url,
            "curve": meta.get("curve"),
        })

    order = {"Leader": 0, "Verified": 1, "Alternative": 2, "Blend": 3, "Fragile": 4, "Negative": 5}
    records.sort(key=lambda r: (order.get(r["status"], 9), -r["metrics"]["cagr10"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated": "2026-11-25",
        "strategies": records,
    }, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB) with {len(records)} strategies")
    print(f"reports copied to {REPORT_OUT}")


if __name__ == "__main__":
    main()
