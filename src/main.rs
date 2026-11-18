mod alpaca;
mod backend;
mod backtest;
mod config;
mod dukascopy;
mod edgar;
mod engine;
mod http;
mod indicators;
mod sim;
mod strategy;
mod types;
mod yahoo;

use anyhow::{bail, Result};
use std::path::{Path, PathBuf};

const USAGE: &str = "\
quant-trader - automatic quantitative paper trading on live US stock data

USAGE:
    quant-trader <COMMAND> [--config <FILE>]

COMMANDS:
    run         Start the live trading loop (paper money, real prices)
    backtest    Test the configured strategy on recent real history
    replay      Rehearse: run the live trading code over the latest session's
                real prices, bar by bar, on a throwaway account
    download    Fetch and cache multi-year 1-minute history for the config's
                symbols (slow; safe to stop and restart)
    status      Show the paper account, positions and P&L
    reset       Wipe the local sim ledger and logs (sim broker only)

OPTIONS:
    --config <FILE>    Config file to use [default: config.toml]
    --days <N>         Backtest the last N days instead of the config's setting
    --timeframe <TF>   Use this candle size instead of the config's: 1m, 5m, 15m, 1h, 1d
    --source <SRC>     Price history for backtests: live (default) or dukascopy
                       (years of 1-minute data for SPY, QQQ and large stocks;
                       slow to download the first time, then cached)
";

fn main() {
    if let Err(e) = real_main() {
        eprintln!("error: {e:#}");
        std::process::exit(1);
    }
}

fn real_main() -> Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut command = None;
    let mut config_path = "config.toml".to_string();
    let mut days: Option<i64> = None;
    let mut timeframe: Option<config::Timeframe> = None;
    let mut source: Option<String> = None;
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--config" | "-c" => {
                i += 1;
                match args.get(i) {
                    Some(p) => config_path = p.clone(),
                    None => bail!("--config needs a file path"),
                }
            }
            "--source" => {
                i += 1;
                match args.get(i).map(|s| s.as_str()) {
                    Some("dukascopy") => source = Some("dukascopy".to_string()),
                    Some("live") => source = Some(String::new()),
                    _ => bail!("--source needs one of: live, dukascopy"),
                }
            }
            "--timeframe" => {
                i += 1;
                match args.get(i).and_then(|t| config::Timeframe::parse(t)) {
                    Some(tf) => timeframe = Some(tf),
                    None => bail!("--timeframe needs one of: 1m, 5m, 15m, 1h, 1d"),
                }
            }
            "--days" => {
                i += 1;
                match args.get(i).and_then(|d| d.parse::<i64>().ok()) {
                    Some(d) if d > 0 => days = Some(d),
                    _ => bail!("--days needs a positive number"),
                }
            }
            "-h" | "--help" | "help" => {
                print!("{USAGE}");
                return Ok(());
            }
            other if command.is_none() && !other.starts_with('-') => command = Some(other.to_string()),
            other => bail!("unexpected argument '{other}'\n\n{USAGE}"),
        }
        i += 1;
    }
    let Some(command) = command else {
        print!("{USAGE}");
        return Ok(());
    };

    let mut cfg = config::Config::load(&config_path)?;
    if let Some(d) = days {
        cfg.backtest.days = d;
    }
    if let Some(tf) = timeframe {
        cfg.timeframe = tf;
        cfg.validate()?;
    }
    if let Some(s) = source {
        cfg.history = s;
    }
    if command == "run" && !cfg.history.is_empty() {
        bail!("history = \"{}\" is for backtests and replays only; live trading uses the live price feed", cfg.history);
    }
    // Each config gets its own paper account and logs: ./data/<config name>/
    let stem = Path::new(&config_path)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("config");
    let data_dir: PathBuf = Path::new("data").join(stem);

    match command.as_str() {
        "run" => {
            let backend = backend::Backend::new(&cfg, &data_dir)?;
            let strategy = strategy::build(&cfg, strategy::Mode::Live, Path::new("data/cache"))?;
            engine::Engine::new(cfg, backend, strategy, data_dir).run()
        }
        "backtest" => {
            let backend = backend::Backend::new(&cfg, &data_dir)?;
            let strategy = strategy::build(&cfg, strategy::Mode::Backtest, Path::new("data/cache"))?;
            backtest::run(&cfg, strategy.as_ref(), &backend)
        }
        "replay" => {
            // Always the built-in simulator with a throwaway account, so a
            // replay can never touch the real paper account or its logs.
            let mut cfg = cfg;
            cfg.broker = config::BrokerKind::Sim;
            let dir = Path::new("data").join(format!("{stem}-replay"));
            if dir.exists() {
                std::fs::remove_dir_all(&dir)?;
            }
            let backend = backend::Backend::new(&cfg, &dir)?;
            let strategy = strategy::build(&cfg, strategy::Mode::Live, Path::new("data/cache"))?;
            engine::Engine::new(cfg, backend, strategy, dir.clone()).replay()?;
            println!("Trades from this replay: {}", dir.join("trades.csv").display());
            Ok(())
        }
        "download" => {
            // Fetch and cache long intraday history without running a test.
            // Safe to stop and restart: finished days are kept on disk.
            let mut cfg = cfg;
            cfg.broker = config::BrokerKind::Sim;
            cfg.history = "dukascopy".to_string();
            let backend = backend::Backend::new(&cfg, &data_dir)?;
            let total = cfg.symbols.len();
            let mut failed = 0;
            for (i, sym) in cfg.symbols.iter().enumerate() {
                match backend.bars(sym, config::Timeframe::D1, cfg.backtest.days) {
                    Ok(b) => println!("[{}/{total}] {sym}: {} sessions ready", i + 1, b.len()),
                    Err(e) => {
                        failed += 1;
                        println!("[{}/{total}] {sym}: {e}", i + 1);
                    }
                }
            }
            println!("Download finished: {} of {total} symbols ready.", total - failed);
            Ok(())
        }
        "status" => {
            let mut backend = backend::Backend::new(&cfg, &data_dir)?;
            engine::status(&cfg, &mut backend)
        }
        "reset" => {
            if cfg.broker != config::BrokerKind::Sim {
                bail!("reset only applies to the sim broker; reset an Alpaca paper account from its dashboard");
            }
            for f in ["sim_ledger.json", "trades.csv", "equity.csv"] {
                let p = data_dir.join(f);
                if p.exists() {
                    std::fs::remove_file(&p)?;
                    println!("removed {}", p.display());
                }
            }
            println!("sim account reset to ${:.2}", cfg.sim.starting_cash);
            Ok(())
        }
        other => bail!("unknown command '{other}'\n\n{USAGE}"),
    }
}
