//! `preflight`: check everything the live loop depends on, without trading.
//!
//! It fetches the same bars and corporate actions the live loop uses, applies
//! the same "completed bar only" rule, and prints the strategy's current
//! target. Run it before starting `run` (and after changing a config).

use crate::backend::Backend;
use crate::config::Config;
use crate::strategy::Strategy;
use crate::types::Bar;
use anyhow::Result;
use std::collections::HashMap;

fn day(ts: i64) -> String {
    chrono::DateTime::from_timestamp(ts, 0)
        .map(|d| d.format("%Y-%m-%d %H:%M").to_string())
        .unwrap_or_else(|| ts.to_string())
}

pub fn run(cfg: &Config, backend: &Backend, strategy: &dyn Strategy) -> Result<()> {
    let tf = cfg.timeframe;
    let now = chrono::Utc::now().timestamp();
    let per_day = tf.bars_per_day() as f64;
    let history = (strategy.warmup() as f64 / per_day * 1.6).ceil() as i64 + 4;
    let mut problems: Vec<String> = Vec::new();

    println!("PREFLIGHT | {} | {} bars | {} symbols", strategy.name(), tf.yahoo(), cfg.symbols.len());
    println!("now: {} UTC | history window: {history} days | warmup: {} bars", day(now), strategy.warmup());
    println!("data: {}", backend.describe());
    println!();

    let mut universe: HashMap<String, Vec<Bar>> = HashMap::new();

    for sym in &cfg.symbols {
        match backend.bars(sym, tf, history) {
            Ok(bars) if !bars.is_empty() => {
                // Same rule as the live loop: only completed bars are visible
                // to the strategy (daily bars finish at their next timestamp).
                let complete: Vec<_> = bars
                    .iter()
                    .copied()
                    .filter(|b| b.is_complete(tf, now))
                    .collect();
                let n = complete.len();
                let last = complete.last().copied();
                let is_fresh = last
                    .map(|b| now - (b.ts + tf.secs()) <= tf.stale_after_secs())
                    .unwrap_or(false);
                let age = last.map(|b| (now - (b.ts + tf.secs())) as f64 / 86400.0).unwrap_or(f64::NAN);
                println!(
                    "{sym:<8} {:>4} bars | last {} | {:.1} days old | close {:.2} | {}",
                    n,
                    last.map(|b| day(b.ts)).unwrap_or_else(|| "-".into()),
                    age,
                    last.map(|b| b.close).unwrap_or(f64::NAN),
                    if is_fresh { "fresh" } else { "STALE" }
                );
                if n < strategy.warmup() {
                    problems.push(format!("{sym}: {n} completed bars, strategy needs {}", strategy.warmup()));
                }
                if !is_fresh {
                    problems.push(format!("{sym}: last completed bar is stale"));
                }
                if n > 0 {
                    universe.insert(sym.clone(), complete);
                }
            }
            Ok(_) => problems.push(format!("{sym}: no bars returned")),
            Err(e) => problems.push(format!("{sym}: {e}")),
        }

        match backend.events(sym, 400) {
            Ok(ev) => {
                let mut recent: Vec<(i64, String)> = Vec::new();
                for (ts, ratio) in ev.splits {
                    recent.push((ts, format!("split {ratio:.4}x on {}", day(ts))));
                }
                for (ts, amount) in ev.dividends {
                    recent.push((ts, format!("dividend ${amount:.4} on {}", day(ts))));
                }
                recent.sort_by_key(|(ts, _)| *ts);
                if recent.is_empty() {
                    println!("         corporate actions: none in 400 days");
                } else {
                    let shown: Vec<&str> = recent.iter().rev().take(3).map(|(_, s)| s.as_str()).collect();
                    println!("         corporate actions: {}", shown.join("; "));
                }
            }
            Err(e) => println!("         corporate actions: unavailable ({e})"),
        }
    }

    // Current decision on exactly the slices the live loop would pass.
    let lookback = strategy.lookback();
    let slices: HashMap<&str, &[Bar]> = universe
        .iter()
        .map(|(s, b)| (s.as_str(), &b[b.len().saturating_sub(lookback)..]))
        .collect();
    let held: Vec<String> = backend.positions()?.keys().cloned().collect();
    let held_refs: Vec<&str> = held.iter().map(|s| s.as_str()).collect();
    let targets = strategy.targets(&slices, &held_refs);

    println!();
    match &targets {
        None => println!("current target: none (strategy would not act on this bar)"),
        Some(t) if t.is_empty() => {
            println!("current target: 100% cash");
            if !held.is_empty() {
                println!("  would close: {}", held.join(", "));
            }
        }
        Some(t) => {
            let gross: f64 = t.iter().map(|(_, w)| w.abs()).sum();
            println!("current target: {:.1}% gross", gross * 100.0);
            for (sym, w) in t {
                println!("  {sym:<8} {:>7.1}%", w * 100.0);
            }
        }
    }

    // Effective leverage is fund-specific (TQQQ is 3x), so report the weights
    // and let the strategy's name carry the multiple.
    if strategy.is_portfolio() && targets.is_some() {
        println!("  (weights are fractions of equity; a 3x fund supplies its own leverage)");
    }

    let acct = backend.account()?;
    println!();
    println!("paper account: equity ${:.2} | cash ${:.2} | {} position(s)", acct.equity, acct.cash, held.len());
    for (s, p) in backend.positions()? {
        println!("  {s:<8} qty {:<12.4} avg ${:.4}", p.qty, p.avg_price);
    }

    if !cfg.backtest.synthetic_symbol.is_empty() {
        problems.push("backtest.synthetic_symbol is set; live trading always uses real prices".into());
    }

    println!();
    if problems.is_empty() {
        println!("PREFLIGHT: PASS");
        Ok(())
    } else {
        for p in &problems {
            println!("  PROBLEM: {p}");
        }
        println!("PREFLIGHT: FAIL ({} problem(s))", problems.len());
        anyhow::bail!("preflight found {} problem(s)", problems.len())
    }
}
