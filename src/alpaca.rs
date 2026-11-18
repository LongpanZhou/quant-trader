//! Alpaca paper-trading account + real-time market data.
//! Docs: https://docs.alpaca.markets

use crate::config::{AlpacaConfig, Timeframe};
use crate::http::{self, num};
use crate::types::{Account, Bar, Fill, Position, Side};
use anyhow::{anyhow, bail, Result};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::time::Duration;

// Hard-wired to the PAPER endpoint: this program can never place live orders.
const TRADE_URL: &str = "https://paper-api.alpaca.markets";
const DATA_URL: &str = "https://data.alpaca.markets";

pub struct Alpaca {
    agent: ureq::Agent,
    key: String,
    secret: String,
    feed: String,
}

impl Alpaca {
    pub fn new(cfg: &AlpacaConfig) -> Self {
        Alpaca {
            agent: http::agent(),
            key: cfg.key_id.clone(),
            secret: cfg.secret_key.clone(),
            feed: cfg.feed.clone(),
        }
    }

    fn get(&self, url: &str, query: &[(&str, &str)]) -> Result<Value> {
        let mut req = self
            .agent
            .get(url)
            .set("APCA-API-KEY-ID", &self.key)
            .set("APCA-API-SECRET-KEY", &self.secret);
        for (k, v) in query {
            req = req.query(k, v);
        }
        http::json(req.call())
    }

    pub fn account(&self) -> Result<Account> {
        let v = self.get(&format!("{TRADE_URL}/v2/account"), &[])?;
        match (num(&v["cash"]), num(&v["equity"])) {
            (Some(cash), Some(equity)) => Ok(Account { cash, equity }),
            _ => Err(anyhow!("unexpected account response: {v}")),
        }
    }

    pub fn positions(&self) -> Result<HashMap<String, Position>> {
        let v = self.get(&format!("{TRADE_URL}/v2/positions"), &[])?;
        let mut out = HashMap::new();
        for p in v.as_array().cloned().unwrap_or_default() {
            if let (Some(sym), Some(qty), Some(avg)) =
                (p["symbol"].as_str(), num(&p["qty"]), num(&p["avg_entry_price"]))
            {
                out.insert(sym.to_string(), Position { qty, avg_price: avg });
            }
        }
        Ok(out)
    }

    pub fn market_open(&self) -> Result<bool> {
        let v = self.get(&format!("{TRADE_URL}/v2/clock"), &[])?;
        v["is_open"].as_bool().ok_or_else(|| anyhow!("unexpected clock response: {v}"))
    }

    /// Unix time of the next market close.
    pub fn session_close(&self) -> Result<i64> {
        let v = self.get(&format!("{TRADE_URL}/v2/clock"), &[])?;
        v["next_close"]
            .as_str()
            .and_then(|t| chrono::DateTime::parse_from_rfc3339(t).ok())
            .map(|t| t.timestamp())
            .ok_or_else(|| anyhow!("unexpected clock response: {v}"))
    }

    pub fn bars(&self, symbol: &str, tf: Timeframe, days: i64) -> Result<Vec<Bar>> {
        let start = (chrono::Utc::now() - chrono::Duration::days(days.max(1)))
            .format("%Y-%m-%dT%H:%M:%SZ")
            .to_string();
        let url = format!("{DATA_URL}/v2/stocks/{symbol}/bars");
        let mut out = Vec::new();
        let mut page: Option<String> = None;
        loop {
            let mut q = vec![
                ("timeframe", tf.alpaca()),
                ("start", start.as_str()),
                ("limit", "10000"),
                ("adjustment", "split"),
                ("feed", self.feed.as_str()),
                ("sort", "asc"),
            ];
            if let Some(p) = &page {
                q.push(("page_token", p.as_str()));
            }
            let v = self.get(&url, &q)?;
            for b in v["bars"].as_array().cloned().unwrap_or_default() {
                let ts = b["t"]
                    .as_str()
                    .and_then(|t| chrono::DateTime::parse_from_rfc3339(t).ok())
                    .map(|t| t.timestamp());
                if let (Some(ts), Some(open), Some(high), Some(low), Some(close)) =
                    (ts, num(&b["o"]), num(&b["h"]), num(&b["l"]), num(&b["c"]))
                {
                    out.push(Bar { ts, open, high, low, close, volume: num(&b["v"]).unwrap_or(0.0) });
                }
            }
            match v["next_page_token"].as_str() {
                Some(t) if !t.is_empty() => page = Some(t.to_string()),
                _ => break,
            }
        }
        Ok(out)
    }

    pub fn last_price(&self, symbol: &str) -> Result<f64> {
        let v = self.get(
            &format!("{DATA_URL}/v2/stocks/{symbol}/trades/latest"),
            &[("feed", self.feed.as_str())],
        )?;
        num(&v["trade"]["p"]).ok_or_else(|| anyhow!("no latest trade for {symbol}"))
    }

    /// Submit a market order and wait briefly for the fill.
    pub fn submit(&self, symbol: &str, side: Side, qty: f64) -> Result<Fill> {
        let order = http::json(
            self.agent
                .post(&format!("{TRADE_URL}/v2/orders"))
                .set("APCA-API-KEY-ID", &self.key)
                .set("APCA-API-SECRET-KEY", &self.secret)
                .send_json(json!({
                    "symbol": symbol,
                    "qty": qty.to_string(),
                    "side": side.as_str(),
                    "type": "market",
                    "time_in_force": "day",
                })),
        )?;
        let id = order["id"]
            .as_str()
            .ok_or_else(|| anyhow!("order rejected: {order}"))?
            .to_string();

        let mut status = String::new();
        for _ in 0..10 {
            std::thread::sleep(Duration::from_millis(700));
            let o = self.get(&format!("{TRADE_URL}/v2/orders/{id}"), &[])?;
            status = o["status"].as_str().unwrap_or("").to_string();
            match status.as_str() {
                "filled" => {
                    return Ok(Fill {
                        qty: num(&o["filled_qty"]).unwrap_or(qty),
                        price: num(&o["filled_avg_price"]).unwrap_or(0.0),
                    })
                }
                "canceled" | "expired" | "rejected" => bail!("order {id} was {status}"),
                _ => {}
            }
        }
        // Don't leave an unfilled order working: it could fill later and
        // double up with the next signal.
        let _ = self
            .agent
            .delete(&format!("{TRADE_URL}/v2/orders/{id}"))
            .set("APCA-API-KEY-ID", &self.key)
            .set("APCA-API-SECRET-KEY", &self.secret)
            .call();
        bail!("order {id} not filled in time (status '{status}'), cancel requested")
    }
}
