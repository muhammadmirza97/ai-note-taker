$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python -m pip install -r (Join-Path $PSScriptRoot "requirements-build.txt")
& $python -m PyInstaller --noconfirm --onefile --windowed --name ProjectLauncher (Join-Path $PSScriptRoot "__main__.py")

Write-Host "Built dist\ProjectLauncher.exe"
