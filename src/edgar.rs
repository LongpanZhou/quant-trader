//! Company financial reports from SEC EDGAR (free, official, no key).
//!
//! Every 10-Q / 10-K a US company files is published as structured data.
//! This module pulls quarterly net income for a company, works out when each
//! figure first became public (the filing date), and scores every report by
//! how surprising it was: SUE, "standardised unexpected earnings".
//!
//!   change = this quarter's profit - same quarter last year
//!   SUE    = (change - the company's usual change over the last 8 quarters)
//!            / (how much that change usually varies)
//!
//! A steadily growing company therefore scores near zero; only a quarter
//! that breaks its own pattern scores high or low.
//!
//! Net income is used rather than earnings per share because it is not
//! distorted by stock splits.

use crate::http;
use anyhow::{anyhow, Result};
use chrono::NaiveDate;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use std::path::PathBuf;
use std::time::{Duration, SystemTime};

/// One quarterly result. Dates are days since 1970-01-01.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct Quarter {
    pub period_end: i64,
    /// Day the report containing this figure was filed with the SEC.
    pub filed: i64,
    pub net_income: f64,
}

/// A filed report and how surprising its profit was.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Report {
    pub filed: i64,
    pub sue: f64,
}

fn day(s: &str) -> Option<i64> {
    let d = NaiveDate::parse_from_str(s, "%Y-%m-%d").ok()?;
    Some(d.signed_duration_since(NaiveDate::from_ymd_opt(1970, 1, 1)?).num_days())
}

/// Turn the raw EDGAR "NetIncomeLoss" facts into one figure per quarter.
pub fn quarters_from_facts(facts: &Value) -> Vec<Quarter> {
    // For each reporting period keep the figure from the earliest filing:
    // that is the date the number first became public.
    let mut periods: BTreeMap<(i64, i64), (i64, f64)> = BTreeMap::new();
    for f in facts["units"]["USD"].as_array().into_iter().flatten() {
        let form = f["form"].as_str().unwrap_or("");
        if !(form.starts_with("10-Q") || form.starts_with("10-K")) {
            continue;
        }
        let (Some(start), Some(end), Some(filed), Some(val)) = (
            f["start"].as_str().and_then(day),
            f["end"].as_str().and_then(day),
            f["filed"].as_str().and_then(day),
            f["val"].as_f64(),
        ) else {
            continue;
        };
        let e = periods.entry((start, end)).or_insert((filed, val));
        if filed < e.0 {
            *e = (filed, val);
        }
    }

    // Three-month periods are quarters as reported.
    let mut quarters: BTreeMap<i64, Quarter> = BTreeMap::new();
    for (&(start, end), &(filed, val)) in &periods {
        if (80..=100).contains(&(end - start)) {
            quarters.insert(end, Quarter { period_end: end, filed, net_income: val });
        }
    }
    // The fourth quarter is only reported inside the annual figure:
    // Q4 = full year - the three quarters already reported.
    for (&(start, end), &(filed, val)) in &periods {
        if !(350..=380).contains(&(end - start)) || quarters.contains_key(&end) {
            continue;
        }
        let inside: Vec<&Quarter> = quarters
            .range(start + 60..end - 60)
            .map(|(_, q)| q)
            .collect();
        if inside.len() == 3 {
            let q4 = val - inside.iter().map(|q| q.net_income).sum::<f64>();
            quarters.insert(end, Quarter { period_end: end, filed, net_income: q4 });
        }
    }
    quarters.into_values().collect()
}

/// Score each quarter against the same quarter a year earlier.
pub fn reports_from_quarters(quarters: &[Quarter]) -> Vec<Report> {
    // Year-over-year change for every quarter that has a year-ago match.
    let mut changes: Vec<(i64, f64)> = Vec::new(); // (filed, change)
    let mut out = Vec::new();
    for q in quarters {
        let Some(prev) = quarters
            .iter()
            .find(|p| (q.period_end - p.period_end - 365).abs() <= 20)
        else {
            continue;
        };
        let change = q.net_income - prev.net_income;
        // Typical size of past changes (up to the last 8, at least 4).
        let past: Vec<f64> = changes.iter().rev().take(8).map(|c| c.1).collect();
        if past.len() >= 4 {
            let mean = past.iter().sum::<f64>() / past.len() as f64;
            let sd = (past.iter().map(|c| (c - mean).powi(2)).sum::<f64>() / past.len() as f64).sqrt();
            if sd > 0.0 {
                // Surprise = how far this change is from the company's usual change.
                out.push(Report { filed: q.filed, sue: (change - mean) / sd });
            }
        }
        changes.push((q.filed, change));
    }
    out.sort_by_key(|r| r.filed);
    out
}

