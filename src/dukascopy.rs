//! Multi-year intraday history from Dukascopy's public datafeed (no key).
//!
//! Yahoo only keeps about 60 days of 5-minute bars. Dukascopy publishes
//! 1-minute candles going back years for SPY, QQQ and large US stocks, one
//! small file per symbol per day. This module downloads those files (slowly:
//! the feed throttles), keeps them on disk, and builds bars of any size.
//!
//! Things to know about this data:
//! - It covers the regular session only (9:30-16:00 Eastern).
//! - Prices are Dukascopy's bid quotes for its CFD on the stock, which track
//!   the real price closely but are not exchange trades.
//! - Volume is Dukascopy's own, not the exchange's. Strategies that weight
//!   by volume (VWAP) are only approximated.
//! - It is for backtests. Live trading keeps using the live price feed.

use crate::config::Timeframe;
use crate::types::Bar;
use anyhow::{anyhow, bail, Result};
use chrono::{Datelike, NaiveDate};
use std::io::Read;
use std::path::PathBuf;
use std::time::Duration;

pub struct Dukascopy {
    agent: ureq::Agent,
    cache_dir: PathBuf,
}

/// Decode one day's file: LZMA-compressed 24-byte records of
/// (seconds since midnight UTC, open, close, low, high, volume), prices in
/// thousandths of a dollar. Minutes without trading are dropped.
pub fn decode_day(raw: &[u8], midnight: i64) -> Result<Vec<Bar>> {
    if raw.is_empty() {
        return Ok(Vec::new());
    }
    let mut data = Vec::new();
    lzma_rs::lzma_decompress(&mut std::io::BufReader::new(raw), &mut data)
        .map_err(|e| anyhow!("corrupt candle file: {e:?}"))?;
    let be_i32 = |b: &[u8]| i32::from_be_bytes([b[0], b[1], b[2], b[3]]);
    let mut out = Vec::new();
    for rec in data.chunks_exact(24) {
        let volume = f32::from_be_bytes([rec[20], rec[21], rec[22], rec[23]]) as f64;
        if volume <= 0.0 {
            continue;
        }
        let px = |i: usize| be_i32(&rec[i..i + 4]) as f64 / 1000.0;
        out.push(Bar {
            ts: midnight + be_i32(&rec[0..4]) as i64,
            open: px(4),
            close: px(8),
            low: px(12),
            high: px(16),
            volume,
        });
    }
    Ok(out)
}

/// Combine 1-minute bars (one session, in time order) into bars of `secs`.
/// Buckets are aligned to the half hour, as the US session opens at :30.
pub fn aggregate(minutes: &[Bar], secs: i64) -> Vec<Bar> {
    let mut out: Vec<Bar> = Vec::new();
    for m in minutes {
        let start = if secs >= 86_400 {
            minutes[0].ts
        } else {
            m.ts - (m.ts - 1800).rem_euclid(secs)
        };
        match out.last_mut() {
            Some(b) if b.ts == start => {
                b.high = b.high.max(m.high);
                b.low = b.low.min(m.low);
                b.close = m.close;
                b.volume += m.volume;
            }
            _ => out.push(Bar { ts: start, ..*m }),
        }
    }
    out
}

/// Rescale intraday bars so that each session's last price equals the
/// split- and dividend-adjusted daily close from another source. This
/// removes the huge artificial jumps that stock splits leave in raw prices
/// (and makes the series a total-return series, like the daily data).
/// Sessions with no matching daily close reuse the previous session's factor.
pub fn adjust_to_daily(bars: &mut [Bar], daily: &[Bar]) {
    let day = |ts: i64| ts.div_euclid(86_400);
    let closes: std::collections::HashMap<i64, f64> = daily.iter().map(|b| (day(b.ts), b.close)).collect();
    let mut factor = 1.0;
    let mut start = 0;
    while start < bars.len() {
        let d = day(bars[start].ts);
        let end = start + bars[start..].iter().take_while(|b| day(b.ts) == d).count();
        let session_close = bars[end - 1].close;
        if let Some(&c) = closes.get(&d) {
            if session_close > 0.0 && c > 0.0 {
                factor = c / session_close;
            }
        }
        for b in &mut bars[start..end] {
            b.open *= factor;
            b.high *= factor;
            b.low *= factor;
            b.close *= factor;
        }
        start = end;
    }
}

