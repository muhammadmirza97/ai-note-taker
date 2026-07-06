$ErrorActionPreference = "Stop"

function Test-PythonVersion {
    $versionOutput = & python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python 3.11+ is required but was not found. Install Python 3.11 or newer and rerun setup.ps1."
        exit 1
    }

    $versionText = [string]$versionOutput
    if ($versionText -notmatch "Python\s+(\d+)\.(\d+)\.(\d+)") {
        Write-Error "Could not determine Python version from: $versionText"
        exit 1
    }

    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
        Write-Error "Python 3.11+ is required. Found $versionText"
        exit 1
    }

    Write-Host "Python check PASS: $versionText"
}

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

function Start-OllamaIfNeeded {
    $ollama = Get-OllamaPath
    if (-not $ollama) {
        Write-Host "Installing Ollama..."
        winget install Ollama.Ollama --accept-source-agreements --accept-package-agreements
        $ollama = Get-OllamaPath
    }

    if (-not $ollama) {
        Write-Error "Ollama installation did not produce an ollama executable on PATH or in the expected install folders."
        exit 1
    }

    if (-not (Test-OllamaReady)) {
        Write-Host "Starting Ollama..."
        Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden | Out-Null
    }

    Write-Host "Waiting for Ollama..."
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        if (Test-OllamaReady) {
            Write-Host "Ollama check PASS"
            return $ollama
        }
        Start-Sleep -Seconds 3
    }

    Write-Error "Ollama did not become available at http://localhost:11434 within 60 seconds."
    exit 1
}

function Invoke-SmokeTest {
    $python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
    Write-Host "Running smoke test..."
    $process = Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    try {
        Start-Sleep -Seconds 5
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000" -UseBasicParsing -TimeoutSec 10
            if ($response.StatusCode -eq 200) {
                Write-Host "Smoke test GET / PASS"
            }
            else {
                Write-Host "Smoke test GET / FAIL: status $($response.StatusCode)"
            }
        }
        catch {
            Write-Host "Smoke test GET / FAIL: $($_.Exception.Message)"
        }
    }
    finally {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
    }
}

Set-Location $PSScriptRoot
Test-PythonVersion

if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .\venv
}
else {
    Write-Host "Virtual environment already exists."
}

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt
& $venvPython -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True)"
& $venvPython -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"

$ollamaPath = Start-OllamaIfNeeded
& $ollamaPath pull llama3.2:1b

Invoke-SmokeTest
Write-Host "Setup complete. Run ./start.ps1 to launch the app."
