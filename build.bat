@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

:: Запрос прав администратора если их нет
net session >nul 2>&1
if errorlevel 1 (
    echo Запрашиваем права администратора...
    powershell -Command "Start-Process cmd -ArgumentList '/c pushd \"%~dp0\" && \"%~f0\"' -Verb RunAs"
    exit /b
)

:: Переходим в папку скрипта (работает с UNC-путями \\wsl.localhost\...)
pushd "%~dp0"
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
if exist dist\InvestDesktopWatcher.exe (
    del /f /q dist\InvestDesktopWatcher.exe
    echo   Removed old InvestDesktopWatcher.exe
)
if exist build rmdir /s /q build

:: Build
echo.
echo [3/3] Building (1-2 minutes)...
python -m PyInstaller invest_desktop_watcher.spec --noconfirm --clean

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check output above.
    pause & exit /b 1
)

:: No need to copy config/dashboard/icons to dist:
:: - dashboard.html + icons are packed inside .exe (via spec datas)
:: - config.json is created in %%APPDATA%%\InvestDesktopWatcher\ on first run (wizard)
echo.
echo All data is packed inside .exe
echo Config will be stored in %%APPDATA%%\InvestDesktopWatcher\

:: Result
echo.
if exist dist\InvestDesktopWatcher.exe (
    for %%A in (dist\InvestDesktopWatcher.exe) do set SIZE=%%~zA
    set /a SIZE_MB=!SIZE! / 1048576
    echo === BUILD OK ===
    echo dist\InvestDesktopWatcher.exe (!SIZE_MB! MB^)
    echo.
    echo Next steps:
    echo   1. Go to dist\
    echo   2. Edit config.json - add API token
    echo   3. Run InvestDesktopWatcher.exe
    echo.
) else (
    echo [ERROR] .exe not found - something went wrong.
)

popd
pause
