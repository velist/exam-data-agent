@echo off
chcp 65001 >nul
echo ============================================
echo   Exam Data Agent - Starting...
echo ============================================
echo.

:: Get script directory
set "BASE_DIR=%~dp0"

:: Build frontend
echo [1/2] Building frontend...
cd /d "%BASE_DIR%frontend"
call npm run build
if errorlevel 1 (
    echo Frontend build failed!
    pause
    exit /b 1
)

:: Start backend server
echo [2/2] Starting server (port 8230)...
cd /d "%BASE_DIR%backend"

echo.
echo ============================================
echo   URL: http://localhost:8230
echo ============================================
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8230
pause