/// The first overnight move too large to be real (a likely unadjusted
/// split): (time, move as a fraction).
pub fn split_jump(bars: &[Bar]) -> Option<(i64, f64)> {
    bars.windows(2)
        .find(|w| !(0.6..=1.67).contains(&(w[1].open / w[0].close)))
        .map(|w| (w[1].ts, w[1].open / w[0].close - 1.0))
}

impl Dukascopy {
    pub fn new(cache_dir: PathBuf) -> Self {
        Dukascopy { agent: crate::http::agent(), cache_dir }
    }

    /// One day's raw file, from disk if already downloaded. An empty result
    /// means the market was closed (or the symbol did not exist yet).
    /// The bool is true when the file had to be downloaded.
    fn day_file(&self, symbol: &str, date: NaiveDate) -> Result<(Vec<u8>, bool)> {
        let dir = self.cache_dir.join(symbol);
        let path = dir.join(format!("{date}.bi5"));
        if let Ok(bytes) = std::fs::read(&path) {
            return Ok((bytes, false));
        }
        let url = format!(
            "https://datafeed.dukascopy.com/datafeed/{symbol}USUSD/{}/{:02}/{:02}/BID_candles_min_1.bi5",
            date.year(),
            date.month0(), // months are numbered from 0 in this feed
            date.day()
        );
        // The feed serves a burst of files and then refuses for several
        // minutes, so keep trying for about ten minutes before giving up.
        let mut wait = 2;
        for _ in 0..14 {
            let res = self
                .agent
                .get(&url)
                .set("Referer", "https://freeserv.dukascopy.com/")
                .timeout(Duration::from_secs(40))
                .call();
            let bytes = match res {
                Ok(resp) => {
                    let mut buf = Vec::new();
                    match resp.into_reader().take(4_000_000).read_to_end(&mut buf) {
                        Ok(_) => Some(buf),
                        Err(_) => None,
                    }
                }
                Err(ureq::Error::Status(404, _)) => Some(Vec::new()),
                // Throttled or a network blip: wait and try again.
                Err(_) => None,
            };
            if let Some(bytes) = bytes {
                std::fs::create_dir_all(&dir)?;
                std::fs::write(&path, &bytes)?;
                return Ok((bytes, true));
            }
            std::thread::sleep(Duration::from_secs(wait));
            wait = (wait * 2).min(60);
        }
        bail!("could not download {symbol} {date}")
    }

