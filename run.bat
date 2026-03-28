@echo off
setlocal
cd /d %~dp0

if not exist logs mkdir logs

rem ── Dung Python nhung trong folder (neu co), fallback sang Python he thong ──
if exist "%~dp0python\python.exe" (
  set "PYTHON=%~dp0python\python.exe"
) else (
  set "PYTHON=C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe"
)

rem ── Kiem tra da chay install.bat chua (chi can neu dung Python nhung) ──────
if exist "%~dp0python" (
  if not exist "%~dp0python\_setup_done.flag" (
    echo [BSMQ] Chua cai dat! Hay double-click install.bat truoc.
    pause & exit /b 1
  )
)

set "PORT=8000"
set "LOG_FILE=logs\api_runtime.log"
set "HEALTH_URL=http://127.0.0.1:%PORT%/api/health"
set "AUTO_OPEN_BROWSER=1"
set "BROWSER_OPENED=0"

title BSMQ Control Center v6
echo ==========================================
echo   BSMQ System v6.0 - FastAPI Backend
echo ==========================================
echo Local  : http://localhost:%PORT%
echo Network: http://192.168.2.9:%PORT%
echo Log    : %LOG_FILE%
echo.
echo Press Ctrl+C to stop.
echo.

rem Check if server already running
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){ exit 0 } else { exit 1 } } catch { exit 1 }"
if "%errorlevel%"=="0" (
  echo [%date% %time%] Server already running on port %PORT%. Opening browser...>>"%LOG_FILE%"
  call :open_browser_once
  goto wait_loop
)

rem Kill stale process if any
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do taskkill /PID %%P /F >nul 2>&1

rem Disable legacy Streamlit listener (port 8501) to avoid dual-platform confusion
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":8501 .*LISTENING"') do (
  echo [%date% %time%] Stopping Streamlit process on 8501 (PID %%P)>>"%LOG_FILE%"
  taskkill /PID %%P /F >nul 2>&1
)

:loop
echo [%date% %time%] Starting BSMQ FastAPI on port %PORT%...>>"%LOG_FILE%"
call :open_browser_once
"%PYTHON%" -m uvicorn app_api:app --host 0.0.0.0 --port %PORT% --log-level warning >>"%LOG_FILE%" 2>&1
echo [%date% %time%] Server exited (code %errorlevel%). Restarting in 3s...>>"%LOG_FILE%"
timeout /t 3 >nul
goto loop

:open_browser_once
if not "%AUTO_OPEN_BROWSER%"=="1" goto :eof
if "%BROWSER_OPENED%"=="1" goto :eof
start http://localhost:%PORT%
set "BROWSER_OPENED=1"
goto :eof

:wait_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -Uri '%HEALTH_URL%' -UseBasicParsing -TimeoutSec 3; if($r.StatusCode -eq 200){ exit 0 } else { exit 1 } } catch { exit 1 }"
if "%errorlevel%"=="0" (
  timeout /t 5 >nul
  goto wait_loop
)
echo [%date% %time%] Server went down. Restarting...>>"%LOG_FILE%"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do taskkill /PID %%P /F >nul 2>&1
timeout /t 2 >nul
goto loop
