# Phase 5: Build + Distribute ZIP

**Part of:** [BSMQ Packaging Plan](./plan.md)
**Status:** Pending
**Depends on:** Phases 1–4 complete and tested

---

## Overview

Assemble the distributable ZIP from source, applying all changes from Phases 1–4.
Strip developer-specific files. Produce a single ZIP under 50 MB.

The `python/` directory is NOT included (created on user machine by install.bat).
`_setup/python-3.11.9-embed-amd64.zip` and `_setup/get-pip.py` ARE included (~11 MB total).

**ZIP name:** `BSMQ_Tool_v6_YYYYMMDD.zip`

---

## Distribution Folder Structure

```
BSMQ_Tool_v6/
├── install.bat
├── run.bat
├── README_SETUP.txt
├── app_api.py
├── BSMQ_Dashboard_v6.html
├── config.json                          (machine paths blanked)
├── requirements_core.txt
├── requirements_optional.txt
│
├── modules/
│   ├── __init__.py
│   ├── ai_classifier.py
│   ├── config.py
│   ├── data_validation.py
│   ├── database.py
│   ├── folder_browser.py
│   ├── notifications.py
│   └── watchdog_sync.py
│
├── tools/
│   ├── tool1_autofill/
│   ├── tool2_pricetracker/
│   ├── tool3_pofilter/
│   └── tool4_po_tracker/
│       ├── engine.py                    (Phase 4 try/except added)
│       ├── app.py
│       └── bsmq_api_client.py
│
├── templates/
│   ├── CAM KẾT BÁN HÀNG CHÍNH HÃNG (GENUINE SALES COMMITMENT).xlsx
│   └── Commercial Quotation Form.xlsx
│
├── _setup/
│   ├── python-3.11.9-embed-amd64.zip
│   └── get-pip.py
│
├── logs/            (.gitkeep)
├── outputs/         (.gitkeep)
├── cache/           (.gitkeep)
└── backups/         (.gitkeep)
```

## Files Explicitly EXCLUDED

```
python/                      (created by install.bat on user machine)
__pycache__/ (all, recursive)
*.pyc, *.pyo
.git/, .gitignore
bsmq.db, bsmq_monitor.db, bsmq_monitor_old.db
logs/*.log, outputs/*, cache/*, backups/*
app_v1_backup.py
BSMQ_Dashboard_v5.html
tests/, pytest.ini
plans/
Claude-Kit/
tools/tool4_po_tracker/excel_state.json
.env, credentials.json
```

## Size Estimate

| Item | Size |
|------|------|
| `_setup/python-3.11.9-embed-amd64.zip` | ~8.3 MB |
| `_setup/get-pip.py` | ~2.6 MB |
| All .py source files | ~300 KB |
| `BSMQ_Dashboard_v6.html` | ~90 KB |
| Templates (2 xlsx) | ~200 KB |
| **Total (compressed)** | **~12–15 MB** |

---

## Build Script: build_dist.ps1

