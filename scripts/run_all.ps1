# GASLIT — start everything (API + WebSocket bridge) in one command.
#
# Usage (from repo root, PowerShell):
#   .\scripts\run_all.ps1
#
# Stops with Ctrl+C. Both processes inherit the venv Python.

$ErrorActionPreference = "Stop"

$repo = (Get-Item ".").FullName
$py = Join-Path $repo ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "[run_all] venv not found at .venv\Scripts\python.exe" -ForegroundColor Red
    Write-Host "[run_all] run: python -m venv .venv ; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

# Read API_PORT and WS_PORT from .env (default 8002 / 8003).
$envFile = Join-Path $repo ".env"
$apiPort = "8002"
$wsPort  = "8003"
if (Test-Path $envFile) {
    $apiMatch = Select-String -Path $envFile -Pattern '^API_PORT=(\d+)' -ErrorAction SilentlyContinue
    if ($apiMatch) { $apiPort = $apiMatch.Matches[0].Groups[1].Value }
    $wsMatch  = Select-String -Path $envFile -Pattern '^WS_PORT=(\d+)' -ErrorAction SilentlyContinue
    if ($wsMatch)  { $wsPort  = $wsMatch.Matches[0].Groups[1].Value }
}

Write-Host "[run_all] starting API on :$apiPort and WS bridge on :$wsPort" -ForegroundColor Cyan

$api = Start-Process -FilePath $py `
    -ArgumentList "-m","uvicorn","api.main:app","--host","127.0.0.1","--port",$apiPort,"--log-level","info" `
    -PassThru -NoNewWindow

$ws  = Start-Process -FilePath $py `
    -ArgumentList "ws/bridge.py" `
    -PassThru -NoNewWindow

Write-Host "[run_all] api pid=$($api.Id)  ws pid=$($ws.Id)" -ForegroundColor Cyan
Write-Host "[run_all] press Ctrl+C to stop both"

try {
    Wait-Process -Id $api.Id, $ws.Id
} finally {
    if (-not $api.HasExited) { Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue }
    if (-not $ws.HasExited)  { Stop-Process -Id $ws.Id  -Force -ErrorAction SilentlyContinue }
}
