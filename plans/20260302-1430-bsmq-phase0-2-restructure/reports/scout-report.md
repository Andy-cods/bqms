# Scout Report — BSMQ Tool 1

**Date:** 2026-03-02
**Project:** `c:/Users/Admin/OneDrive - SONG CHAU CO., LTD/SC - Tai lieu 240916/Documents/bsmq_tool1/`

---

## File Inventory

| File | Size | LOC | Role |
|------|------|-----|------|
| app.py | 59 KB | 1567 | Monolith: Tool 1 UI + logic + tabs |
| db_monitor.py | 6.8 KB | 195 | SQLite events layer (bsmq_monitor.db) |
| watcher.py | 5.6 KB | 182 | Watchdog file monitor (singleton) |
| config.json | 396 B | 7 | Minimal config |
| requirements.txt | 96 B | 6 | 6 packages only |
| bsmq_monitor.db | 32 KB | — | SQLite: watched_folders + file_events |
| BSMQ_Dashboard_v4.html | 69 KB | 1193 | Static demo dashboard (design reference) |
| templates/*.xlsx | 460 KB | — | CAM_KET + Commercial Quotation |
| Claude-Kit/ | 1.5 MB | — | External boilerplate (not used) |

---

## app.py Structure

| Lines | Section | Notes |
|-------|---------|-------|
| 1–75 | Imports + Constants | COL_KEYWORDS for fuzzy matching |
| 76–185 | Dark CSS | Partial dark theme (not full BSMQ v4) |
| 186–340 | Config + Session State | 8 session state keys |
| 340–530 | `parse_bc_bqms()` | Header auto-detect, fuzzy col match, deadline parse |
| 540–620 | Image handling | match + PIL→openpyxl conversion |
| 620–760 | Helper functions | sanitize_filename, classify_loai_hang, date formatters |
| 760–950 | `fill_cam_ket()` | CAM_KET template fill, row insertion |
| 950–1180 | `fill_quotation()` | Commercial Quotation fill, Grand Total formula |
| 1180–1275 | PDF export | LibreOffice subprocess, retry logic |
| 1275–1360 | `process_orders()` | Orchestration: group by RFQ, run fills, progress |
| 1360–1930 | UI Tabs (4 tabs) | Sidebar + Tab1 Orders + Tab2 Export + Tab3 Logs + Tab4 Monitor |

---

## db_monitor.py Functions

- `add_folder(path, label, recursive)` → int (folder_id)
- `get_folders(active_only)` → list[dict]
- `set_folder_active(folder_id, active)`
- `insert_event(folder_id, event_type, file_path, ...)`
- `get_events(folder_id, limit, unprocessed_only, ext_filter)` → list[dict]
- `mark_processed(event_id)`
- `cleanup_old_events(days)`
- `get_stats()` → {today, week, total, unread}
- `count_unprocessed()` → int

DB tables: `watched_folders`, `file_events`

---

## watcher.py Functions

- `_BSMQHandler` class (FileSystemEventHandler) — filters .tmp, .crdownload, ~$ prefix, 2-sec debounce
- `start_or_refresh()` — start/restart watchdog.Observer
- `stop()`
- `is_running()` → bool
- `get_status()` → {running, watching, missing}
- `drain_queue(max_items)` → list[dict]

Auto-starts on module import.

---

## config.json (Current)

```json
{
  "rfq_folder": "C:\\Users\\Admin\\OneDrive - SONG CHAU CO., LTD\\Puplic\\BQMS\\RFQ\\RFQ 2026\\THANG 2",
  "company_name": "Công ty Cổ phần AMA Bắc Ninh",
  "last_bc_file": "BC BQMS THANG 2.xlsx",
  "templates_dir": "./templates",
  "cam_ket_template": "CAM KẾT BÁN HÀNG CHÍNH HÃNG (GENUINE SALES COMMITMENT).xlsx",
  "quotation_template": "Commercial Quotation Form.xlsx"
}
```

---

## Template Cell Mapping (from app.py source)

### CAM_KET
- Product 1: rows 16–18 (3-row merged blocks)
  - C16: STT, D16: BQMS code, F16: Spec, J16: Maker, L16: Unit Price (EMPTY), N16: Image
- Product 2: rows 19–21, same structure
- Product N+: rows auto-inserted (3 rows per product)
- L31: Date string "Ngày X Tháng Y năm Z"

### Commercial Quotation
- C4: Date (DD/MM/YYYY)
- H6: RFQ No (QT26015802)
- C7: Quotation No ("QTAMABN-SEV DDMMYYYY - QT26015802")
- A14: Product description
- Data rows from 17: A=No, B=RFQ, C=BQMS+Spec, D=Maker, E=Image, F=Unit, G=Qty, H=Unit Price (EMPTY), I=formula =G*H
- Grand Total: SUM(G17:Glast), SUM(I17:Ilast)

---

## Environment

| Item | Value |
|------|-------|
| Python | 3.11.9 |
| Streamlit | 1.54.0 |
| SQLite FTS5 | ✅ Confirmed working |
| Platform | Windows 10 (win32) |
| LibreOffice | Unknown — needs check at runtime |

---

## Unresolved Questions

1. LibreOffice installed? Path: both `Program Files` and `Program Files (x86)` checked at runtime
2. Thống kê hội hàng file: location and column structure unknown — needed for Phase 1 ETL
3. OneDrive RFQ folder structure: confirmed path `Puplic/BQMS/RFQ/RFQ 2026/THANG 2` — will change monthly
4. Google Sheets credentials: not yet set up — user action required in Phase 4
5. Gemini API keys: not yet in config — user provides in `.env`
