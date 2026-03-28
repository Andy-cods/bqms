# Phase 1: Embedded Python Setup

**Part of:** [BSMQ Packaging Plan](./plan.md)
**Status:** Pending
**Depends on:** Nothing (first phase)

---

## Overview

Bundle Python 3.11 embeddable ZIP (`python-3.11.9-embed-amd64.zip`, ~8.3 MB) inside the
distribution. Does NOT include pip and does NOT have `site-packages` on `sys.path` by default.
This phase establishes the exact steps to make it pip-ready and package-capable.

Embedded Python lives at `python/` relative to distribution root. NEVER added to user's
system PATH.

---

## Key Insights

1. **`python311._pth` must be edited.** After extracting ZIP, `python/python311._pth` has
   `#import site` commented out. Pip will not work until uncommented to `import site`.
   install.bat performs this edit via PowerShell.

2. **Bootstrap order matters:**
   a. Extract embeddable ZIP to `python/`
   b. Edit `python311._pth` — uncomment `import site`
   c. Run `python get-pip.py`
   d. Run `python -m pip install -r requirements_core.txt`
   e. Run pywin32 post-install script

3. **Architecture: amd64 only.** Target is Windows 10 x64.

4. **Version pinned.** Bundle `python-3.11.9-embed-amd64.zip` exactly — not "latest".

5. **Packages install to** `python/Lib/site-packages/`. No separate venv needed.

6. **SSL certificates.** `certifi` (pulled in by requests) fixes HTTPS in the app.

---

## Requirements

- `_setup/python-3.11.9-embed-amd64.zip` present in distribution folder
- `_setup/get-pip.py` present
- PowerShell available on target machine (built-in on Win10)
- Internet access during install

---

## Architecture

```
_setup/
  python-3.11.9-embed-amd64.zip   (~8.3 MB, bundled)
  get-pip.py                       (~2.6 MB, bundled)

install.bat performs:
  Step 1: PowerShell Expand-Archive → python/
  Step 2: PowerShell edit python311._pth (uncomment import site)
  Step 3: python\_setup\get-pip.py
  Step 4: python -m pip install -r requirements_core.txt
  Step 5: python pywin32_postinstall.py -install
  Step 6: Write python\_setup_done.flag
```

---

## Implementation Steps

### Step 1.1 — Split requirements.txt into core and optional

`requirements_core.txt`:
```
streamlit>=1.32
openpyxl>=3.1
pandas>=2.0
pillow>=10.0
watchdog>=4.0
sqlite-utils>=3.30
plotly>=5.0.0
google-generativeai>=0.5.0
selenium>=4.18.0
webdriver-manager>=4.0.1
pdfplumber>=0.10.0
python-dotenv>=1.0.0
requests>=2.31.0
win10toast>=0.9
plyer>=2.1.0
pywin32>=306
fastapi>=0.110.0
uvicorn>=0.29.0
```

`requirements_optional.txt`:
```
# Heavy optional — only needed for Price Tracker (Tool 2)
crawl4ai>=0.4.0
playwright>=1.40.0
```

### Step 1.2 — Download and bundle setup assets (developer machine)

```powershell
Invoke-WebRequest https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip -OutFile _setup\python-3.11.9-embed-amd64.zip
Invoke-WebRequest https://bootstrap.pypa.io/get-pip.py -OutFile _setup\get-pip.py
```

### Step 1.3 — _pth edit pattern for install.bat

```bat
powershell -NoProfile -Command ^
  "(Get-Content '%PYTHON_DIR%\python311._pth') -replace '^#import site','import site' | ^
  Set-Content '%PYTHON_DIR%\python311._pth'"
```

### Step 1.4 — pywin32 post-install path

After `pip install pywin32`, post-install script is at:
`python\Scripts\pywin32_postinstall.py`

```bat
"%PYTHON_EXE%" "%PYTHON_DIR%\Scripts\pywin32_postinstall.py" -install
```

---

## Todo List

- [ ] Download `python-3.11.9-embed-amd64.zip` and verify SHA256
- [ ] Download `get-pip.py`
- [ ] Test `python311._pth` PowerShell edit on fresh extract
- [ ] Test full install sequence on clean Windows 10 (no Python installed)
- [ ] Verify pywin32 post-install succeeds with embedded Python
- [ ] Confirm all app imports work after install

---

## Success Criteria

- `python/python.exe` exists and runs after install
- `python/python.exe -c "import streamlit; import fastapi"` exits 0
- `python/python.exe -c "import site; print(site.getsitepackages())"` shows `python/Lib/site-packages`
- `python/` folder size after install: under 800 MB

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| pywin32 post-install fails | Medium | Low | Non-fatal; plyer fallback works for notifications |
| pip SSL error on corporate proxy | Medium | High | Bundle certifi; document proxy workaround |
| Python 3.11.9 zip SHA mismatch | Low | High | Verify SHA256 in build script |

---

## Next Steps

Phase 2: Write install.bat and run.bat using the embedded Python path established here.
