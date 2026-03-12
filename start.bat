@echo off
chcp 65001 >nul 2>nul
cd /d "%~dp0"
python launcher.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Exit code: %ERRORLEVEL%
    echo Please check Python is installed and added to PATH
    echo Download: https://www.python.org/downloads/
)
pause
