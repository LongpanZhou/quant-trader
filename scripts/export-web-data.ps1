$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    cargo build --release
    if ($LASTEXITCODE -ne 0) { throw "cargo build failed" }

    $exe = Join-Path $root "target\release\quant-trader.exe"
    $data = Join-Path $root "web\public\data"

    function Export-Window($slug, $config, $window, [string[]]$extra = @()) {
        $dir = Join-Path $data $slug
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $json = Join-Path $dir "$window.json"
        $cliArgs = @("backtest", "--config", $config, "--json", $json) + $extra
        & $exe @cliArgs
        if ($LASTEXITCODE -ne 0) { throw "backtest failed for $slug/$window" }
    }

    # Nasdaq leveraged trend (the promoted strategy)
    Export-Window "nasdaq-leveraged-trend" "configs\nasdaq_leveraged_trend.toml" "5y"
    Export-Window "nasdaq-leveraged-trend" "configs\nasdaq_leveraged_trend.toml" "10y" @("--days", "3650")
    Export-Window "nasdaq-leveraged-trend" "configs\nasdaq_synthetic_20y.toml" "20y"
    Export-Window "nasdaq-leveraged-trend" "configs\nasdaq_synthetic_20y.toml" "26y" @("--days", "9500")

    # S&P 500 2x trend (research variant)
    Export-Window "sp500-2x-trend" "web\strategies\sp500_2x_trend.toml" "5y"
    Export-Window "sp500-2x-trend" "web\strategies\sp500_2x_trend.toml" "10y" @("--days", "3650")
    Export-Window "sp500-2x-trend" "web\strategies\sp500_2x_trend.toml" "20y" @("--days", "7299")

    # Nasdaq 3x simple trend, no volatility target (ablation)
    Export-Window "nasdaq-3x-simple" "web\strategies\nasdaq_3x_simple.toml" "5y"
    Export-Window "nasdaq-3x-simple" "web\strategies\nasdaq_3x_simple.toml" "10y" @("--days", "3650")
    Export-Window "nasdaq-3x-simple" "web\strategies\nasdaq_3x_simple_synth.toml" "20y"
    Export-Window "nasdaq-3x-simple" "web\strategies\nasdaq_3x_simple_synth.toml" "26y" @("--days", "9500")

    Write-Host "`nDashboard data written to web/public/data"
} finally {
    Pop-Location
}
