Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Get-Agent5Root {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Import-Agent5Env([string]$Root) {
    $envFile = Join-Path $Root ".env"
    if (-not (Test-Path -LiteralPath $envFile)) { return }
    Get-Content -LiteralPath $envFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $parts = $line.Split("=", 2)
        if ($parts.Count -eq 2) {
            [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
        }
    }
}


function Reset-Agent5StaleTestEnvironment {
    $testMode = [Environment]::GetEnvironmentVariable("AGENT5_TEST_MODE", "Process")
    $storage = [Environment]::GetEnvironmentVariable("AGENT5_STORAGE_DIR", "Process")
    $database = [Environment]::GetEnvironmentVariable("AGENT5_DATABASE_URL", "Process")
    $looksLikeTest = ($testMode -eq "1") -or ($storage -and $storage -match "(?i)test-runtime") -or ($database -and $database -match "(?i)agent5_test\.db")
    if ($looksLikeTest) {
        Write-Host "Clearing stale Agent5 test-runtime environment before production startup."
        foreach ($name in @("AGENT5_TEST_MODE", "AGENT5_STORAGE_DIR", "AGENT5_DATABASE_URL")) {
            [Environment]::SetEnvironmentVariable($name, $null, "Process")
        }
    }
    [Environment]::SetEnvironmentVariable("PYTEST_DISABLE_PLUGIN_AUTOLOAD", $null, "Process")
}

function Assert-Agent5ProductionEnvironment {
    $testMode = [Environment]::GetEnvironmentVariable("AGENT5_TEST_MODE", "Process")
    $storage = [Environment]::GetEnvironmentVariable("AGENT5_STORAGE_DIR", "Process")
    $database = [Environment]::GetEnvironmentVariable("AGENT5_DATABASE_URL", "Process")
    if ($testMode -eq "1" -or ($storage -and $storage -match "(?i)test-runtime") -or ($database -and $database -match "(?i)agent5_test\.db")) {
        throw "Production startup refused a test-runtime configuration. Remove AGENT5_TEST_MODE/test-runtime database settings from .env."
    }
}

function Get-Agent5Python([string]$Root) {
    $python = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Agent5 virtual environment is missing. Run .\setup_agent5.ps1 first."
    }
    return $python
}

function Test-Agent5Port([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(300)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-Agent5Url([string]$Url, [int]$TimeoutSeconds = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -eq 200) { return $response }
        } catch { Start-Sleep -Milliseconds 750 }
    }
    throw "Timed out waiting for $Url"
}

function Invoke-Agent5NpmRetry {
    param(
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [Parameter(Mandatory=$true)][string]$Description,
        [int]$Attempts = 3
    )
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        & npm @Arguments
        if ($LASTEXITCODE -eq 0) { return }
        if ($attempt -lt $Attempts) {
            $delay = 3 * $attempt
            Write-Warning "$Description failed (attempt $attempt/$Attempts). Retrying in $delay seconds..."
            Start-Sleep -Seconds $delay
        }
    }
    throw "$Description failed after $Attempts attempts. Check internet/proxy access to registry.npmjs.org and review npm output."
}
