$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  Write-Host "Virtual environment not found. Run .\setup.ps1 first."
  exit 1
}

Write-Host "Starting Lab Notes on http://localhost:8010"
& $Python -m uvicorn lab_app:app --host 127.0.0.1 --port 8010
