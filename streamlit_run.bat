@echo off
setlocal
cd /d %~dp0

if not exist logs mkdir logs

rem ── Chon Python ──────────────────────────────────────────────
if exist "%~dp0python\python.exe" (
  set "PYTHON=%~dp0python\python.exe"
) else (
  set "PYTHON=C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe"
)

set "PORT=8501"
title BSMQ Streamlit v5 - Port %PORT%

echo ==========================================
echo   BSMQ Tool v5 - Streamlit UI
echo ==========================================
echo Local  : http://localhost:%PORT%
echo Tab moi: MARKET (Price Search)
echo.
echo Press Ctrl+C to stop.
echo.

rem Kill stale process on port 8501 if any
for /f "tokens=5" %%P in ('netstat -ano 2^>nul ^| findstr /r /c:":%PORT% .*LISTENING"') do (
  taskkill /PID %%P /F >nul 2>&1
)

rem Start Streamlit
"%PYTHON%" -m streamlit run app.py --server.port %PORT% --server.address 0.0.0.0 --server.headless true >> logs\streamlit_runtime.log 2>&1

echo.
echo [BSMQ] Streamlit exited. Restart streamlit_run.bat de chay lai.
pause
