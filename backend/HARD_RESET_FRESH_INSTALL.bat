@echo off
setlocal EnableExtensions
cd /d "%~dp0"

title ProGrapher - HARD RESET TO FRESH INSTALL

echo.
echo ============================================================
echo        ProGrapher - HARD RESET TO FRESH INSTALL
echo ============================================================
echo.
echo THIS IS IRREVERSIBLE.
echo.
echo This removes ALL runtime/product data from the configured
echo PROGRAPHER_DATA_DIR, including:
echo.
echo   - Users and passwords
echo   - Login sessions
echo   - Onboarding answers
echo   - Events and uploaded photos
echo   - Previews and edited renders
echo   - Lightroom imports
echo   - Dataset builds and audits
echo   - Vision / CLIP analysis saved by ProGrapher
echo   - Trained Production Profiles under ProGrapher data
echo   - Profile versions and ACTIVE profile
echo   - Predictions
echo   - Approve / Correct learning samples
echo   - Retraining runs and candidates
echo   - XMP exports
echo.
echo It intentionally KEEPS installation/runtime dependencies:
echo.
echo   - Backend source code
echo   - .env deployment configuration
echo   - .venv / Python packages
echo   - Hugging Face / foundation-model cache
echo   - Frontend source/build files
echo.
echo That is the equivalent of deploying the application code on a
echo prepared machine with a completely empty application database.
echo.
echo IMPORTANT:
echo Close start_backend.bat and any ProGrapher Python process NOW.
echo.
set /p CONFIRM=Type HARDRESET exactly to erase all ProGrapher runtime data: 

if not "%CONFIRM%"=="HARDRESET" (
    echo.
    echo Reset cancelled. Nothing was deleted.
    pause
    exit /b 0
)

echo.
echo Resolving the REAL data directory from .env...

set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
    goto python_found
)

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
pause
exit /b 1

:python_found
"%PYTHON_CMD%" "hard_reset_fresh_install.py" --confirmed
if errorlevel 1 (
    echo.
    echo HARD RESET FAILED. Review the message above.
    echo No fresh-start test should be started until this succeeds.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo                 HARD RESET COMPLETE
echo ============================================================
echo.
echo Next:
echo   1. Run start_backend.bat
echo   2. Run VERIFY_FRESH_INSTALL.bat
echo   3. Open the ProGrapher website
echo.
echo The old browser session will invalidate automatically.
echo A brand-new registration will also clear the old local
echo Lightroom-profile pointer from this browser.
echo.
pause
exit /b 0
