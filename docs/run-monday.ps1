<#
.SYNOPSIS
    Starts the live paper-trading session: one window per strategy.

.DESCRIPTION
    Paper money only. Each strategy gets its own window, its own paper
    account (data\<name>\) and a log file (data\<name>\live.log).
    Start it a few minutes before the US market opens (9:30 AM Eastern).
    To stop a strategy, press Ctrl+C in its window or close the window.

.PARAMETER Strategies
    Names of presets in the configs\ folder. Default: seven strategies, six
    of which trade many symbols (see docs\monday.md).

.PARAMETER Rehearse
    Do not trade live. Instead replay the latest session's real prices
    through the live code on a throwaway account, in this window.

.PARAMETER Fresh
    Wipe each strategy's paper account back to its starting cash first.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File docs\run-monday.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File docs\run-monday.ps1 -Rehearse

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File docs\run-monday.ps1 -Strategies orb_1m,trend_sp500
#>
param(
    [string[]]$Strategies = @("orb_stocks_5m", "intraday_momentum_10", "vwap_10_1m", "core", "value_momentum_long", "intraday_ls_momentum_live_active", "leverage_2x"),
    [switch]$Rehearse,
    [switch]$Fresh
)

$ErrorActionPreference = "Stop"

# "powershell -File" passes "a,b,c" as one string, so split the names here.
$Strategies = @($Strategies | ForEach-Object { $_ -split "," } | ForEach-Object { $_.Trim() } | Where-Object { $_ })

# The program reads configs\, universes\ and data\ relative to the project folder.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$exe = Join-Path $root "target\release\quant-trader.exe"

# Build the program if it has not been built yet.
if (-not (Test-Path $exe)) {
    $cargo = Join-Path $env:USERPROFILE ".cargo\bin\cargo.exe"
    if (-not (Test-Path $cargo)) {
        Write-Host "Rust is not installed (no $cargo). Install it from https://rustup.rs and run this again." -ForegroundColor Red
        exit 1
    }
    Write-Host "Building quant-trader (first run only)..."
    & $cargo build --release
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exe)) {
        Write-Host "Build failed." -ForegroundColor Red
        exit 1
    }
}

# Check every requested preset exists before starting anything.
foreach ($name in $Strategies) {
    if (-not (Test-Path (Join-Path $root "configs\$name.toml"))) {
        $known = (Get-ChildItem (Join-Path $root "configs") -Filter *.toml | ForEach-Object { $_.BaseName }) -join ", "
        Write-Host "No preset named '$name'. Available: $known" -ForegroundColor Red
        exit 1
    }
}

if ($Rehearse) {
    foreach ($name in $Strategies) {
        Write-Host ""
        Write-Host "===== Rehearsal: $name =====" -ForegroundColor Cyan
        & $exe replay --config "configs\$name.toml"
    }
    Write-Host ""
    Write-Host "Rehearsal finished. Nothing was traded on the real paper accounts." -ForegroundColor Green
    exit 0
}

# Refuse to start a strategy twice: two copies would trade the same account.
$running = Get-CimInstance Win32_Process -Filter "Name = 'quant-trader.exe'" -ErrorAction SilentlyContinue
foreach ($name in $Strategies) {
    if ($running | Where-Object { $_.CommandLine -match " run " -and $_.CommandLine -match [regex]::Escape("$name.toml") }) {
        Write-Host "'$name' is already running. Close its window first." -ForegroundColor Red
        exit 1
    }
}

foreach ($name in $Strategies) {
    $config = "configs\$name.toml"
    if ($Fresh) {
        & $exe reset --config $config | Out-Null
        Write-Host "Reset the paper account for $name."
    }
    $dataDir = Join-Path $root "data\$name"
    New-Item -ItemType Directory -Force $dataDir | Out-Null
    $log = Join-Path $dataDir "live.log"

    # Runs in its own window; everything shown is also appended to the log.
    $command = @"
`$Host.UI.RawUI.WindowTitle = 'quant-trader: $name'
Set-Location '$root'
& '$exe' run --config '$config' 2>&1 | Tee-Object -FilePath '$log' -Append
Write-Host ''
Write-Host 'quant-trader stopped. You can close this window.' -ForegroundColor Yellow
"@
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $command
    Write-Host "Started $name  (log: data\$name\live.log)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Each strategy is running in its own window."
Write-Host "Check an account at any time, for example:"
Write-Host "    .\target\release\quant-trader.exe status --config configs\$($Strategies[0]).toml"
