@echo off
setlocal
cd /d %~dp0

rem ── Chon Python ───────────────────────────────────────────────────────────
if exist "%~dp0python\python.exe" (
  set "PYTHON=%~dp0python\python.exe"
) else (
  set "PYTHON=C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe"
)

title BSMQ - Cap nhat / Update

echo.
echo =============================================
echo   BSMQ Tool - Kiem tra cap nhat
echo =============================================
echo.

rem ── Kiem tra server co dang chay khong ───────────────────────────────────
set "API=http://127.0.0.1:8000/api"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Invoke-WebRequest '%API%/health' -UseBasicParsing -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo [BSMQ] Server chua chay. Dang khoi dong de kiem tra cap nhat...
  start /b "" "%PYTHON%" -m uvicorn app_api:app --host 127.0.0.1 --port 8000 --log-level error
  timeout /t 4 >nul
)

rem ── Goi API kiem tra cap nhat ─────────────────────────────────────────────
echo Dang kiem tra...
"%PYTHON%" -c "
import json, urllib.request, sys
try:
    with urllib.request.urlopen('%API%/update/check', timeout=15) as r:
        d = json.loads(r.read())
    print('Phien ban hien tai:', d.get('current','?'))
    print('Phien ban moi nhat:', d.get('latest','?'))
    if d.get('has_update'):
        print()
        print('CO BAN CAP NHAT MOI!')
        cl = d.get('changelog','')
        if cl:
            print('Thay doi:', cl)
        sys.exit(10)
    elif d.get('error'):
        print('Loi:', d['error'])
        sys.exit(2)
    else:
        print('Da la phien ban moi nhat.')
        sys.exit(0)
except Exception as e:
    print('Loi ket noi:', e)
    sys.exit(1)
"

set "CHECK_CODE=%errorlevel%"

if "%CHECK_CODE%"=="10" (
  echo.
  set /p CONFIRM=Ban co muon cap nhat khong? ^(y/N^):
  if /i "!CONFIRM!"=="y" (
    echo.
    echo Dang ap dung cap nhat...
    "%PYTHON%" -c "
import json, urllib.request
req = urllib.request.Request('%API%/update/apply', data=b'{}', method='POST')
req.add_header('Content-Type','application/json')
with urllib.request.urlopen(req, timeout=10) as r:
    d = json.loads(r.read())
print('Job ID:', d.get('job_id','?'))
print('Khoi dong lai BSMQ de hoan tat cap nhat.')
"
    echo.
    echo Vui long dong va mo lai run.bat sau khi cap nhat.
  ) else (
    echo Da huy cap nhat.
  )
)

echo.
pause
