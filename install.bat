@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

set "PYTHON_DIR=%~dp0python"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "DONE_FLAG=%PYTHON_DIR%\_setup_done.flag"
set "PY_ZIP=%~dp0_setup\python-3.11.9-embed-amd64.zip"
set "GET_PIP=%~dp0_setup\get-pip.py"

if not exist logs mkdir logs
set "LOG=%~dp0logs\install.log"

title BSMQ - Cai dat lan dau
echo.
echo =============================================
echo   BSMQ Tool v6 - Cai dat / First-time Setup
echo =============================================
echo.

rem ── Kiem tra da cai chua ──────────────────────────────────────────────────
if exist "%DONE_FLAG%" (
  echo [OK] Da cai dat truoc do. Chay run.bat de khoi dong BSMQ.
  echo.
  pause
  exit /b 0
)

rem ── Tai file Python neu chua co ───────────────────────────────────────────
if not exist "%PY_ZIP%" (
  echo [1/5] Tai Python 3.11 embeddable ...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Invoke-WebRequest 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile '%PY_ZIP%' -UseBasicParsing; Write-Host 'OK' } catch { Write-Host 'FAIL:' $_.Exception.Message; exit 1 }"
  if errorlevel 1 (
    echo [LOI] Khong tai duoc Python. Kiem tra ket noi internet.
    pause & exit /b 1
  )
) else (
  echo [1/5] Python zip da co san.
)

if not exist "%GET_PIP%" (
  echo     Tai get-pip.py ...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%GET_PIP%' -UseBasicParsing } catch { exit 1 }"
  if errorlevel 1 (
    echo [LOI] Khong tai duoc get-pip.py.
    pause & exit /b 1
  )
)

rem ── Giai nen Python ───────────────────────────────────────────────────────
echo [2/5] Giai nen Python portable ...
if exist "%PYTHON_DIR%" rmdir /s /q "%PYTHON_DIR%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Expand-Archive -LiteralPath '%PY_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"
if errorlevel 1 (
  echo [LOI] Giai nen that bai.
  pause & exit /b 1
)
echo     OK

rem ── Cau hinh Python (uncomment import site) ───────────────────────────────
echo [3/5] Cau hinh Python ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "(Get-Content '%PYTHON_DIR%\python311._pth') -replace '^#import site','import site' | Set-Content '%PYTHON_DIR%\python311._pth'"
echo     OK

rem ── Cai dat pip ───────────────────────────────────────────────────────────
echo [4/5] Cai dat pip ...
"%PYTHON_EXE%" "%GET_PIP%" --quiet >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [LOI] Cai pip that bai. Xem: logs\install.log
  pause & exit /b 1
)
echo     OK

rem ── Cai dat cac goi Python ────────────────────────────────────────────────
echo [5/5] Cai dat packages ^(co the mat 5-10 phut^) ...
echo     Dang chay... vui long doi.
"%PYTHON_EXE%" -m pip install --no-warn-script-location --quiet -r requirements_core.txt >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [LOI] Cai packages that bai. Xem: logs\install.log
  pause & exit /b 1
)
echo     OK

rem ── pywin32 post-install (non-fatal) ──────────────────────────────────────
if exist "%PYTHON_DIR%\Scripts\pywin32_postinstall.py" (
  "%PYTHON_EXE%" "%PYTHON_DIR%\Scripts\pywin32_postinstall.py" -install >> "%LOG%" 2>&1
)

rem ── Ghi flag hoan thanh ───────────────────────────────────────────────────
echo 1 > "%DONE_FLAG%"

rem ── Tao shortcut tren Desktop ────────────────────────────────────────────
echo Tao shortcut "BSMQ Tool" tren Desktop...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\BSMQ Tool.lnk'); $sc.TargetPath = 'wscript.exe'; $sc.Arguments = '\"' + '%~dp0launcher.vbs' + '\"'; $sc.WorkingDirectory = '%~dp0'; $sc.IconLocation = '%SystemRoot%\System32\shell32.dll,167'; $sc.Description = 'BSMQ Procurement Tool v6'; $sc.Save()"
echo     OK

echo.
echo =============================================
echo   CAI DAT HOAN TAT!
echo =============================================
echo   Icon "BSMQ Tool" da duoc them vao Desktop.
echo   Nhan doi-click de mo ung dung.
echo   Trinh duyet se tu dong mo.
echo =============================================
echo.
pause
exit /b 0