/// A balance-sheet figure at a point in time. Dates are days since 1970-01-01.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub struct Snapshot {
    pub period_end: i64,
    /// Day the report containing this figure was filed with the SEC.
    pub filed: i64,
    pub value: f64,
}

/// Turn raw EDGAR balance-sheet facts (e.g. "Assets") into one figure per
/// balance-sheet date, each dated by the first filing that contained it.
pub fn snapshots_from_facts(facts: &Value) -> Vec<Snapshot> {
    let mut by_date: BTreeMap<i64, (i64, f64)> = BTreeMap::new();
    for f in facts["units"]["USD"].as_array().into_iter().flatten() {
        let form = f["form"].as_str().unwrap_or("");
        if !(form.starts_with("10-Q") || form.starts_with("10-K")) {
            continue;
        }
        let (Some(end), Some(filed), Some(val)) =
            (f["end"].as_str().and_then(day), f["filed"].as_str().and_then(day), f["val"].as_f64())
        else {
            continue;
        };
        let e = by_date.entry(end).or_insert((filed, val));
        if filed < e.0 {
            *e = (filed, val);
        }
    }
    by_date
        .into_iter()
        .map(|(period_end, (filed, value))| Snapshot { period_end, filed, value })
        .collect()
}

/// Return on assets = profit over the last four quarters / total assets.
/// Each value is dated by when both inputs were public, so a backtest never
/// sees a figure before the market did.
pub fn return_on_assets(quarters: &[Quarter], assets: &[Snapshot]) -> Vec<(i64, f64)> {
    let mut out = Vec::new();
    for i in 3..quarters.len() {
        let q = &quarters[i];
        // Four consecutive quarters: the first ends about 9 months before the last.
        if !(250..=300).contains(&(q.period_end - quarters[i - 3].period_end)) {
            continue;
        }
        let profit: f64 = quarters[i - 3..=i].iter().map(|x| x.net_income).sum();
        // Balance sheet for the same date, or the latest one before it.
        let Some(a) = assets
            .iter()
            .rev()
            .find(|a| a.period_end <= q.period_end + 10 && q.period_end - a.period_end <= 120)
        else {
            continue;
        };
        if a.value > 0.0 {
            out.push((q.filed.max(a.filed), profit / a.value));
        }
    }
    out.sort_by_key(|x| x.0);
    out
}

pub struct Edgar {
    agent: ureq::Agent,
    user_agent: String,
    cache_dir: PathBuf,
}

impl Edgar {
    pub fn new(user_agent: &str, cache_dir: PathBuf) -> Self {
        Edgar { agent: http::agent(), user_agent: user_agent.to_string(), cache_dir }
    }

    /// One reported figure ("concept") for a company, parsed by `parse`.
    /// Served from the local cache when it is younger than `max_age`,
    /// otherwise downloaded from the SEC.
    fn concept<T: Serialize + serde::de::DeserializeOwned>(
        &self,
        symbol: &str,
        cik: u64,
        concept: &str,
        cache_suffix: &str,
        max_age: Duration,
        parse: fn(&Value) -> T,
    ) -> Result<T> {
        let path = self
            .cache_dir
            .join(format!("{}{cache_suffix}.json", symbol.replace(['/', '\\'], "_")));
        let fresh = std::fs::metadata(&path)
            .and_then(|m| m.modified())
            .map(|t| SystemTime::now().duration_since(t).unwrap_or_default() < max_age)
            .unwrap_or(false);
        if fresh {
            if let Ok(q) = serde_json::from_str(&std::fs::read_to_string(&path)?) {
                return Ok(q);
            }
        }
        let url = format!("https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010}/us-gaap/{concept}.json");
        let mut attempt = 0;
        let facts = loop {
            let res = http::json(self.agent.get(&url).set("User-Agent", &self.user_agent).call());
            match res {
                Ok(v) => break v,
                Err(e) if attempt < 2 && !e.to_string().contains("HTTP 404") => {
                    attempt += 1;
                    std::thread::sleep(Duration::from_millis(1500 * attempt));
                }
                Err(e) => return Err(anyhow!("EDGAR {symbol}: {e}")),
            }
        };
        let parsed = parse(&facts);
        std::fs::create_dir_all(&self.cache_dir)?;
        std::fs::write(&path, serde_json::to_string(&parsed)?)?;
        // The SEC allows 10 requests a second; stay well under it.
        std::thread::sleep(Duration::from_millis(150));
        Ok(parsed)
    }

