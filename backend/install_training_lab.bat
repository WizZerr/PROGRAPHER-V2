@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title ProGrapher Training Engine

echo.
echo ==========================================
echo    ProGrapher Training Engine Installer
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv was not found.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install numpy scikit-learn joblib

echo.
echo Training dependencies installed.
echo Restart start_backend.bat before training.
echo.
pause
