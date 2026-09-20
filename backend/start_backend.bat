@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Run setup_windows.bat first.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo        ProGrapher Local Engine
echo ==========================================
echo.
echo API:  http://127.0.0.1:8000
echo Docs: http://127.0.0.1:8000/docs
echo.
echo Keep this window open while using ProGrapher.
echo.

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo Backend stopped.
pause
endlocal
