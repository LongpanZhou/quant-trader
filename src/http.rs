use anyhow::{anyhow, Result};
use serde_json::Value;
use std::time::Duration;

pub fn agent() -> ureq::Agent {
    ureq::AgentBuilder::new()
        .timeout_connect(Duration::from_secs(10))
        .timeout(Duration::from_secs(30))
        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) quant-trader/0.1")
        .build()
}

/// Run a request and parse the JSON body, turning HTTP errors into readable messages.
pub fn json(result: std::result::Result<ureq::Response, ureq::Error>) -> Result<Value> {
    match result {
        Ok(resp) => {
            let text = resp.into_string()?;
            if text.trim().is_empty() {
                return Ok(Value::Null);
            }
            Ok(serde_json::from_str(&text)?)
        }
        Err(ureq::Error::Status(code, resp)) => {
            let url = resp.get_url().split('?').next().unwrap_or("").to_string();
            let body = resp.into_string().unwrap_or_default();
            let body: String = body.chars().take(300).collect();
            Err(anyhow!("HTTP {code} from {url}: {body}"))
        }
        Err(e) => Err(anyhow!("network error: {e}")),
    }
}

/// Read a number that may be encoded as a JSON number or a string.
pub fn num(v: &Value) -> Option<f64> {
    match v {
        Value::Number(n) => n.as_f64(),
        Value::String(s) => s.parse().ok(),
        _ => None,
    }
}
