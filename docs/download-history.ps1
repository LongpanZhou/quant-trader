<#
.SYNOPSIS
    Downloads years of 1-minute price history for a preset's symbols.

.DESCRIPTION
    The free live price feed keeps only about 60 days of 5-minute candles.
    This fetches multi-year history from Dukascopy's public datafeed (no
    account needed) and keeps it in data\cache\dukascopy, so that backtests
    with "--source dukascopy" can run on it.

    It is slow: the feed allows roughly 1,400 daily files an hour, and five
    years of one symbol is about 1,300 files. Leave this window open. It is
    safe to close it and run it again later: finished days are kept and it
    carries on from where it stopped. It does not interfere with live
    trading, which uses a different price feed.

.PARAMETER Config
    Preset whose symbols to download. Default: the 25-stock momentum test.

.PARAMETER Days
    How many days of history. Default 1825 (five years).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File docs\download-history.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File docs\download-history.ps1 -Config configs\intraday_ls_momentum_live_active.toml
#>
param(
    [string]$Config = "configs\momentum_25_5y.toml",
    [int]$Days = 1825
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$exe = Join-Path $root "target\release\quant-trader.exe"
if (-not (Test-Path $exe)) {
    Write-Host "quant-trader is not built yet. Run docs\run-monday.ps1 once, or 'cargo build --release'." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $root $Config))) {
    Write-Host "No such preset: $Config" -ForegroundColor Red
    exit 1
}

$log = Join-Path $root "data\download-history.log"
New-Item -ItemType Directory -Force (Join-Path $root "data") | Out-Null

# Days that could not be fetched during a throttled spell are skipped, so
# go round again until a pass downloads nothing new.
for ($pass = 1; $pass -le 4; $pass++) {
    Write-Host "===== Pass $pass  ($(Get-Date -Format 'yyyy-MM-dd HH:mm')) =====" -ForegroundColor Cyan
    & $exe download --config $Config --days $Days 2>&1 | Tee-Object -FilePath $log -Append
    $tail = Get-Content $log -Tail 400
    if (-not ($tail | Select-String "could not be downloaded")) { break }
}
Write-Host ""
Write-Host "History is ready. You can now run, for example:" -ForegroundColor Green
Write-Host "    .\target\release\quant-trader.exe backtest --config $Config"
