# Phase 01 — Database Layer

**Context:** [plan.md](./plan.md) | Depends on: [Phase 00](./phase-00-project-restructure.md)
**Date:** 2026-03-02 | **Priority:** HIGH
**Status:** ⬜ Pending | **Review:** ⬜ Not reviewed

---

## Overview

Implement three modules:
1. `modules/database.py` — SQLite + FTS5 schema (products, po_history, job_log)
2. `modules/data_validation.py` — F06–F12 input file validation
3. `modules/watchdog_sync.py` — merged watcher.py + db_monitor.py unified API

---

## Key Insights

- **FTS5 confirmed working** on Python 3.11.9 (tested `CREATE VIRTUAL TABLE USING fts5`)
- `bsmq_monitor.db` schema (watched_folders + file_events) must be preserved in `watchdog_sync.py` — same table names/columns so existing data in `bsmq_monitor_old.db` can be migrated
- `database.py` creates a NEW `bsmq.db` — separate from monitoring DB
- FTS5 `content=` external content table needs manual trigger or `rebuild_fts_index()` call on updates
- `data_validation.py` must NOT import Streamlit — pure Python

---

## Requirements

**Functional:**
- `init_sqlite_db()` idempotent — safe to call multiple times (`IF NOT EXISTS`)
- FTS5 search returns results in < 100ms for 10k rows
- `watchdog_sync.py` drop-in replacement: `from modules.watchdog_sync import start_or_refresh, is_running, drain_queue` works
- File lock detection works on Windows (exclusive open attempt)
- `run_full_validation()` returns structured result, not raises

**Non-functional:**
- No global state in `database.py` — use connection context manager
- `watchdog_sync.py` observer is singleton (existing pattern preserved)
- All DB operations handle `sqlite3.OperationalError` gracefully

---

## Architecture

### `modules/database.py`

```python
# Connection factory — no persistent global connection
def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # dict-like rows
    return conn

# Schema
"""
products (id, code UNIQUE, name, spec, type CHECK('gc','tm'),
          maker, unit DEFAULT 'EA', price, price_source,
          price_updated, price_status DEFAULT 'none',
          win_count DEFAULT 0, lose_count DEFAULT 0,
          created_at, updated_at)

products_fts USING fts5(code, name, spec, maker,
                        content='products', content_rowid='id')

po_history (id, rfq_no, bqms_code, round DEFAULT 1,
            price_submitted, deadline, status,
            ai_decision, ai_confidence, created_at)

job_log (id, job_type, job_ref, status, progress DEFAULT 0,
         message, started_at, finished_at)
"""

# Public API
def init_sqlite_db(db_path: str) -> None
def search_products(db_path, query, type_filter=None, status_filter=None) -> list[dict]
def get_db_stats(db_path) -> dict  # {total, gc, tm, ok, expired, none, query_ms}
def upsert_product(db_path, data: dict) -> int  # returns id
def rebuild_fts_index(db_path) -> None
def add_job_log(db_path, job_type, job_ref) -> int  # returns job_id
def update_job_log(db_path, job_id, status, progress=None, message=None) -> None
```

### `modules/data_validation.py`

```python
from dataclasses import dataclass, field

@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

# Public API
def validate_input_file(path: str) -> ValidationResult
def check_column_schema(df, required_keywords: dict) -> ValidationResult
def check_file_lock(path: str) -> bool  # True = locked
def check_duplicate_codes(df, col: str) -> list[str]  # list of dupe codes
def check_missing_fields(df, cols: list[str]) -> dict  # {col: count_missing}
def run_full_validation(path: str, required_cols: dict = None) -> ValidationResult
```

### `modules/watchdog_sync.py`

```python
# Merged: db_monitor.py + watcher.py
# Unified DB file = bsmq_monitor.db (new location, same schema)
# Tables: watched_folders, file_events (identical schema to bsmq_monitor_old.db)

# From db_monitor (preserved):
def add_folder(path, label, recursive=True) -> int
def get_folders(active_only=True) -> list[dict]
def set_folder_active(folder_id, active) -> None
def insert_event(folder_id, event_type, file_path, ...) -> None
def get_events(folder_id=None, limit=50, unprocessed_only=False, ext_filter=None) -> list[dict]
def mark_processed(event_id) -> None
def cleanup_old_events(days=30) -> None
def get_stats() -> dict  # {today, week, total, unread}
def count_unprocessed() -> int

# From watcher (preserved):
def start_or_refresh() -> None
def stop() -> None
def is_running() -> bool
def get_status() -> dict  # {running, watching, missing}
def drain_queue(max_items=20) -> list[dict]
```

---

## Related Code Files

| File | Action | Notes |
|------|--------|-------|
| `modules/database.py` | Create | New SQLite + FTS5 |
| `modules/data_validation.py` | Create | Pure Python, no Streamlit |
| `modules/watchdog_sync.py` | Create | Merge watcher.py + db_monitor.py |
| `db_monitor.py` | Keep (deprecated) | Old app.py still imports it |
| `watcher.py` | Keep (deprecated) | Old app.py still imports it |

> Note: old `db_monitor.py` and `watcher.py` kept until Phase 2 replaces `app.py`. Marked with `# DEPRECATED - use modules/watchdog_sync` comment at top.

---

## Implementation Steps

### Step 1 — `modules/database.py`

