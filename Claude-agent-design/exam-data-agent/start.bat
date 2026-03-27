@echo off
chcp 65001 >nul
echo ============================================
echo   考试宝典数据助手 - 一键启动
echo ============================================
echo.

:: 获取脚本所在目录
set "BASE_DIR=%~dp0"

:: 构建前端
echo [1/2] 构建前端...
cd /d "%BASE_DIR%frontend"
call npm run build
if errorlevel 1 (
    echo 前端构建失败！
    pause
    exit /b 1
)

:: 启动服务
echo [2/2] 启动服务 (port 8000)...
cd /d "%BASE_DIR%backend"

echo.
echo ============================================
echo   访问地址: http://localhost:8000
echo ============================================
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
