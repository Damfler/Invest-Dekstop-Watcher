@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title T-Bank Invest Build

echo.
echo === T-Bank Invest Tray - Build ===
echo.

:: Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    pause & exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo Python: %PY_VER%

:: Install dependencies
echo.
echo [1/3] Installing dependencies...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause & exit /b 1
)

:: Install PyInstaller
python -m pip install -q pyinstaller>=6.0
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause & exit /b 1
)

:: Clean old build
echo.
echo [2/3] Cleaning previous build...
if exist dist\tbank_invest.exe (
    del /f /q dist\tbank_invest.exe
    echo   Removed old tbank_invest.exe
)
if exist build rmdir /s /q build

:: Build
echo.
echo [3/3] Building (1-2 minutes)...
python -m PyInstaller tbank_invest.spec --noconfirm --clean

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check output above.
    pause & exit /b 1
)

:: No need to copy config/dashboard/icons to dist:
:: - dashboard.html + icons are packed inside .exe (via spec datas)
:: - config.json is created in %%APPDATA%%\TBankWatcher\ on first run (wizard)
echo.
echo All data is packed inside .exe
echo Config will be stored in %%APPDATA%%\TBankWatcher\

:: Result
echo.
if exist dist\tbank_invest.exe (
    for %%A in (dist\tbank_invest.exe) do set SIZE=%%~zA
    set /a SIZE_MB=!SIZE! / 1048576
    echo === BUILD OK ===
    echo dist\tbank_invest.exe (!SIZE_MB! MB^)
    echo.
    echo Next steps:
    echo   1. Go to dist\
    echo   2. Edit config.json - add API token
    echo   3. Run tbank_invest.exe
    echo.
) else (
    echo [ERROR] .exe not found - something went wrong.
)

pause
