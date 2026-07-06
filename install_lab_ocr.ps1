$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  Write-Host "Virtual environment not found. Run .\setup.ps1 first."
  exit 1
}

Write-Host "Installing Python OCR wrapper..."
& $Python -m pip install pytesseract

$Tesseract = Get-Command tesseract -ErrorAction SilentlyContinue
if (-not $Tesseract) {
  $Winget = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $Winget) {
    Write-Host "winget was not found. Install Tesseract OCR manually, then re-run this script."
    exit 1
  }

  Write-Host "Installing Tesseract OCR engine with winget..."
  winget install --id UB-Mannheim.TesseractOCR --source winget --accept-package-agreements --accept-source-agreements
}

$Tesseract = Get-Command tesseract -ErrorAction SilentlyContinue
if ($Tesseract) {
  Write-Host "OCR is ready: $($Tesseract.Source)"
} else {
  Write-Host "Tesseract was installed, but it is not on PATH yet. Restart PowerShell and run .\start_labs.ps1 again."
}
