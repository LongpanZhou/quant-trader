//! Keyless market data from Yahoo Finance's public chart endpoint.

use crate::config::Timeframe;
use crate::http;
use crate::types::Bar;
use anyhow::{anyhow, Result};
use serde_json::Value;

/// Splits and dividends for one symbol, oldest first.
#[derive(Debug, Default, Clone)]
pub struct Events {
    /// (effective unix time, new shares per old share)
    pub splits: Vec<(i64, f64)>,
    /// (ex-date unix time, cash per share)
    pub dividends: Vec<(i64, f64)>,
}

pub struct Yahoo {
    agent: ureq::Agent,
}

fn now() -> i64 {
    chrono::Utc::now().timestamp()
}

impl Yahoo {
    pub fn new() -> Self {
        Yahoo { agent: http::agent() }
    }

    fn chart(&self, symbol: &str, interval: &str, from: i64, to: i64) -> Result<Value> {
        // Yahoo writes share classes with a dash (BRK-B), not a dot.
        let url = format!(
            "https://query1.finance.yahoo.com/v8/finance/chart/{}",
            symbol.replace('.', "-")
        );
        let mut attempt = 0;
        let v = loop {
            let res = http::json(
                self.agent
                    .get(&url)
                    .query("interval", interval)
                    .query("period1", &from.to_string())
                    .query("period2", &to.to_string())
                    .query("includePrePost", "false")
                    .query("events", "div,splits")
                    .call(),
            );
            match res {
                Ok(v) => break v,
                // Rate limits and network blips: back off and retry.
                Err(e) if attempt < 3 && !e.to_string().contains("HTTP 404") => {
                    attempt += 1;
                    std::thread::sleep(std::time::Duration::from_millis(1500 * attempt));
                }
                Err(e) => return Err(e),
            }
        };
        let result = &v["chart"]["result"][0];
        if result.is_null() {
            return Err(anyhow!("Yahoo returned no data for {symbol}: {}", v["chart"]["error"]));
        }
        Ok(result.clone())
    }

    /// Regular-session bars for the last `days` calendar days, oldest first.
    /// The final bar may still be forming.
    pub fn bars(&self, symbol: &str, tf: Timeframe, days: i64) -> Result<Vec<Bar>> {
        // Yahoo limits how far back intraday data can be requested.
        let max_days = match tf {
            Timeframe::M1 => 29,
            Timeframe::M5 | Timeframe::M15 => 59,
            Timeframe::H1 => 729,
            Timeframe::D1 => 36500,
        };
        // 1-minute history is only served a week at a time, so longer
        // ranges are fetched in several requests.
        let chunk = if tf == Timeframe::M1 { 7 * 86400 } else { i64::MAX };
        let to = now();
        let mut from = to - days.clamp(1, max_days) * 86400;
        let mut out = Vec::new();
        while from < to {
            let end = from.saturating_add(chunk).min(to);
            let r = self.chart(symbol, tf.yahoo(), from, end)?;
            let ts = r["timestamp"].as_array().cloned().unwrap_or_default();
            let q = &r["indicators"]["quote"][0];
            // Daily bars come with a dividend-adjusted close. Scaling each bar
            // by adjusted/raw makes the series a total-return series, so
            // dividends count for both the strategy and buy & hold. (The most
            // recent bars have a factor of 1, so live prices are unaffected.)
            let adj = &r["indicators"]["adjclose"][0]["adjclose"];
            for (i, t) in ts.iter().enumerate() {
                let get = |k: &str| q[k][i].as_f64();
                // Yahoo emits nulls for minutes with no trades; skip those.
                if let (Some(ts), Some(open), Some(high), Some(low), Some(close)) =
                    (t.as_i64(), get("open"), get("high"), get("low"), get("close"))
                {
                    let k = match adj[i].as_f64() {
                        Some(a) if tf == Timeframe::D1 && close > 0.0 && a > 0.0 => a / close,
                        _ => 1.0,
                    };
                    out.push(Bar {
                        ts,
                        open: open * k,
                        high: high * k,
                        low: low * k,
                        close: close * k,
                    });
                }
            }
            from = end;
        }
        out.sort_by_key(|b| b.ts);
        out.dedup_by_key(|b| b.ts);
        Ok(out)
    }

    /// Last market-data timestamp and the exchange's reported delay, in
    /// seconds. Used by preflight to catch a stale or delayed quote.
    pub fn quote_age(&self, symbol: &str) -> Result<(i64, i64)> {
        let to = now();
        let r = self.chart(symbol, "1d", to - 5 * 86400, to)?;
        let ts = r["meta"]["regularMarketTime"].as_i64().unwrap_or(0);
        let delay = r["meta"]["exchangeDataDelayedBy"].as_i64().unwrap_or(0).max(0) * 60;
        Ok((ts, delay))
    }

    /// Splits and dividends for `symbol` over the last `days` calendar days.
    /// Used to keep the paper ledger correct when a held fund splits or pays.
    pub fn events(&self, symbol: &str, days: i64) -> Result<Events> {
        let to = now();
        let from = to - days.clamp(1, 36500) * 86400;
        let r = self.chart(symbol, "1d", from, to)?;
        let mut out = Events::default();
        if let Some(splits) = r["events"]["splits"].as_object() {
            for v in splits.values() {
                if let (Some(date), Some(num), Some(den)) =
                    (v["date"].as_i64(), v["numerator"].as_f64(), v["denominator"].as_f64())
                {
                    if num > 0.0 && den > 0.0 && (num / den - 1.0).abs() > 1e-9 {
                        out.splits.push((date, num / den));
                    }
                }
            }
        }
        if let Some(divs) = r["events"]["dividends"].as_object() {
            for v in divs.values() {
                if let (Some(date), Some(amount)) = (v["date"].as_i64(), v["amount"].as_f64()) {
                    if amount > 0.0 {
                        out.dividends.push((date, amount));
                    }
                }
            }
        }
        out.splits.sort_by_key(|s| s.0);
        out.dividends.sort_by_key(|d| d.0);
        Ok(out)
    }

    pub fn last_price(&self, symbol: &str) -> Result<f64> {
        let to = now();
        let r = self.chart(symbol, "1d", to - 5 * 86400, to)?;
        r["meta"]["regularMarketPrice"]
            .as_f64()
            .ok_or_else(|| anyhow!("no price for {symbol}"))
    }

    /// Unix time at which the current (or most recent) regular session ends.
    /// Correct on half-days too.
    pub fn session_close(&self) -> Result<i64> {
        let to = now();
        let r = self.chart("SPY", "1d", to - 5 * 86400, to)?;
        r["meta"]["currentTradingPeriod"]["regular"]["end"]
            .as_i64()
            .ok_or_else(|| anyhow!("Yahoo response missing trading hours"))
    }

    /// True while the US regular session is in progress.
    pub fn market_open(&self) -> Result<bool> {
        let to = now();
        let r = self.chart("SPY", "1d", to - 5 * 86400, to)?;
        let reg = &r["meta"]["currentTradingPeriod"]["regular"];
        match (reg["start"].as_i64(), reg["end"].as_i64()) {
            (Some(s), Some(e)) => Ok(to >= s && to < e),
            _ => Err(anyhow!("Yahoo response missing trading hours")),
        }
    }
}
