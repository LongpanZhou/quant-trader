mod alpaca;
mod backend;
mod backtest;
mod config;
mod engine;
mod http;
mod indicators;
mod preflight;
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
    status      Show the paper account, positions and P&L
    preflight   Check live data, freshness, corporate actions and the current
                target without placing orders
    reset       Wipe the local sim ledger and logs (sim broker only)

OPTIONS:
    --config <FILE>    Config file to use [default: config.toml]
    --days <N>         Backtest the last N days instead of the config's setting
    --timeframe <TF>   Use this candle size instead of the config's: 1m, 5m, 15m, 1h, 1d
    --json <FILE>      Also write the full backtest report as JSON (for the web app)
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
    let mut json: Option<String> = None;
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
            "--json" => {
                i += 1;
                match args.get(i) {
                    Some(p) => json = Some(p.clone()),
                    None => bail!("--json needs a file path"),
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
    if json.is_some() && command != "backtest" {
        bail!("--json is only used with the backtest command");
    }

    let mut cfg = config::Config::load(&config_path)?;
    if let Some(d) = days {
        cfg.backtest.days = d;
    }
    if let Some(tf) = timeframe {
        cfg.timeframe = tf;
        cfg.validate()?;
    }
    if (command == "run" || command == "replay") && !cfg.backtest.synthetic_symbol.is_empty() {
        bail!("backtest.synthetic_symbol is for backtests only; live trading uses the real symbol");
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
            let strategy = strategy::build(&cfg);
            engine::Engine::new(cfg, backend, strategy, data_dir).run()
        }
        "backtest" => {
            let backend = backend::Backend::new(&cfg, &data_dir)?;
            let strategy = strategy::build(&cfg);
            backtest::run(&cfg, strategy.as_ref(), &backend, json.as_deref())
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
            let strategy = strategy::build(&cfg);
            engine::Engine::new(cfg, backend, strategy, dir.clone()).replay()?;
            println!("Trades from this replay: {}", dir.join("trades.csv").display());
            Ok(())
        }
        "status" => {
            let mut backend = backend::Backend::new(&cfg, &data_dir)?;
            engine::status(&cfg, &mut backend)
        }
        "preflight" => {
            let backend = backend::Backend::new(&cfg, &data_dir)?;
            let strategy = strategy::build(&cfg);
            preflight::run(&cfg, &backend, strategy.as_ref())
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