    /// Quarterly net income for a company.
    pub fn quarters(&self, symbol: &str, cik: u64, max_age: Duration) -> Result<Vec<Quarter>> {
        self.concept(symbol, cik, "NetIncomeLoss", "", max_age, quarters_from_facts)
    }

    /// Total assets at each balance-sheet date.
    pub fn assets(&self, symbol: &str, cik: u64, max_age: Duration) -> Result<Vec<Snapshot>> {
        self.concept(symbol, cik, "Assets", ".assets", max_age, snapshots_from_facts)
    }

    /// Run `f` for every company, a few at a time. Results keep the order of `ciks`.
    fn for_each<T: Send>(
        &self,
        ciks: &[(String, u64)],
        f: impl Fn(&str, u64) -> Result<T> + Sync,
    ) -> Vec<Option<T>> {
        let next = std::sync::atomic::AtomicUsize::new(0);
        let results: Vec<std::sync::Mutex<Option<T>>> =
            ciks.iter().map(|_| std::sync::Mutex::new(None)).collect();
        std::thread::scope(|scope| {
            for _ in 0..ciks.len().min(3) {
                scope.spawn(|| loop {
                    let i = next.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                    let Some((sym, cik)) = ciks.get(i) else { break };
                    *results[i].lock().unwrap() = f(sym, *cik).ok();
                });
            }
        });
        results.into_iter().map(|m| m.into_inner().unwrap()).collect()
    }

    /// Return on assets over time for every symbol that has a CIK, as
    /// (day the figure became public, value). Symbols without usable data
    /// are returned in the second list.
    pub fn load_profitability(
        &self,
        ciks: &[(String, u64)],
        max_age: Duration,
    ) -> (std::collections::HashMap<String, Vec<(i64, f64)>>, Vec<String>) {
        let loaded = self.for_each(ciks, |sym, cik| {
            let quarters = self.quarters(sym, cik, max_age)?;
            let assets = self.assets(sym, cik, max_age)?;
            Ok(return_on_assets(&quarters, &assets))
        });
        let mut out = std::collections::HashMap::new();
        let mut failed = Vec::new();
        for ((sym, _), series) in ciks.iter().zip(loaded) {
            match series {
                Some(s) if !s.is_empty() => {
                    out.insert(sym.clone(), s);
                }
                _ => failed.push(sym.clone()),
            }
        }
        (out, failed)
    }