1. Import: `sqlite3`, `os`, `json`, `datetime`, `time`
2. `get_connection(db_path)` — `conn.row_factory = sqlite3.Row`
3. `init_sqlite_db(db_path)`:
   ```sql
   CREATE TABLE IF NOT EXISTS products (...)
   CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
       code, name, spec, maker,
       content='products', content_rowid='id'
   )
   CREATE TABLE IF NOT EXISTS po_history (...)
   CREATE TABLE IF NOT EXISTS job_log (...)
   ```
4. `search_products(db_path, query, type_filter, status_filter)`:
   ```python
   # If query empty: SELECT * with filters
   # If query non-empty: FTS5 MATCH
   sql = """
   SELECT p.*, rank FROM products p
   JOIN products_fts ON products_fts.rowid = p.id
   WHERE products_fts MATCH ?
   """
   # Apply type_filter and status_filter as AND clauses
   # Return list(dict(row)) sorted by rank
   ```
5. `get_db_stats(db_path)`:
   ```python
   t0 = time.monotonic()
   # COUNT(*), COUNT CASE type='gc', type='tm'
   # COUNT CASE price_status='ok'/'expired'/'none'
   return {..., "query_ms": int((time.monotonic()-t0)*1000)}
   ```
6. `upsert_product(db_path, data)`:
   ```python
   # INSERT OR REPLACE INTO products (...)
   # Then update FTS: DELETE + re-INSERT
   ```
7. `rebuild_fts_index(db_path)`:
   ```sql
   INSERT INTO products_fts(products_fts) VALUES('rebuild')
   ```
8. `add_job_log` / `update_job_log` — simple INSERT/UPDATE on job_log table

### Step 2 — `modules/data_validation.py`

1. `validate_input_file(path)`:
   ```python
   try:
       wb = openpyxl.load_workbook(path, read_only=True)
       return ValidationResult(ok=True)
   except Exception as e:
       return ValidationResult(ok=False, errors=[str(e)])
   ```
2. `check_file_lock(path)`:
   ```python
   try:
       with open(path, 'r+b') as f: pass
       return False  # not locked
   except (IOError, PermissionError):
       return True  # locked
   ```
3. `check_column_schema(df, required_keywords)`:
   - Fuzzy match: for each required key, check if any column header contains any keyword (case-insensitive, Unicode-normalized)
   - Return missing keys as errors
4. `check_duplicate_codes(df, col)`:
   ```python
   dupes = df[df[col].duplicated(keep=False)][col].unique().tolist()
   return dupes
   ```
5. `check_missing_fields(df, cols)` → `{col: df[col].isna().sum()}`
6. `run_full_validation(path, required_cols=None)`:
   - Call all checks in order
   - Aggregate into single `ValidationResult`
   - Warn (not error) on duplicates; error on missing required columns

### Step 3 — `modules/watchdog_sync.py`

1. Copy full content of `db_monitor.py` — add `# DEPRECATED import` note at module top
2. Copy full content of `watcher.py` — merge into same file
3. Key change: DB path becomes configurable:
   ```python
   import os, json
   def _get_db_path():
       cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
       try:
           return json.load(open(cfg_path)).get('monitor_db', './bsmq_monitor.db')
       except:
           return './bsmq_monitor.db'
   ```
4. All `_DB` references updated to call `_get_db_path()` lazily
5. Validate merged module: `from modules.watchdog_sync import start_or_refresh, count_unprocessed` works

### Step 4 — Smoke Tests

```python
# Test database.py
from modules.database import init_sqlite_db, search_products, get_db_stats
init_sqlite_db('./bsmq.db')
stats = get_db_stats('./bsmq.db')
assert stats['total'] == 0

# Test data_validation.py
from modules.data_validation import run_full_validation
# Test with a non-existent file
result = run_full_validation('./nonexistent.xlsx')
assert not result.ok

# Test watchdog_sync.py
from modules.watchdog_sync import get_stats, count_unprocessed
# Should work without errors
```

---

## Todo List

- [ ] Implement `modules/database.py` (8 functions)
- [ ] Implement `modules/data_validation.py` (6 functions + ValidationResult dataclass)
- [ ] Implement `modules/watchdog_sync.py` (merge db_monitor + watcher, 12 functions)
- [ ] Run smoke tests for all 3 modules
- [ ] Add `# DEPRECATED` notice to top of `db_monitor.py` and `watcher.py`
- [ ] Verify existing `app.py` still imports `db_monitor` / `watcher` without error

---

## Success Criteria

- `init_sqlite_db('./bsmq.db')` creates 4 objects (3 tables + 1 FTS virtual table)
- `search_products('./bsmq.db', 'test')` returns `[]` without error
- `rebuild_fts_index('./bsmq.db')` executes without error
- `run_full_validation('./nonexistent.xlsx').ok == False`
- `from modules.watchdog_sync import start_or_refresh` — no ImportError
- Existing `app.py` still launches on port 8501

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| FTS5 `content=` table rebuild logic | Medium | Medium | Use `INSERT INTO fts(fts) VALUES('rebuild')` — proven pattern |
| Windows file lock detection false positive | Low | Low | Catch both IOError and PermissionError |
| watchdog merge causes import conflict | Medium | High | Use distinct variable names, test imports after merge |
| Old app.py breaks when watcher.py is modified | Medium | High | Don't modify watcher.py — only CREATE new watchdog_sync.py |

---

## Security Considerations

- DB file at `./bsmq.db` — local only, no network exposure
- No user input directly into SQL — use parameterized queries throughout
- FTS5 MATCH query: sanitize special chars `"` → escaped before passing to MATCH

---

## Next Steps

→ Phase 2: Extract Tool 1 engine from `app.py` → `tools/tool1_autofill/engine.py`
