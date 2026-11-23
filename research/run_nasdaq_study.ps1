# Rebuilds the tables in docs/nasdaq_leveraged_trend.md.
# Run from the repository root:  .\research\run_nasdaq_study.ps1
$ErrorActionPreference = "Stop"
$exe = ".\target\release\quant-trader.exe"
if (-not (Test-Path $exe)) { throw "Build first: cargo build --release" }

$headline = "configs\nasdaq_leveraged_trend.toml"
New-Item -ItemType Directory -Force -Path "research\results" | Out-Null
New-Item -ItemType Directory -Force -Path "research\logs" | Out-Null

function Show-Backtest([string]$title, [string[]]$cli) {
    "`n=== $title ==="
    & $exe backtest @cli 2>&1 | Where-Object {
        $_ -match '^\d{4}\s|Strategy return|QQQ buy|SPY buy|Excess|Max drawdown|Sharpe|Period tested|Closed trades|Win rate|Profit factor'
    }
}

Show-Backtest "Headline, five years" @("--config", $headline)
& $exe backtest --config $headline 2>&1 | Set-Content "research\results\nasdaq_leveraged_trend_5y.txt"

Show-Backtest "Headline, ten years" @("--config", $headline, "--days", "3650")
& $exe backtest --config $headline --days 3650 2>&1 | Set-Content "research\results\nasdaq_leveraged_trend_10y.txt"

$configs = @(
    "plateau_s155_v040_open", "plateau_s165_v040_open", "plateau_s175_v040_open",
    "qqq_tqqq_s165_v035_open", "plateau_s165_v045_open", "plateau_s165_v050_open",
    "plateau_s165_v040_vd10_open", "plateau_s165_v040_vd40_open",
    "qqq_tqqq_s165_v040_lag1_slip5_open", "qqq_tqqq_s200_v040_open",
    "qqq_qld_s150_v040_open", "qqq_tsmom_12m_v040_x2_open"
)

"`n=== Parameter plateau and rejected variants (5 years) ==="
"Config; CAGR; Excess; MaxDD; Sharpe"
$rows = @()
foreach ($name in $configs) {
    $out = & $exe backtest --config "configs\research\$name.toml" 2>&1 | Out-String
    Set-Content "research\logs\$name.txt" $out
    $cagr = ([regex]::Match($out, 'Strategy return\s*:.*?\(([-+0-9.]+)% a year\)')).Groups[1].Value
    $ex = ([regex]::Match($out, 'Excess vs QQQ\s*:\s*([-+0-9.]+)% a year')).Groups[1].Value
    $dd = ([regex]::Match($out, 'Max drawdown\s*:\s*([-0-9.]+)%')).Groups[1].Value
    $sh = ([regex]::Match($out, 'Sharpe \(annualised\)\s*:\s*([-0-9.]+)')).Groups[1].Value
    "$name; $cagr; $ex; $dd; $sh"
    $rows += [pscustomobject]@{ config = $name; cagr_pct = $cagr; excess_vs_qqq_pct = $ex; max_dd_pct = $dd; sharpe = $sh }
}
$rows | Export-Csv "research\results\plateau.csv" -NoTypeInformation

"`n=== Endpoint sensitivity (headline config, shifted end) ==="
foreach ($e in 0, 30, 45, 60) {
    $cfg = Get-Content $headline -Raw
    $cfg = $cfg -replace '(?m)^end_days_ago.*$', ''
    $cfg = $cfg + "`nend_days_ago = $e`n"
    $path = "configs\research\endpoint_$e.toml"
    Set-Content $path $cfg
    $out = & $exe backtest --config $path 2>&1 | Out-String
    $qqq = ([regex]::Match($out, 'QQQ buy & hold\s*:.*?\(([-+0-9.]+)% a year\)')).Groups[1].Value
    $ex = ([regex]::Match($out, 'Excess vs QQQ\s*:\s*([-+0-9.]+)% a year')).Groups[1].Value
    "end -$e days: QQQ $qqq% a year, excess $ex pp"
}