    /// Scored reports for every symbol that has a CIK. Symbols whose data
    /// cannot be loaded are returned in the second list.
    pub fn load_all(
        &self,
        ciks: &[(String, u64)],
        max_age: Duration,
    ) -> (std::collections::HashMap<String, Vec<Report>>, Vec<String>) {
        let next = std::sync::atomic::AtomicUsize::new(0);
        let results: Vec<std::sync::Mutex<Option<Result<Vec<Quarter>>>>> =
            ciks.iter().map(|_| std::sync::Mutex::new(None)).collect();
        std::thread::scope(|scope| {
            for _ in 0..ciks.len().min(3) {
                scope.spawn(|| loop {
                    let i = next.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                    let Some((sym, cik)) = ciks.get(i) else { break };
                    *results[i].lock().unwrap() = Some(self.quarters(sym, *cik, max_age));
                });
            }
        });
        let mut out = std::collections::HashMap::new();
        let mut failed = Vec::new();
        for ((sym, _), r) in ciks.iter().zip(results) {
            match r.into_inner().unwrap() {
                Some(Ok(q)) => {
                    let reports = reports_from_quarters(&q);
                    if reports.is_empty() {
                        failed.push(sym.clone());
                    } else {
                        out.insert(sym.clone(), reports);
                    }
                }
                _ => failed.push(sym.clone()),
            }
        }
        (out, failed)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn fact(start: &str, end: &str, val: f64, form: &str, filed: &str) -> Value {
        json!({"start": start, "end": end, "val": val, "form": form, "filed": filed})
    }

    #[test]
    fn quarters_use_first_filing_and_derive_q4() {
        let facts = json!({"units": {"USD": [
            fact("2023-01-01", "2023-03-31", 10.0, "10-Q", "2023-05-01"),
            // Same period repeated a year later as a comparative: ignored.
            fact("2023-01-01", "2023-03-31", 11.0, "10-Q", "2024-05-01"),
            fact("2023-04-01", "2023-06-30", 12.0, "10-Q", "2023-08-01"),
            // Six-month year-to-date figure: not a quarter.
            fact("2023-01-01", "2023-06-30", 22.0, "10-Q", "2023-08-01"),
            fact("2023-07-01", "2023-09-30", 14.0, "10-Q", "2023-11-01"),
            fact("2023-01-01", "2023-12-31", 60.0, "10-K", "2024-02-15"),
            // Not a periodic report: ignored.
            fact("2023-10-01", "2023-12-31", 99.0, "8-K", "2024-01-20"),
        ]}});
        let q = quarters_from_facts(&facts);
        let vals: Vec<f64> = q.iter().map(|x| x.net_income).collect();
        assert_eq!(vals, vec![10.0, 12.0, 14.0, 24.0]); // Q4 = 60 - 36
        assert_eq!(q[0].filed, day("2023-05-01").unwrap());
        assert_eq!(q[3].filed, day("2024-02-15").unwrap());
    }

    #[test]
    fn sue_flags_an_unusually_good_quarter() {
        // Profit grows by about 1 a year (with a little noise), then jumps by 20.
        let noise = [0.0, 0.3, -0.2, 0.1, -0.3, 0.2, 0.0, -0.1, 0.3, -0.2, 0.1, 0.0];
        let mut quarters: Vec<Quarter> = (0..12)
            .map(|i| Quarter {
                period_end: 19_000 + i as i64 * 91,
                filed: 19_030 + i as i64 * 91,
                net_income: 100.0 + (i / 4) as f64 + noise[i],
            })
            .collect();
        quarters.push(Quarter { period_end: 19_000 + 12 * 91, filed: 19_030 + 12 * 91, net_income: 122.0 });
        let reports = reports_from_quarters(&quarters);
        let last = reports.last().unwrap();
        assert_eq!(last.filed, 19_030 + 12 * 91);
        assert!(last.sue > 5.0, "sue {}", last.sue);
        // Ordinary quarters score near the usual range.
        assert!(reports[..reports.len() - 1].iter().all(|r| r.sue.abs() < 5.0));
    }

    #[test]
    fn return_on_assets_is_point_in_time() {
        // Five quarters of 10 each; assets of 400 reported with each quarter.
        let quarters: Vec<Quarter> = (0..5)
            .map(|i| Quarter { period_end: 19_000 + i * 91, filed: 19_030 + i * 91, net_income: 10.0 })
            .collect();
        let assets: Vec<Snapshot> = (0..5)
            .map(|i| Snapshot { period_end: 19_000 + i * 91, filed: 19_030 + i * 91, value: 400.0 })
            .collect();
        let roa = return_on_assets(&quarters, &assets);
        // Needs four quarters, so the first value appears with the 4th filing.
        assert_eq!(roa, vec![(19_030 + 3 * 91, 0.1), (19_030 + 4 * 91, 0.1)]);
        // A gap in the quarterly history: no value spans it.
        let mut gappy = quarters.clone();
        gappy.remove(2);
        assert!(return_on_assets(&gappy, &assets).is_empty());
        // Balance sheet filed later than the earnings: dated by the later filing.
        let mut late = assets.clone();
        late[3].filed += 20;
        assert_eq!(return_on_assets(&quarters, &late)[0].0, 19_030 + 3 * 91 + 20);
    }

    #[test]
    fn snapshots_keep_the_first_filing() {
        let facts = json!({"units": {"USD": [
            {"end": "2023-03-31", "val": 100.0, "form": "10-Q", "filed": "2023-05-01"},
            {"end": "2023-03-31", "val": 101.0, "form": "10-Q", "filed": "2024-05-01"},
            {"end": "2023-06-30", "val": 110.0, "form": "8-K", "filed": "2023-07-01"},
            {"end": "2023-06-30", "val": 120.0, "form": "10-Q", "filed": "2023-08-01"},
        ]}});
        let s = snapshots_from_facts(&facts);
        assert_eq!(s.len(), 2);
        assert_eq!((s[0].value, s[0].filed), (100.0, day("2023-05-01").unwrap()));
        assert_eq!(s[1].value, 120.0);
    }
}
