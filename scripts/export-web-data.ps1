$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    cargo build --release
    if ($LASTEXITCODE -ne 0) { throw "cargo build failed" }

    $exe = Join-Path $root "target\release\quant-trader.exe"
    $data = Join-Path $root "web\public\data"
    New-Item -ItemType Directory -Force -Path $data | Out-Null

    & $exe backtest --config "configs\nasdaq_leveraged_trend.toml" --json (Join-Path $data "5y.json")
    & $exe backtest --config "configs\nasdaq_leveraged_trend.toml" --days 3650 --json (Join-Path $data "10y.json")
    & $exe backtest --config "configs\nasdaq_synthetic_20y.toml" --json (Join-Path $data "20y.json")
    & $exe backtest --config "configs\nasdaq_synthetic_20y.toml" --days 9500 --json (Join-Path $data "26y.json")

    Write-Host "`nDashboard data written to web/public/data"
} finally {
    Pop-Location
}
