# Phase 00 — Project Restructure

**Context:** [plan.md](./plan.md)
**Date:** 2026-03-02 | **Priority:** CRITICAL — must run first
**Status:** ⬜ Pending | **Review:** ⬜ Not reviewed

---

## Overview

Create the new folder architecture, migrate configs, update deps — without breaking the currently working `app.py` (it stays runnable until Phase 2 replaces it).

---

## Key Insights

- Existing `app.py` (1567 LOC) stays intact until Phase 2 extraction
- `db_monitor.py` + `watcher.py` → merged into `modules/watchdog_sync.py` (Phase 1)
- `bsmq_monitor.db` must be preserved — rename to `bsmq_monitor_old.db`, NOT deleted
- `templates/` — do NOT touch (openpyxl reads these directly)
- LibreOffice path: check both `Program Files` and `Program Files (x86)`

---

## Requirements

**Functional:**
- All new dirs created with `.gitkeep` placeholders
- `config.json` expanded to full schema without losing existing keys
- `.env.example` lists all secrets (never actual values)
- `requirements.txt` includes all Phase 0–5 deps (install once)

**Non-functional:**
- Existing `app.py` still runnable (`streamlit run app.py`) after Phase 0
- No circular imports introduced
- `__init__.py` files empty (no auto-imports)

---

## Architecture

```
bsmq_tool1/
├── app.py                     ← UNCHANGED until Phase 2
├── config.json                ← UPDATED (expand schema)
├── .env.example               ← NEW
├── requirements.txt           ← UPDATED
├── run.bat                    ← UPDATED
├── bsmq_monitor_old.db        ← RENAMED from bsmq_monitor.db
├── bsmq.db                    ← NEW (empty, init in Phase 1)
│
├── tools/
│   ├── __init__.py
│   └── tool1_autofill/
│       ├── __init__.py
│       ├── engine.py          ← placeholder "# TODO Phase 2"
│       └── app.py             ← placeholder "# TODO Phase 2"
│
├── modules/
│   ├── __init__.py
│   ├── database.py            ← placeholder "# TODO Phase 1"
│   ├── data_validation.py     ← placeholder "# TODO Phase 1"
│   └── watchdog_sync.py       ← placeholder "# TODO Phase 1"
│
├── templates/                 ← UNTOUCHED
├── outputs/.gitkeep
├── cache/.gitkeep
├── logs/.gitkeep
└── backups/.gitkeep
```

---

## Related Code Files

| File | Action | Change |
|------|--------|--------|
| `config.json` | Modify | Expand to full schema |
| `requirements.txt` | Modify | Add 9 new packages |
| `run.bat` | Modify | Add --server.port, --browser.gatherUsageStats |
| `bsmq_monitor.db` | Rename | → `bsmq_monitor_old.db` |
| `app.py` | No change | Keep working until Phase 2 |
| `tools/__init__.py` | Create | Empty |
| `tools/tool1_autofill/__init__.py` | Create | Empty |
| `tools/tool1_autofill/engine.py` | Create | Placeholder |
| `tools/tool1_autofill/app.py` | Create | Placeholder |
| `modules/__init__.py` | Create | Empty |
| `modules/database.py` | Create | Placeholder |
| `modules/data_validation.py` | Create | Placeholder |
| `modules/watchdog_sync.py` | Create | Placeholder |
| `.env.example` | Create | Secret keys template |
| `outputs/.gitkeep` | Create | Dir placeholder |
| `cache/.gitkeep` | Create | Dir placeholder |
| `logs/.gitkeep` | Create | Dir placeholder |
| `backups/.gitkeep` | Create | Dir placeholder |

---

## Implementation Steps

### Step 1 — Rename existing DB
```bash
# Windows: rename bsmq_monitor.db → bsmq_monitor_old.db
mv bsmq_monitor.db bsmq_monitor_old.db
```

### Step 2 — Create directory tree
```bash
mkdir -p tools/tool1_autofill modules outputs cache logs backups
```

### Step 3 — Create `__init__.py` files
All empty. Files: `tools/__init__.py`, `tools/tool1_autofill/__init__.py`, `modules/__init__.py`

### Step 4 — Create placeholder modules
Each placeholder file:
```python
# TODO: Implement in Phase X
# See: plans/20260302-1430-bsmq-phase0-2-restructure/phase-XX-*.md
```

Files: `tools/tool1_autofill/engine.py`, `tools/tool1_autofill/app.py`,
`modules/database.py`, `modules/data_validation.py`, `modules/watchdog_sync.py`

