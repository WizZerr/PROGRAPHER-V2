@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ProGrapher - Verify Fresh Install

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
"%PYTHON_CMD%" "verify_fresh_install.py"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
    echo Fresh-install verification PASSED.
) else (
    echo Fresh-install verification FAILED.
)
echo.
pause
exit /b %RESULT%
