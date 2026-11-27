"""5-year 1-minute backtest of the Nasdaq Leveraged Trend rule.

Data
----
1-minute OHLCV bars for QQQ, TQQQ and BIL are downloaded from the free
Hugging Face dataset `syncster-data/historical-market-data`
(https://huggingface.co/datasets/syncster-data/historical-market-data).
That dataset is third-party research data, licensed "other"; it is stored
under `data/intraday-hf/` (gitignored) and is not redistributed by this repo.

The 1-minute prices are adjusted for dividends and splits with Yahoo Finance
daily `adjclose / close` factors. QQQ/TQQQ are already split-adjusted in the
source; BIL has a 1:2 reverse split on 2017-11-30, which is repaired here.

Strategy
--------
The same rule as the promoted daily strategy:
  - QQQ above its 165-day SMA -> target 40% annualised volatility, capped at 3x
  - otherwise -> BIL
  - 2% rebalance band, next-bar-open fills, 1 bp slippage (configurable)

The script reports two runs over the same window:
  1. decisions every 1 minute
  2. decisions once per day (validation of the simulator against the Rust
     daily engine)

Run:
  python scripts/intraday_1m_backtest.py --download
  python scripts/intraday_1m_backtest.py --start 2021-10-25 --end 2026-10-23
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
    import pyarrow  # noqa: F401
except ModuleNotFoundError as error:
    raise SystemExit(
        "Missing dependency. Install the research extras first:\n"
        "  pip install -r scripts/requirements-intraday.txt"
    ) from error

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "intraday-hf"
HF_BASE = (
    "https://huggingface.co/datasets/syncster-data/historical-market-data/"
    "resolve/main/data/stocks/1m/{first}/{symbol}.parquet?download=true"
)
YAHOO_DAILY = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?period1={start}&period2={end}&interval=1d"
    "&events=div%2Csplit&includeAdjustedClose=true"
)
SYMBOLS = ("QQQ", "TQQQ", "BIL")
START_EQUITY = 100_000.0
SMA_DAYS = 165
VOL_DAYS = 20
TARGET_VOL = 0.40
LEVERAGE = 3.0


def download_file(url: str, path: Path) -> None:
    if path.exists() and path.stat().st_size > 0:
        print(f"  exists  {path.relative_to(ROOT)}")
        return
    print(f"  download {path.relative_to(ROOT)}")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=180) as response:
        path.write_bytes(response.read())
    print(f"  saved   {path.relative_to(ROOT)} ({path.stat().st_size / 1e6:.1f} MB)")


def download_yahoo_daily(symbol: str, path: Path, start: str, end: str) -> None:
    if path.exists() and path.stat().st_size > 0:
        print(f"  exists  {path.relative_to(ROOT)}")
        return
    start_ts = int(pd.Timestamp(start, tz="UTC").timestamp())
    end_ts = int(pd.Timestamp(end, tz="UTC").timestamp()) + 2 * 86400
    url = YAHOO_DAILY.format(symbol=symbol, start=start_ts, end=end_ts)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) quant-trader/0.1",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.load(response)
    result = body["chart"]["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    adjusted = result["indicators"]["adjclose"][0]["adjclose"]
    rows = []
    for index, timestamp in enumerate(timestamps):
        close = quote["close"][index]
        adjclose = adjusted[index]
        if close is None or adjclose is None:
            continue
        rows.append(
            {
                "date": pd.to_datetime(timestamp, unit="s", utc=True)
                .tz_convert("America/New_York")
                .date(),
                "open": quote["open"][index],
                "high": quote["high"][index],
                "low": quote["low"][index],
                "close": close,
                "adjclose": adjclose,
                "volume": quote["volume"][index],
            }
        )
    pd.DataFrame(rows).to_parquet(path, index=False)
    print(f"  saved   {path.relative_to(ROOT)} ({len(rows):,} daily bars)")


def ensure_data(start: str, end: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Data directory: {DATA_DIR.relative_to(ROOT)}")
    for symbol in SYMBOLS:
        download_file(
            HF_BASE.format(first=symbol[0], symbol=symbol),
            DATA_DIR / f"{symbol}-1m.parquet",
        )
        download_yahoo_daily(
            symbol,
            DATA_DIR / f"{symbol}-1d-yahoo.parquet",
            "2015-01-01",
            end,
        )


def load_1m(symbol: str) -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / f"{symbol}-1m.parquet")
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert("America/New_York")
    df = df[
        (df["ts"].dt.time >= pd.Timestamp("09:30").time())
        & (df["ts"].dt.time < pd.Timestamp("16:00").time())
    ].copy()
    df["date"] = df["ts"].dt.date

    # The source BIL bars are not split-adjusted. BIL had a 1:2 reverse split
    # on 2017-11-30; bring older prices onto the current share basis.
    if symbol == "BIL":
        before = df["date"] < pd.Timestamp("2017-11-30").date()
        for column in ("open", "high", "low", "close"):
            df.loc[before, column] *= 2.0

    daily = pd.read_parquet(DATA_DIR / f"{symbol}-1d-yahoo.parquet")
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    daily["factor"] = daily["adjclose"] / daily["close"]
    df = df.merge(daily[["date", "factor"]], on="date", how="left")
    df["factor"] = df["factor"].ffill().bfill()
    for column in ("open", "high", "low", "close"):
        df[column] = df[column] * df["factor"]
    return df[["ts", "date", "open", "high", "low", "close", "volume"]]


def target_weights(
    close: np.ndarray, bars_per_day: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(close)
    sma_bars = SMA_DAYS * bars_per_day
    vol_bars = VOL_DAYS * bars_per_day
    sma = pd.Series(close).rolling(sma_bars, min_periods=sma_bars).mean().to_numpy()
    returns = pd.Series(close).pct_change().to_numpy()
    vol = (
        pd.Series(returns)
        .rolling(vol_bars, min_periods=vol_bars)
        .std(ddof=0)
        .to_numpy()
        * np.sqrt(252.0 * bars_per_day)
    )
    exposure = np.where(vol > 1e-9, np.minimum(TARGET_VOL / vol, LEVERAGE), 1.0)

    w_qqq = np.zeros(n)
    w_tqqq = np.zeros(n)
    w_bil = np.zeros(n)
    trend = (close > sma) & ~np.isnan(sma)
    w_bil[~trend] = 1.0

    index = np.flatnonzero(trend)
    if len(index):
        e = exposure[index]
        above_one = e >= 1.0
        risk = np.clip((e[above_one] - 1.0) / (LEVERAGE - 1.0), 0.0, 1.0)
        w_tqqq[index[above_one]] = risk
        w_qqq[index[above_one]] = 1.0 - risk
        w_qqq[index[~above_one]] = e[~above_one]
        w_bil[index[~above_one]] = 1.0 - e[~above_one]
    return w_qqq, w_tqqq, w_bil


def simulate(
    timestamps: pd.DatetimeIndex,
    opens: np.ndarray,
    closes: np.ndarray,
    targets: tuple[np.ndarray, np.ndarray, np.ndarray],
    bars_per_year: float,
    band: float,
    slippage_bps: float,
) -> dict:
    n = len(timestamps)
    w_qqq, w_tqqq, w_bil = targets
    slippage = slippage_bps / 10_000.0
    cash = START_EQUITY
    shares = np.zeros(3)
    average_cost = np.zeros(3)
    partial_pnl = np.zeros(3)
    equity = np.full(n, np.nan)
    cash_curve = np.full(n, np.nan)
    trade_pnls: list[float] = []
    fills = 0
    traded = 0.0
    realized = 0.0
    wins = losses = flat = 0

    def trade(i: int, target: np.ndarray) -> None:
        nonlocal cash, fills, traded, realized, wins, losses, flat
        price_open = opens[i]
        book = cash + float(np.dot(shares, price_open))
        if not (book > 0):
            return

        # Exits and sell-side rebalances first.
        for s in range(3):
            if shares[s] <= 0:
                continue
            if target[s] == 0:
                quantity = shares[s]
            else:
                excess = shares[s] * price_open[s] - target[s] * book
                if excess <= band * book:
                    continue
                quantity = excess / price_open[s]
            quantity = min(quantity, shares[s])
            if quantity <= 0:
                continue
            price = price_open[s] * (1.0 - slippage)
            notional = quantity * price
            cash += notional
            traded += notional
            fills += 1
            pnl = quantity * (price - average_cost[s])
            realized += pnl
            partial_pnl[s] += pnl
            shares[s] -= quantity
            if shares[s] < 1e-10:
                shares[s] = 0.0
                closed_pnl = partial_pnl[s]
                if closed_pnl > 0.01:
                    wins += 1
                elif closed_pnl < -0.01:
                    losses += 1
                else:
                    flat += 1
                trade_pnls.append(closed_pnl)
                partial_pnl[s] = 0.0
                average_cost[s] = 0.0

        # Buys and buy-side rebalances.
        for s in range(3):
            if target[s] <= 0:
                continue
            current = shares[s] * price_open[s]
            shortfall = target[s] * book - current
            is_new = shares[s] <= 0
            if not is_new and shortfall <= band * book:
                continue
            if shortfall <= 0:
                continue
            price = price_open[s] * (1.0 + slippage)
            quantity = min(shortfall / price, cash / price)
            if quantity <= 1e-12:
                continue
            notional = quantity * price
            cash -= notional
            traded += notional
            fills += 1
            previous = shares[s]
            shares[s] = previous + quantity
            average_cost[s] = (
                average_cost[s] * previous + notional
            ) / shares[s]

    equity[0] = cash + float(np.dot(shares, closes[0]))
    cash_curve[0] = cash
    for i in range(n - 1):
        trade(i + 1, np.array([w_qqq[i], w_tqqq[i], w_bil[i]]))
        equity[i + 1] = cash + float(np.dot(shares, closes[i + 1]))
        cash_curve[i + 1] = cash

    returns = np.diff(equity) / equity[:-1]
    years = (timestamps[-1] - timestamps[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(equity)
    drawdown = equity / peak - 1.0
    downside = np.minimum(returns, 0.0)
    closed = wins + losses + flat
    trade_array = np.array(trade_pnls)
    return {
        "timestamps": timestamps,
        "equity": equity,
        "total_return": equity[-1] / equity[0] - 1.0,
        "cagr": (equity[-1] / equity[0]) ** (1.0 / years) - 1.0,
        "max_drawdown": -drawdown.min(),
        "volatility": np.std(returns, ddof=0) * np.sqrt(bars_per_year),
        "sharpe": (
            np.mean(returns) / np.std(returns, ddof=0) * np.sqrt(bars_per_year)
            if np.std(returns) > 0
            else 0.0
        ),
        "sortino": (
            np.mean(returns)
            / np.sqrt(np.mean(downside**2))
            * np.sqrt(bars_per_year)
            if np.mean(downside**2) > 0
            else 0.0
        ),
        "exposure": np.mean((equity - cash_curve) / equity),
        "fills": fills,
        "turnover": traded / START_EQUITY,
        "closed_trades": closed,
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "realized_pnl": realized,
        "trade_pnls": trade_array,
        "years": years,
    }


def benchmark(close: np.ndarray, timestamps: pd.DatetimeIndex, bars_per_year: float) -> dict:
    returns = np.diff(close) / close[:-1]
    years = (timestamps[-1] - timestamps[0]).total_seconds() / (365.25 * 86400)
    peak = np.maximum.accumulate(close)
    return {
        "cagr": (close[-1] / close[0]) ** (1.0 / years) - 1.0,
        "max_drawdown": -(close / peak - 1.0).min(),
    }


def print_result(label: str, result: dict, bench: dict) -> None:
    print(f"\n=== {label} ===")
    print(
        f"period              {result['timestamps'][0]} -> {result['timestamps'][-1]}"
        f"  ({result['years']:.2f} years, {len(result['timestamps']):,} bars)"
    )
    print(f"total return        {result['total_return']*100:+.2f}%")
    print(f"CAGR                {result['cagr']*100:+.2f}%")
    print(f"QQQ CAGR            {bench['cagr']*100:+.2f}%")
    print(f"excess vs QQQ       {(result['cagr'] - bench['cagr'])*100:+.2f} pp/yr")
    print(
        f"max drawdown        {result['max_drawdown']*100:.2f}%"
        f"  (QQQ {bench['max_drawdown']*100:.2f}%)"
    )
    print(f"volatility (ann.)   {result['volatility']*100:.2f}%")
    print(f"Sharpe              {result['sharpe']:.2f}")
    print(f"Sortino             {result['sortino']:.2f}")
    print(f"avg exposure        {result['exposure']*100:.1f}%")
    print(
        f"closed trades       {result['closed_trades']:,}"
        f"  ({result['wins']} wins / {result['losses']} losses / {result['flat']} flat)"
    )
    print(f"fills / turnover    {result['fills']:,} / {result['turnover']:.1f}x")
    print(f"realized P&L        ${result['realized_pnl']:,.0f}")
    print(f"ending equity       ${result['equity'][-1]:,.0f}")
    pnls = result["trade_pnls"]
    if len(pnls):
        print(
            f"trade P&L           median ${np.median(pnls):,.0f}"
            f"  mean ${pnls.mean():,.0f}"
            f"  min ${pnls.min():,.0f}  max ${pnls.max():,.0f}"
        )


def run(start: str, end: str, band: float, slippage_bps: float, sensitivity: bool) -> None:
    start_ts = pd.Timestamp(start, tz="America/New_York")
    end_ts = pd.Timestamp(end, tz="America/New_York").normalize() + pd.Timedelta(days=1)

    qqq_full = load_1m("QQQ").set_index("ts")
    tqqq_full = load_1m("TQQQ").set_index("ts")
    qqq_full = qqq_full[qqq_full.index < end_ts]
    tqqq_full = tqqq_full[tqqq_full.index < end_ts]
    targets_full = target_weights(qqq_full["close"].to_numpy(), 390)
    start_full = int(qqq_full.index.searchsorted(start_ts))
    print(
        f"warmup available: {start_full:,} bars before {start_ts}"
        f" (need {SMA_DAYS * 390:,})"
    )

    qqq = qqq_full[qqq_full.index >= start_ts]
    tqqq = tqqq_full[tqqq_full.index >= start_ts]
    if not qqq.index.equals(tqqq.index):
        tqqq = tqqq.reindex(qqq.index).ffill().bfill()
    bil = load_1m("BIL")
    bil = bil[(bil["ts"] >= start_ts) & (bil["ts"] < end_ts)]
    bil = bil.set_index("ts").reindex(qqq.index).ffill().bfill()

    opens = np.column_stack(
        [qqq["open"].to_numpy(), tqqq["open"].to_numpy(), bil["open"].to_numpy()]
    )
    closes = np.column_stack(
        [qqq["close"].to_numpy(), tqqq["close"].to_numpy(), bil["close"].to_numpy()]
    )
    targets = tuple(array[start_full:] for array in targets_full)
    assert len(targets[0]) == len(qqq)

    minute_result = simulate(
        qqq.index, opens, closes, targets, 252.0 * 390, band, slippage_bps
    )
    minute_bench = benchmark(qqq["close"].to_numpy(), qqq.index, 252.0 * 390)
    print_result(
        f"Main strategy - 1-minute decisions, {band*100:.0f}% band, {slippage_bps:.0f} bp",
        minute_result,
        minute_bench,
    )

    results_dir = DATA_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"timestamp": minute_result["timestamps"], "equity": minute_result["equity"]}
    ).to_csv(results_dir / "main-1m-equity.csv", index=False)

    if sensitivity:
        print("\n=== 1-minute sensitivity: rebalance band (1 bp slippage) ===")
        for candidate in (0.02, 0.05, 0.10, 0.20):
            r = simulate(
                qqq.index, opens, closes, targets, 252.0 * 390, candidate, 1.0
            )
            print(
                f"band {candidate*100:>4.0f}%  CAGR {r['cagr']*100:>6.2f}%"
                f"  maxDD {r['max_drawdown']*100:>5.2f}%  Sharpe {r['sharpe']:>5.2f}"
                f"  fills {r['fills']:>6,}  turnover {r['turnover']:>7.1f}x"
            )
        print("\n=== 1-minute sensitivity: slippage (2% band) ===")
        for candidate in (0.0, 1.0, 5.0):
            r = simulate(
                qqq.index, opens, closes, targets, 252.0 * 390, 0.02, candidate
            )
            print(
                f"slip {candidate:>4.1f}bp  CAGR {r['cagr']*100:>6.2f}%"
                f"  maxDD {r['max_drawdown']*100:>5.2f}%  Sharpe {r['sharpe']:>5.2f}"
                f"  fills {r['fills']:>6,}  turnover {r['turnover']:>7.1f}x"
            )

    # Daily validation: resample the same adjusted 1m bars to one bar/day.
    def daily(frame: pd.DataFrame, name: str) -> pd.DataFrame:
        source = frame.reset_index() if "ts" in frame.columns else frame
        if "ts" not in source.columns:
            source = frame.copy()
            source["ts"] = frame.index
        out = source.groupby("date").agg(
            open=("open", "first"),
            close=("close", "last"),
        )
        out.index = pd.DatetimeIndex(pd.to_datetime(out.index)).tz_localize(
            "America/New_York"
        )
        out.columns = pd.MultiIndex.from_product([[name], out.columns])
        return out

    qqq_daily = daily(load_1m("QQQ"), "qqq")
    tqqq_daily = daily(load_1m("TQQQ"), "tqqq")
    bil_daily = daily(load_1m("BIL"), "bil")
    qqq_daily = qqq_daily[qqq_daily.index >= start_ts.normalize()]
    tqqq_daily = tqqq_daily.reindex(qqq_daily.index).ffill().bfill()
    bil_daily = bil_daily.reindex(qqq_daily.index).ffill().bfill()
    daily_targets = target_weights(qqq_daily[("qqq", "close")].to_numpy(), 1)
    daily_start = int(np.searchsorted(qqq_daily.index, start_ts.normalize()))
    daily_end = int(np.searchsorted(qqq_daily.index, end_ts.normalize()))
    daily_targets = tuple(array[daily_start:daily_end] for array in daily_targets)
    daily_opens = np.column_stack(
        [
            qqq_daily[("qqq", "open")],
            tqqq_daily[("tqqq", "open")],
            bil_daily[("bil", "open")],
        ]
    )[daily_start:daily_end]
    daily_closes = np.column_stack(
        [
            qqq_daily[("qqq", "close")],
            tqqq_daily[("tqqq", "close")],
            bil_daily[("bil", "close")],
        ]
    )[daily_start:daily_end]
    daily_ts = qqq_daily.index[daily_start:daily_end]
    daily_result = simulate(
        daily_ts, daily_opens, daily_closes, daily_targets, 252.0, band, slippage_bps
    )
    daily_bench = benchmark(daily_closes[:, 0], daily_ts, 252.0)
    print_result(
        "Main strategy - daily decisions from the same 1m data (validation)",
        daily_result,
        daily_bench,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Nasdaq Leveraged Trend rule on 1-minute QQQ/TQQQ/BIL data.",
        epilog="See the module docstring and README for data sources and caveats.",
    )
    parser.add_argument("--download", action="store_true", help="download missing data")
    parser.add_argument("--start", default="2021-10-25")
    parser.add_argument("--end", default="2026-10-23")
    parser.add_argument("--band", type=float, default=0.02)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--sensitivity", action="store_true")
    args = parser.parse_args()

    if args.download or not (DATA_DIR / "QQQ-1m.parquet").exists():
        ensure_data(args.start, args.end)

    run(args.start, args.end, args.band, args.slippage_bps, args.sensitivity)


if __name__ == "__main__":
    main()
