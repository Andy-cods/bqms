# BSMQ Packaging: Windows Distributable Folder

**Date:** 2026-03-21
**Priority:** HIGH — enables distribution to non-technical users
**Status:** In Planning

---

## Overview

Package the BSMQ Procurement Automation Tool as a self-contained Windows folder that
non-technical users can receive as a ZIP, extract, and run by double-clicking a BAT file.

**Chosen approach: Embedded Python Bundle**

Bundle Python 3.11 embeddable ZIP inside the distribution folder. A one-time `install.bat`
extracts and configures Python, installs pip, and installs all Python packages. Subsequent
runs use `run.bat` which launches the app using the embedded Python.

**Runtime architecture:**
- Backend: FastAPI (app_api.py) served by uvicorn on port 8000
- Frontend: BSMQ_Dashboard_v6.html (static HTML/JS calling the API)
- run.bat manages the FastAPI process with health-check + auto-restart loop

**Key constraints:**
1. pywin32 requires `python pywin32_postinstall.py -install` after pip install
2. crawl4ai + playwright are heavy (~200 MB) — made optional / deferred
3. Selenium 4.x uses webdriver-manager — auto-downloads ChromeDriver
4. OneDrive paths vary per machine — first-run wizard collects them
5. Python embeddable ZIP excludes pip — get-pip.py bootstraps it
6. `python311._pth` must uncomment `import site` for pip/packages to work
7. Target ZIP size: <50 MB

---

## Phases

| # | Name | Status | File |
|---|------|--------|------|
| 1 | Embedded Python Setup | Pending | [phase-01](./phase-01-embedded-python-setup.md) |
| 2 | install.bat + run.bat Scripts | Pending | [phase-02](./phase-02-install-run-scripts.md) |
| 3 | Config + First-Run Wizard | Pending | [phase-03-config-firstrun-wizard.md](./phase-03-config-firstrun-wizard.md) |
| 4 | ChromeDriver Handling | Pending | [phase-04](./phase-04-chromedriver-handling.md) |
| 5 | Build + Distribute ZIP | Pending | [phase-05](./phase-05-build-distribute-zip.md) |

---

## Dependency Order

```
Phase 1 (Python bundle strategy)
  → Phase 2 (scripts use embedded Python paths from Phase 1)
    → Phase 3 (wizard config hooks into app_api.py)
      → Phase 4 (ChromeDriver config exposed in wizard)
        → Phase 5 (build ZIP using final scripts from Phases 1–4)
```

---

## Deliverables

```
BSMQ_Tool_v6/                    ← Root distribution folder (zipped)
├── install.bat                  ← One-time setup
├── run.bat                      ← Daily launch script
├── README_SETUP.txt             ← Plain-English instructions
├── app_api.py                   ← FastAPI backend
├── BSMQ_Dashboard_v6.html       ← Frontend (wizard overlay added)
├── config.json                  ← Defaults only (no machine paths)
├── requirements_core.txt        ← Core packages
├── requirements_optional.txt    ← Optional heavy packages (crawl4ai)
├── modules/                     ← All modules
├── tools/                       ← All tools
├── templates/                   ← Excel templates (2 files)
├── _setup/
│   ├── python-3.11.9-embed-amd64.zip
│   └── get-pip.py
├── logs/                        ← Empty placeholder
├── outputs/                     ← Empty placeholder
├── cache/                       ← Empty placeholder
└── backups/                     ← Empty placeholder
```

---

## Files Changed / Created

**New:** `install.bat`, `README_SETUP.txt`, `requirements_core.txt`, `requirements_optional.txt`,
`_setup/get-pip.py`, `_setup/python-3.11.9-embed-amd64.zip`, `build_dist.ps1`

**Modified:** `run.bat` (embed-Python path), `config.json` (blanked paths),
`app_api.py` (+wizard endpoints), `modules/config.py` (+first_run detection),
`tools/tool4_po_tracker/engine.py` (+try/except ChromeDriver)

**Unchanged:** All tool engines (except tool4), templates/