### Step 5 — Update `config.json`
Full schema (preserve existing keys, add new ones):
```json
{
  "rfq_folder": "C:\\Users\\Admin\\OneDrive - SONG CHAU CO., LTD\\Puplic\\BQMS\\RFQ\\RFQ 2026\\THANG 2",
  "company_name": "Công ty Cổ phần AMA Bắc Ninh",
  "last_bc_file": "BC BQMS THANG 2.xlsx",
  "templates_dir": "./templates",
  "cam_ket_template": "CAM KẾT BÁN HÀNG CHÍNH HÃNG (GENUINE SALES COMMITMENT).xlsx",
  "quotation_template": "Commercial Quotation Form.xlsx",
  "output_base_path": "./outputs",
  "db_path": "./bsmq.db",
  "cache_dir": "./cache",
  "backup_dir": "./backups",
  "log_dir": "./logs",
  "quotation_prefix": "QTAMABN-SEV",
  "price_expiry_days": 60,
  "gemini_keys": [],
  "sheets_id": "",
  "sheets_creds": "./credentials.json",
  "libreoffice_path": "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
  "libreoffice_path_alt": "C:\\Program Files (x86)\\LibreOffice\\program\\soffice.exe",
  "crawler_delay_min": 2,
  "crawler_delay_max": 5,
  "etl_year_range": [2023, 2026]
}
```

### Step 6 — Create `.env.example`
```dotenv
# Gemini API Keys (rotate 4 keys = 240 rpm total)
GEMINI_KEY_1=your_gemini_key_here
GEMINI_KEY_2=your_gemini_key_here
GEMINI_KEY_3=your_gemini_key_here
GEMINI_KEY_4=your_gemini_key_here

# Google Sheets
SHEETS_ID=your_spreadsheet_id_here
GOOGLE_CREDS_PATH=./credentials.json
```

### Step 7 — Update `requirements.txt`
```
# Core
streamlit>=1.32
openpyxl>=3.1
pandas>=2.0
pillow>=10.0
watchdog>=4.0
streamlit-autorefresh>=1.0

# Database
sqlite-utils>=3.30

# Google APIs
google-auth>=2.0.0
google-auth-oauthlib>=1.0.0
gspread>=5.0.0

# AI
google-generativeai>=0.5.0

# Web crawling
crawl4ai>=0.4.0
playwright>=1.40.0

# Utils
python-dotenv>=1.0.0
requests>=2.31.0

# Windows notifications
win10toast>=0.9; sys_platform == 'win32'
plyer>=2.1.0
```

### Step 8 — Update `run.bat`
```batch
@echo off
title BSMQ Control Center
cd /d %~dp0
echo Starting BSMQ System...
python -m streamlit run app.py --server.port 8501 --server.headless false --browser.gatherUsageStats false
pause
```

### Step 9 — Create `.gitkeep` placeholders
Empty files in `outputs/`, `cache/`, `logs/`, `backups/`

### Step 10 — Verify existing app.py still works
```bash
streamlit run app.py
# Should launch on port 8501, all 4 existing tabs functional
```

---

## Todo List

- [ ] Rename `bsmq_monitor.db` → `bsmq_monitor_old.db`
- [ ] Create dirs: `tools/tool1_autofill/`, `modules/`, `outputs/`, `cache/`, `logs/`, `backups/`
- [ ] Create `__init__.py` files (3 files, all empty)
- [ ] Create placeholder module files (5 files)
- [ ] Update `config.json` with full schema
- [ ] Create `.env.example`
- [ ] Update `requirements.txt`
- [ ] Update `run.bat`
- [ ] Create `.gitkeep` in empty dirs
- [ ] Verify `streamlit run app.py` still works

---

## Success Criteria

- `streamlit run app.py` launches without errors
- All 4 existing tabs functional
- New directory structure matches target architecture
- `config.json` contains all required keys
- `import tools.tool1_autofill.engine` works (placeholder, no error)
- `import modules.database` works (placeholder, no error)

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| `app.py` breaks after rename | Low | High | Don't modify app.py in this phase |
| Import path issues (tools/modules) | Medium | Medium | Empty `__init__.py` in all dirs |
| Config.json key conflicts | Low | Low | Keep ALL existing keys, only add new |

---

## Security Considerations

- `.env.example` must NEVER contain real keys — only placeholder text
- `credentials.json` (Google Service Account) must NOT be in version control
- `config.json` has no secrets (keys come from `.env`)

---

## Next Steps

→ Phase 1: Implement `modules/database.py`, `modules/data_validation.py`, `modules/watchdog_sync.py`
