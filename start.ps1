$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\venv\Scripts\Activate.ps1")) {
    Write-Error "Virtual environment not found. Run ./setup.ps1 first."
    exit 1
}

. .\venv\Scripts\Activate.ps1

function Get-OllamaPath {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
        "$env:ProgramFiles\Ollama\ollama.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

function Test-OllamaReady {
    try {
        Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 5 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Test-AppReady {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000" -UseBasicParsing -TimeoutSec 5
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (-not (Test-OllamaReady)) {
    $ollama = Get-OllamaPath
    if (-not $ollama) {
        Write-Error "Ollama not found. Run ./setup.ps1 first."
        exit 1
    }
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden | Out-Null
}

Start-Sleep -Seconds 3

if (Test-AppReady) {
    Write-Host "App running at http://localhost:8000"
    exit 0
}

Write-Host "App running at http://localhost:8000"
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
