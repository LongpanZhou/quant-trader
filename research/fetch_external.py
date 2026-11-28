"""Fetch daily cross-asset series from Yahoo for new-family research.

Writes `data/external/<symbol>.parquet` with date/open/high/low/close/adjclose/volume.
The TQQQ execution panel remains the local 1-minute QQQ/TQQQ/BIL data.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "external"
SYMBOLS = [
    "^VIX", "^VIX3M", "^TNX", "^IRX", "^TYX", "^FVX", "^MOVE",
    "^SKEW", "^VVIX",
    "TLT", "IEF", "SHY", "HYG", "LQD", "TIP", "UUP", "GLD", "USO", "CPER",
    "XLU", "XLK", "XLE", "XLF", "IWM", "EEM", "EFA", "RSP", "SPY",
    "QUAL", "MTUM", "GDX", "SLV", "SMH", "XBI", "XHB", "XRT",
    "BTC-USD", "JPY=X",
]
P1, P2 = 1420070400, 1790000000  # 2015-01-01 .. 2026-10


def fetch(symbol: str) -> pd.DataFrame:
    q = urllib.parse.quote(symbol)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{q}"
           f"?period1={P1}&period2={P2}&interval=1d&events=div%2Csplits")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    result = payload["chart"]["result"][0]
    ts = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert("America/New_York")
    q = result["indicators"]["quote"][0]
    adj = result["indicators"].get("adjclose", [{}])[0].get("adjclose", q["close"])
    df = pd.DataFrame({
        "date": ts.tz_localize(None).normalize(),
        "open": q["open"], "high": q["high"], "low": q["low"],
        "close": q["close"], "adjclose": adj, "volume": q["volume"],
    }).dropna(subset=["close"]).drop_duplicates("date").sort_values("date")
    return df


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for symbol in SYMBOLS:
        path = OUT / f"{symbol.replace('^', '').replace('=', '_')}.parquet"
        if path.exists():
            print(f"{symbol}: cached")
            continue
        try:
            df = fetch(symbol)
            df.to_parquet(path, index=False)
            print(f"{symbol}: {len(df)} rows {df.date.min().date()}..{df.date.max().date()}")
        except Exception as exc:
            print(f"{symbol}: FAILED {exc}")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
