@echo off
setlocal
cd /d "%~dp0"

echo.
echo ==========================================
echo      ProGrapher Local AI Brain Setup
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Run setup_windows.bat first.
    pause
    exit /b 1
)

echo Installing PyTorch with NVIDIA CUDA support...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto :fail

echo.
echo Installing local vision dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements-ai.txt
if errorlevel 1 goto :fail

echo.
echo AI dependencies installed successfully.
echo.
echo Next:
echo 1. Start start_backend.bat
echo 2. Open http://127.0.0.1:8000/docs
echo 3. Run POST /api/brain/warmup
echo.
echo The first warmup downloads the vision model to this PC.
pause
exit /b 0

:fail
echo.
echo ERROR: AI installation failed.
pause
exit /b 1
endlocal
