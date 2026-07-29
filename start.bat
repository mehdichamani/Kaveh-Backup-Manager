@echo off
title Database Backup Manager
cd /d "%~dp0"

set "PYTHON_EXE=C:\Users\Mehdi\AppData\Local\Programs\Python\Python314\python.exe"

if exist "%PYTHON_EXE%" (
    "%PYTHON_EXE%" "%~dp0backup_manager.py"
) else (
    python "%~dp0backup_manager.py"
)
pause
