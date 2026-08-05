param(
    [ValidateSet("Monitor", "Preview", "RunOnce", "CheckRoster", "CheckEdges")]
    [string]$Mode = "Monitor"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir

function Initialize-Environment {
    [Console]::InputEncoding = [System.Text.Encoding]::UTF8
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $script:OutputEncoding = [System.Text.Encoding]::UTF8
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUNBUFFERED = "1"
    $webhook = [Environment]::GetEnvironmentVariable("MAKEUP_WECHAT_WEBHOOK_URL", "Process")
    if ([string]::IsNullOrWhiteSpace($webhook)) {
        $webhook = [Environment]::GetEnvironmentVariable("MAKEUP_WECHAT_WEBHOOK_URL", "User")
    }
    if (-not [string]::IsNullOrWhiteSpace($webhook)) {
        $env:MAKEUP_WECHAT_WEBHOOK_URL = $webhook.Trim()
    }
}

function Get-Config {
    return Get-Content -LiteralPath (Join-Path $projectDir "config.json") -Raw -Encoding UTF8 |
        ConvertFrom-Json
}

function Test-EdgeDebugPort {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri ($Url.TrimEnd("/") + "/json/version") -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Ensure-Edges {
    $browsers = @((Get-Config).browsers.PSObject.Properties)
    foreach ($browser in $browsers) {
        $url = [string]$browser.Value.cdp_url
        if (-not (Test-EdgeDebugPort -Url $url)) {
            throw "$($browser.Name) Edge is not ready: $url. Start and sign in from the live-data export project first."
        }
        Write-Host "$($browser.Name) Edge is ready: $url"
    }
}

function Invoke-Python {
    param([string[]]$Arguments)
    Push-Location $projectDir
    try {
        & python -u -m makeup_monitor.main @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Python failed with exit code: $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

Initialize-Environment
switch ($Mode) {
    "Monitor" {
        Ensure-Edges
        Invoke-Python @("--monitor")
    }
    "Preview" {
        Ensure-Edges
        Invoke-Python @("--dry-run")
    }
    "RunOnce" {
        Ensure-Edges
        Invoke-Python @()
    }
    "CheckRoster" {
        Invoke-Python @("--roster-only")
    }
    "CheckEdges" {
        Ensure-Edges
    }
}