    /// Regular-session bars for the last `days` calendar days, oldest first.
    pub fn bars(&self, symbol: &str, tf: Timeframe, days: i64) -> Result<Vec<Bar>> {
        if symbol.contains('.') {
            bail!("{symbol}: not available from this source");
        }
        let today = chrono::Utc::now().date_naive();
        let mut date = today - chrono::Duration::days(days.max(1));
        let epoch = NaiveDate::from_ymd_opt(1970, 1, 1).unwrap();
        let (mut out, mut downloaded, mut failed) = (Vec::new(), 0usize, 0usize);
        // Only completed days: today's file is still being written.
        while date < today {
            if date.weekday().number_from_monday() <= 5 {
                match self.day_file(symbol, date) {
                    Ok((raw, fresh)) => {
                        let midnight = date.signed_duration_since(epoch).num_seconds();
                        out.extend(aggregate(&decode_day(&raw, midnight)?, tf.secs()));
                        if fresh {
                            downloaded += 1;
                            if downloaded % 50 == 0 {
                                println!("  {symbol}: downloaded {downloaded} days (now at {date})");
                            }
                            // Be gentle: the feed blocks clients that hurry.
                            std::thread::sleep(Duration::from_millis(350));
                        }
                    }
                    Err(_) => failed += 1,
                }
            }
            date += chrono::Duration::days(1);
        }
        if failed > 0 {
            println!("  {symbol}: {failed} day(s) could not be downloaded and are missing");
        }
        if out.is_empty() {
            bail!("{symbol}: no intraday history available from this source");
        }
        Ok(out)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn minute(ts: i64, o: f64, h: f64, l: f64, c: f64) -> Bar {
        Bar { ts, open: o, high: h, low: l, close: c, volume: 1.0 }
    }

    #[test]
    fn aggregates_minutes_into_session_aligned_bars() {
        // Session opens 14:30 UTC. Seven minutes -> one full 5-minute bar and a partial one.
        let open = 14 * 3600 + 30 * 60;
        let m: Vec<Bar> = (0..7)
            .map(|i| minute(open + i * 60, 100.0 + i as f64, 101.0 + i as f64, 99.0 + i as f64, 100.5 + i as f64))
            .collect();
        let bars = aggregate(&m, 300);
        assert_eq!(bars.len(), 2);
        assert_eq!((bars[0].ts, bars[1].ts), (open, open + 300));
        assert_eq!((bars[0].open, bars[0].high, bars[0].low, bars[0].close), (100.0, 105.0, 99.0, 104.5));
        assert_eq!(bars[0].volume, 5.0);
        // Hourly bars start on the half hour, like the exchange session.
        assert_eq!(aggregate(&m, 3600)[0].ts, open);
        // Daily: one bar for the whole session.
        let day = aggregate(&m, 86_400);
        assert_eq!(day.len(), 1);
        assert_eq!((day[0].open, day[0].close, day[0].volume), (100.0, 106.5, 7.0));
    }

    #[test]
    fn decodes_candle_records_and_skips_idle_minutes() {
        // Two records: one traded minute, one idle minute.
        let mut plain = Vec::new();
        for (secs, o, c, l, h, v) in [(52_200i32, 591_717i32, 591_766i32, 591_656i32, 591_777i32, 1.5f32),
                                      (52_260, 591_766, 591_766, 591_766, 591_766, 0.0)] {
            for x in [secs, o, c, l, h] {
                plain.extend_from_slice(&x.to_be_bytes());
            }
            plain.extend_from_slice(&v.to_be_bytes());
        }
        let mut packed = Vec::new();
        lzma_rs::lzma_compress(&mut std::io::BufReader::new(plain.as_slice()), &mut packed).unwrap();
        let bars = decode_day(&packed, 1_000_000).unwrap();
        assert_eq!(bars.len(), 1);
        let b = bars[0];
        assert_eq!(b.ts, 1_000_000 + 52_200);
        assert_eq!((b.open, b.close, b.low, b.high, b.volume), (591.717, 591.766, 591.656, 591.777, 1.5));
        // A closed day is an empty file.
        assert!(decode_day(&[], 0).unwrap().is_empty());
    }

    #[test]
    fn adjustment_removes_a_split_jump() {
        const DAY: i64 = 86_400;
        let open = 14 * 3600 + 30 * 60;
        // Day 1 trades around 400 (before a 4-for-1 split), day 2 around 101.
        let mut bars = vec![
            minute(open, 400.0, 404.0, 396.0, 400.0),
            minute(open + 300, 400.0, 408.0, 400.0, 404.0),
            minute(DAY + open, 101.0, 102.0, 100.0, 102.0),
        ];
        assert!(split_jump(&bars).is_some());
        // Adjusted daily closes: 101 (= 404 / 4) and 102.
        let daily = vec![minute(open, 0.0, 0.0, 0.0, 101.0), minute(DAY + open, 0.0, 0.0, 0.0, 102.0)];
        adjust_to_daily(&mut bars, &daily);
        assert!(split_jump(&bars).is_none());
        assert!((bars[1].close - 101.0).abs() < 1e-9);
        assert!((bars[0].open - 100.0).abs() < 1e-9 && (bars[0].high - 101.0).abs() < 1e-9);
        // Day 2 already matched, so it is unchanged.
        assert!((bars[2].close - 102.0).abs() < 1e-9 && (bars[2].low - 100.0).abs() < 1e-9);
    }
}
