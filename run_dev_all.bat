@echo off
TITLE WA! CRM Suite Runner
COLOR 0B

echo ======================================================================
echo           WA! CRM - UNIFIED CORPORATE SUITE (WITH NATIVE BILLING)
echo ======================================================================
echo.

cd /d "%~dp0"

echo [1/2] Starting WA! CRM FastAPI Backend on http://127.0.0.1:8000...
start "WaCRM Backend (FastAPI :8000)" cmd /k "cd backend && venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Starting WA! CRM Vite Frontend on http://localhost:5173...
start "WaCRM Frontend (Vite :5173)" cmd /k "cd frontend && npm run dev"

echo.
echo ======================================================================
echo CRM Services running:
echo   - WaCRM Web Application: http://localhost:5173
echo   - WaCRM Backend API:     http://localhost:8000/docs
echo   - Quotations & Billing:  Built directly inside the CRM!
echo ======================================================================
pause
