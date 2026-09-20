@echo off
setlocal
cd /d "%~dp0"

echo.
echo ==========================================
echo      ProGrapher Backend V0.1 - Setup
echo ==========================================
echo.

set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto python_found
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto python_found
)

echo ERROR: Python was not found.
echo Install Python 3.11 or 3.12 and enable "Add Python to PATH".
echo.
pause
exit /b 1

:python_found
echo Python command: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Could not activate virtual environment.
    pause
    exit /b 1
)

echo.
echo Updating pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: pip upgrade failed.
    pause
    exit /b 1
)

echo.
echo Installing base packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Base package installation failed.
    pause
    exit /b 1
)

echo.
choice /C YN /N /M "Install RAW support now? [Y/N] "
if errorlevel 2 goto skip_raw

echo.
echo Installing RAW support...
python -m pip install -r requirements-raw.txt
if errorlevel 1 (
    echo.
    echo WARNING: RAW support failed to install.
    echo The backend can still run with JPG/PNG for the first test.
)

:skip_raw
echo.
echo ==========================================
echo Setup completed successfully.
echo Next step: run start_backend.bat
echo ==========================================
echo.
pause
endlocal
