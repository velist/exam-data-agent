@echo off
chcp 65001 >nul
echo ============================================
echo   考试宝典数据助手 - 一键启动
echo ============================================
echo.

:: 获取脚本所在目录
set "BASE_DIR=%~dp0"

:: 启动后端
echo [1/2] 启动后端服务 (port 8000)...
cd /d "%BASE_DIR%backend"
start "ExamAgent-Backend" cmd /k "python -m uvicorn main:app --host 0.0.0.0 --port 8000"

:: 等后端就绪
timeout /t 3 /nobreak >nul

:: 启动前端
echo [2/2] 启动前端服务 (port 5173)...
cd /d "%BASE_DIR%frontend"
start "ExamAgent-Frontend" cmd /k "npx vite --port 5173 --host"

:: 等前端就绪
timeout /t 3 /nobreak >nul

echo.
echo ============================================
echo   启动完成！
echo   前端: http://localhost:5173
echo   后端: http://localhost:8000/api/health
echo ============================================
echo.
echo 关闭此窗口不会影响服务运行。
echo 要停止服务，请关闭 ExamAgent-Backend 和 ExamAgent-Frontend 窗口。
pause
