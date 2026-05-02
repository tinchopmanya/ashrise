$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if (-not $env:ASHRISE_BASE_URL) {
  $env:ASHRISE_BASE_URL = "http://localhost:8080"
}

if (-not $env:ASHRISE_TOKEN) {
  $env:ASHRISE_TOKEN = "dev-token"
}

if (-not $env:RADAR_WATCH_DIR) {
  $env:RADAR_WATCH_DIR = Join-Path $repoRoot "data\radar\inbox"
}

if (-not $env:RADAR_PROCESSED_DIR) {
  $env:RADAR_PROCESSED_DIR = Join-Path $repoRoot "data\radar\processed"
}

if (-not $env:RADAR_FAILED_DIR) {
  $env:RADAR_FAILED_DIR = Join-Path $repoRoot "data\radar\failed"
}

Write-Host "Radar watcher"
Write-Host "  API:       $env:ASHRISE_BASE_URL"
Write-Host "  inbox:     $env:RADAR_WATCH_DIR"
Write-Host "  processed: $env:RADAR_PROCESSED_DIR"
Write-Host "  failed:    $env:RADAR_FAILED_DIR"

& .\.venv\Scripts\python.exe -m ashrise_runtime.radar_watcher