```powershell
$version = "v6_$(Get-Date -Format 'yyyyMMdd')"
$stagingDir = "BSMQ_Tool_$version"
$zipName    = "BSMQ_Tool_$version.zip"
$src        = "."

# 1. Create staging dir
if (Test-Path $stagingDir) { Remove-Item $stagingDir -Recurse -Force }
New-Item -ItemType Directory $stagingDir | Out-Null

# 2. Copy source (excluding git, pycache, databases, secrets)
$excludeDirs  = @(".git", "__pycache__", "python", "tests", "plans", "Claude-Kit",
                  ".pytest_cache", "node_modules")
$excludeFiles = @("bsmq.db","bsmq_monitor.db","bsmq_monitor_old.db",
                  "app_v1_backup.py","BSMQ_Dashboard_v5.html",
                  "excel_state.json",".env","credentials.json","*.pyc","*.pyo")

Get-ChildItem -Path $src -Recurse | Where-Object {
    $rel = $_.FullName.Substring((Get-Location).Path.Length + 1)
    $skip = $false
    foreach ($d in $excludeDirs) { if ($rel -like "$d*") { $skip = $true; break } }
    foreach ($f in $excludeFiles) { if ($_.Name -like $f) { $skip = $true; break } }
    if ($rel -like "$stagingDir*") { $skip = $true }
    -not $skip
} | ForEach-Object {
    $dest = Join-Path $stagingDir ($_.FullName.Substring((Get-Location).Path.Length + 1))
    if ($_.PSIsContainer) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
    else { Copy-Item $_.FullName -Destination $dest -Force }
}

# 3. Create empty placeholder dirs
foreach ($d in @("logs","outputs","cache","backups")) {
    $p = Join-Path $stagingDir $d
    New-Item -ItemType Directory -Path $p -Force | Out-Null
    "" | Out-File (Join-Path $p ".gitkeep")
}

# 4. Compress
Compress-Archive -Path $stagingDir -DestinationPath $zipName -Force
$size = [math]::Round((Get-Item $zipName).Length / 1MB, 1)
Write-Host "Built: $zipName ($size MB)"

# 5. Cleanup staging
Remove-Item $stagingDir -Recurse -Force
```

---

## Build Steps (Manual)

### Step 5.1 — Apply all phase changes
Ensure Phases 1–4 fully implemented and tested.

### Step 5.2 — Prepare clean config.json
Blank all `C:\Users\Admin\...` paths. Verify no API keys or passwords in file.

### Step 5.3 — Download _setup assets (one-time)
```powershell
Invoke-WebRequest "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip" -OutFile "_setup\python-3.11.9-embed-amd64.zip"
Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile "_setup\get-pip.py"
```

### Step 5.4 — Run build script
```powershell
.\build_dist.ps1
```

### Step 5.5 — Test on clean Windows 10 VM
- [ ] No Python installed on VM
- [ ] Extract ZIP, double-click install.bat → "Setup complete"
- [ ] Double-click run.bat → browser opens at localhost:8000
- [ ] Wizard appears (blank rfq_folder)
- [ ] Complete wizard, verify config.json saved
- [ ] Test Tool 1 (RFQ auto-fill)
- [ ] Test Tool 4 (PO Tracker) with Chrome installed

### Step 5.6 — Distribute
Send `BSMQ_Tool_v6_YYYYMMDD.zip` via email or file share.
Include `README_SETUP.txt` as a standalone file outside the ZIP.

---

## Todo List

- [ ] Write `build_dist.ps1` and test it
- [ ] Download and verify `_setup/python-3.11.9-embed-amd64.zip` (SHA256 from python.org)
- [ ] Download `_setup/get-pip.py`
- [ ] Clean `config.json` — strip all machine paths and secrets
- [ ] Run `.\build_dist.ps1` and verify ZIP size < 50 MB
- [ ] Test on clean Windows 10 VM (full flow)
- [ ] Share ZIP with end user

---

## Success Criteria

- ZIP size < 50 MB
- Clean VM install completes in under 10 minutes
- Non-technical user completes setup without documentation
- All core features (Tool 1, Tool 3, database) work after install
- Tool 4 works if Chrome is installed

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ZIP too large | Low | Low | crawl4ai excluded; check size in build script |
| Clean VM test fails | Medium | High | Fix before distributing; keep VM snapshot |
| Path with spaces in extraction dir | Low | Medium | Use `%~dp0` with quoting throughout bat scripts |
| Antivirus flags embedded Python | Low | High | Document: add BSMQ_Tool folder to AV exclusions |

---

## Security Considerations

- ZIP must NOT contain bsmq.db (user data)
- ZIP must NOT contain .env, credentials.json, API keys, passwords
- Verify config.json has no secrets before building
- README advises users not to share the installed folder (contains credentials after wizard)

---

## Updates / Patching

For future updates: distribute only changed .py files in a patch folder with instructions.
Users do NOT need to re-run install.bat for app code changes — only for new package dependencies.
