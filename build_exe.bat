@echo off
title Build Standalone Backup Manager EXE
echo ===================================================
echo   Building Standalone EXE for Server Backup Manager
echo ===================================================
echo.

:: Check PyInstaller availability
where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] pyinstaller command was not found in PATH.
    echo [*] Checking pip installation...
    pip show pyinstaller >nul 2>&1
    if %errorlevel% neq 0 (
        echo [!] PyInstaller is not installed. Installing...
        pip install pyinstaller pyyaml PyQt6
    )
)

echo [*] Compiling Backup Manager using PyInstaller...
pyinstaller --noconsole --onefile --icon=assets/app_icon.ico --add-data "assets;assets" --name "BackupManager" backup_manager.py

if %errorlevel% equ 0 (
    echo.
    echo ===================================================
    echo [+] Success! Standalone executable created:
    echo     dist\BackupManager.exe
    echo ===================================================
) else (
    echo.
    echo [!] Build failed. Please verify error messages above.
)
echo.
pause
