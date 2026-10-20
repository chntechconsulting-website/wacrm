@echo off
TITLE WA! CRM - Local Production Runner
COLOR 0A

echo ========================================================
echo         WA! CRM - PRODUCTION LOCAL RUNNER
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/3] Building React Frontend with relative /api endpoints...
cd frontend
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Frontend build failed. Please fix build errors.
    pause
    exit /b %ERRORLEVEL%
)
cd ..
echo [✔] Frontend built successfully in frontend/dist.
echo.

echo [2/3] Checking FastAPI Backend...
echo Starting backend server on http://127.0.0.1:8000...
start "WA! CRM FastAPI Backend (127.0.0.1:8000)" cmd /k "cd backend && venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

echo.
echo [3/3] Nginx Reverse Proxy Setup:
echo --------------------------------------------------------
tasklist /fi "imagename eq nginx.exe" | findstr /i "nginx.exe" >nul
if %ERRORLEVEL% EQU 0 (
    echo [✔] Nginx is already running. Reloading configuration...
    cd /d "C:\nginx" && nginx.exe -s reload
    cd /d "%~dp0"
) else (
    echo [*] Starting Nginx...
    cd /d "C:\nginx" && start nginx.exe
    cd /d "%~dp0"
    echo [✔] Nginx started.
)
echo.
echo Once Nginx is started, access your CRM at:
echo    --> http://localhost
echo    --> https://wacrm.dinuping.com
echo.
echo ========================================================
echo Backend is running on 127.0.0.1:8000
echo Reverse Proxy exposed on port 80 (http://localhost)
echo Cloudflare Tunnel forwarding to https://wacrm.dinuping.com
echo ========================================================
pause
