# Phase 2: install.bat + run.bat Scripts

**Part of:** [BSMQ Packaging Plan](./plan.md)
**Status:** Pending
**Depends on:** Phase 1

---

## Overview

Two scripts govern the user experience:

- **`install.bat`** — one-time setup. Extracts embedded Python, edits _pth, bootstraps pip,
  installs requirements_core.txt, runs pywin32 post-install, writes done-flag. Idempotent.

- **`run.bat`** — daily launch. Checks done-flag (prompts install if missing), starts
  FastAPI backend using embedded Python, opens browser to http://localhost:8000.
  Preserves existing run.bat logic (health-check loop, port cleanup, auto-restart).

Both use `%~dp0` to compute the distribution root — work regardless of folder location.

---

## Key Insights

1. **Current run.bat has hardcoded Python path** (`C:\Users\Admin\AppData\...`). Only change
   needed: replace with `%~dp0python\python.exe` + add install-check gate.

2. **install.bat must be idempotent.** If `python\_setup_done.flag` exists, skip to done message.

3. **No admin rights required** for extracting ZIP and running pip in a local folder.
   pywin32 post-install is non-fatal.

4. **Port 8000** (uvicorn/FastAPI), not 8501 (Streamlit).

5. **Log install output** to `logs\install.log` for support.

---

## Architecture

### install.bat flow

```
Check _setup_done.flag → exists? → "Already installed. Run run.bat" → exit 0
Check _setup\python-3.11.9-embed-amd64.zip → missing? → error → exit 1
Create python\ dir
PowerShell: Expand-Archive → python\
PowerShell: Edit python311._pth (uncomment import site)
python\python.exe _setup\get-pip.py
  → fail? → "pip bootstrap failed" → exit 1
python\python.exe -m pip install -r requirements_core.txt >> logs\install.log
  → fail? → "Package install failed, see logs\install.log" → exit 1
python\python.exe Scripts\pywin32_postinstall.py -install (non-fatal)
echo 1 > python\_setup_done.flag
echo "Setup complete. Run run.bat to start BSMQ."
pause → exit 0
```

### run.bat flow

```
Set PYTHON = %~dp0python\python.exe
Set PORT   = 8000
Check _setup_done.flag → missing? → "Run install.bat first" → pause → exit 1
Create logs\ if not exists
Health-check http://127.0.0.1:8000/api/health
  → running: open browser → wait_loop
Kill stale process on port 8000
:loop
  Start browser (first time only)
  %PYTHON% -m uvicorn app_api:app --host 127.0.0.1 --port 8000
  On exit: wait 3s → goto :loop
```

---

## Implementation Steps

### Step 2.1 — Write install.bat

Key snippets:

```bat
@echo off
setlocal
cd /d %~dp0

set "PYTHON_DIR=%~dp0python"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "DONE_FLAG=%PYTHON_DIR%\_setup_done.flag"
set "LOG=%~dp0logs\install.log"

if exist "%DONE_FLAG%" (
  echo [BSMQ] Setup already complete. Run run.bat to start.
  pause & exit /b 0
)

if not exist "_setup\python-3.11.9-embed-amd64.zip" (
  echo [BSMQ] ERROR: Missing _setup\python-3.11.9-embed-amd64.zip
  pause & exit /b 1
)

echo [BSMQ] Step 1/5: Extracting Python...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Expand-Archive '_setup\python-3.11.9-embed-amd64.zip' -DestinationPath 'python' -Force"

echo [BSMQ] Step 2/5: Configuring Python...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "(Get-Content '%PYTHON_DIR%\python311._pth') -replace '^#import site','import site' | Set-Content '%PYTHON_DIR%\python311._pth'"

echo [BSMQ] Step 3/5: Installing pip...
"%PYTHON_EXE%" "_setup\get-pip.py" >> "%LOG%" 2>&1
if errorlevel 1 ( echo [BSMQ] ERROR: pip bootstrap failed. See logs\install.log & pause & exit /b 1 )

echo [BSMQ] Step 4/5: Installing packages (5-10 minutes)...
"%PYTHON_EXE%" -m pip install --no-warn-script-location -r requirements_core.txt >> "%LOG%" 2>&1
if errorlevel 1 ( echo [BSMQ] ERROR: Package install failed. See logs\install.log & pause & exit /b 1 )

echo [BSMQ] Step 5/5: Finalizing...
"%PYTHON_EXE%" "%PYTHON_DIR%\Scripts\pywin32_postinstall.py" -install >> "%LOG%" 2>&1

echo 1 > "%DONE_FLAG%"
echo.
echo [BSMQ] Setup complete! Double-click run.bat to start.
pause
```

### Step 2.2 — Update run.bat (replace hardcoded Python path)

Replace:
```bat
set "PYTHON=C:\Users\Admin\AppData\..."
```
With:
```bat
set "PYTHON=%~dp0python\python.exe"
```

Add after variable declarations:
```bat
if not exist "%~dp0python\_setup_done.flag" (
  echo [BSMQ] ERROR: Run install.bat first before launching.
  pause & exit /b 1
)
```

Keep all existing health-check, port-kill, auto-restart, browser-open logic.

### Step 2.3 — Write README_SETUP.txt

```
BSMQ PROCUREMENT TOOL — HƯỚNG DẪN CÀI ĐẶT / SETUP INSTRUCTIONS
================================================================

LẦN ĐẦU SỬ DỤNG / FIRST TIME SETUP:
1. Giải nén (Extract) file ZIP ra thư mục (vd: Desktop\BSMQ_Tool)
2. Double-click: install.bat
   - Cần kết nối internet, mất khoảng 5-10 phút
   - Chờ hiện thông báo "Setup complete"
3. Double-click: run.bat
4. Trình duyệt tự mở tại http://localhost:8000
5. Làm theo hướng dẫn trong trình duyệt

SỬ DỤNG HÀNG NGÀY / DAILY USE:
- Double-click run.bat
- Đóng cửa sổ đen để tắt tool

YÊU CẦU / REQUIREMENTS:
- Windows 10 (64-bit)
- Kết nối internet (lần đầu)
- Google Chrome (cho Tool 4 - PO Tracker)

LỖI / TROUBLESHOOTING:
- Xem logs\install.log nếu install.bat lỗi
- Xem logs\api_runtime.log nếu app lỗi
```

---

## Todo List

- [ ] Write install.bat with all 5 stages and error checks
- [ ] Update run.bat: replace Python path + add install-check gate
- [ ] Test install.bat on clean VM (no Python)
- [ ] Test run.bat after install.bat completes
- [ ] Test re-running install.bat (idempotency)
- [ ] Write README_SETUP.txt in Vietnamese + English

---

## Success Criteria

- User extracts ZIP, runs install.bat, sees "Setup complete", runs run.bat, browser opens
- No Python knowledge required
- install.bat is idempotent
- run.bat shows clear error if install not done first

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| User runs run.bat before install.bat | High | High | Done-flag check with clear message |
| Port 8000 blocked by firewall | Low | High | Bind to 127.0.0.1 only; document in README |
| pip install hangs on slow network | Medium | Medium | Log output visible; README note on timing |

---

## Next Steps

Phase 3: First-run wizard in the browser for OneDrive paths and API key configuration.
