@echo off
setlocal
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
  set "PY=venv\Scripts\python.exe"
) else (
  set "PY=python"
)

"%PY%" -m pip install -r launcher\requirements-build.txt || exit /b 1
taskkill /T /F /IM "AI Note Taker.exe" >nul 2>nul
taskkill /T /F /IM ProjectLauncher.exe >nul 2>nul

set "PYI_WORK=%TEMP%\AINoteTakerBuild"
if exist "%PYI_WORK%" rmdir /s /q "%PYI_WORK%" >nul 2>nul

"%PY%" -m PyInstaller --clean --noconfirm --workpath "%PYI_WORK%" "AI Note Taker.spec" || exit /b 1
"%PY%" verify_build.py || exit /b 1

echo Built and verified dist\AI Note Taker.exe
