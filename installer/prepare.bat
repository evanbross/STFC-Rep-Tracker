@echo off
:: ============================================================
:: STFC Rep Tracker — Installer Preparation Script
:: Run this once before building the Inno Setup installer.
:: Requires: internet access, Node.js (for npm run build)
:: ============================================================
setlocal

:: ai: claude-opus-5-5 | 2026-11-07
:: Keep in step with .python-version (the major.minor must match; use its latest patch).
set PYTHON_VER=3.14.7
set PYTHON_ZIP=python-%PYTHON_VER%-embed-amd64.zip
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/%PYTHON_ZIP%
set GETPIP_URL=https://bootstrap.pypa.io/get-pip.py

cd /d "%~dp0"

:: ── 1. Download Python embeddable ────────────────────────────────────────────
if exist "%PYTHON_ZIP%" (
    echo Python embeddable already downloaded, skipping.
) else (
    echo Downloading Python %PYTHON_VER% embeddable...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_ZIP%'"
    if errorlevel 1 ( echo ERROR: Failed to download Python embeddable. & exit /b 1 )
)

:: ── 2. Download get-pip.py ───────────────────────────────────────────────────
if exist "get-pip.py" (
    echo get-pip.py already present, skipping.
) else (
    echo Downloading get-pip.py...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%GETPIP_URL%' -OutFile 'get-pip.py'"
    if errorlevel 1 ( echo ERROR: Failed to download get-pip.py. & exit /b 1 )
)

:: ── 3. Build the React frontend ──────────────────────────────────────────────
echo Building frontend...
pushd ..\frontend
call npm run build
if errorlevel 1 ( echo ERROR: npm run build failed. & popd & exit /b 1 )
popd
echo Frontend built successfully.

:: ── 4. Generate requirements_dist.txt (torch/torchvision excluded) ───────────
:: These are installed separately from the PyTorch CPU wheel index.
echo Generating requirements_dist.txt...
powershell -NoProfile -Command ^
  "Get-Content '..\requirements.txt' | Where-Object { $_ -notmatch '^torch==' -and $_ -notmatch '^torchvision==' } | Set-Content 'requirements_dist.txt'"
echo requirements_dist.txt generated.

:: ai: claude-opus-5-5 | 2026-11-07
:: ── 5. Generate requirements_torch.txt (CPU builds of the locked torch pins) ─
:: The torch/torchvision versions come from requirements.txt (generated from
:: uv.lock), so the installer can't drift from the lock.
echo Generating requirements_torch.txt...
powershell -NoProfile -Command ^
  "$pins = @(Get-Content '..\requirements.txt' | Where-Object { $_ -match '^(torch|torchvision)==' } | ForEach-Object { ($_ -split '\s*;')[0].Trim() + '+cpu' }); if ($pins.Count -ne 2) { Write-Error 'Expected torch and torchvision pins in requirements.txt'; exit 1 }; @('--index-url https://download.pytorch.org/whl/cpu') + $pins | Set-Content 'requirements_torch.txt'"
if errorlevel 1 ( echo ERROR: Could not generate requirements_torch.txt. & exit /b 1 )
echo requirements_torch.txt generated.

echo.
echo ============================================================
echo Preparation complete. Open STFC_Rep_Tracker.iss in the
echo Inno Setup Compiler and click Build to create the installer.
echo ============================================================
endlocal
