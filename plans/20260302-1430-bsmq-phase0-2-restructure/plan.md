# BSMQ Phase 0–2: Restructure + Database + Tool 1

**Date:** 2026-03-02
**Priority:** HIGH — foundational work, unblocks all future phases
**Status:** 🟡 Pending implementation

---

## Overview

Refactor monolith `app.py` (1567 LOC) into modular architecture, add SQLite+FTS5 database layer, and complete Tool 1 Auto Fill per spec.

**Stack:** Python 3.11.9 · Streamlit 1.54.0 · SQLite FTS5 ✅ · openpyxl · watchdog

---

## Phases

| # | Name | Status | File |
|---|------|--------|------|
| 0 | Project Restructure | ⬜ Pending | [phase-00](./phase-00-project-restructure.md) |
| 1 | Database Layer | ⬜ Pending | [phase-01](./phase-01-database-layer.md) |
| 2 | Tool 1 Auto Fill | ⬜ Pending | [phase-02](./phase-02-tool1-autofill.md) |

---

## Key Dependencies

```
Phase 0 → must complete first (creates folder structure)
Phase 1 → depends on Phase 0 (modules/ dir must exist)
Phase 2 → depends on Phase 0 (tools/ dir must exist), uses Phase 1 DB
```

---

## Files Affected (Summary)

**Create:** `tools/tool1_autofill/engine.py`, `tools/tool1_autofill/app.py`, `modules/database.py`, `modules/data_validation.py`, `modules/watchdog_sync.py`, `.env.example`
**Modify:** `app.py` (full rewrite as shell), `config.json`, `requirements.txt`, `run.bat`
**Preserve:** `templates/`, `bsmq_monitor.db` → renamed `bsmq_monitor_old.db`
**Create new:** `bsmq.db` (new schema), `outputs/`, `cache/`, `logs/`, `backups/`

---

## Reports

- [Scout Report](./reports/scout-report.md) — codebase analysis 2026-03-02
