# BSMQ Tool1

Procurement automation tool for Samsung Electronics Vietnam RFQ workflow (AMA Bac Ninh).

Single-user Windows desktop app built with Python + Streamlit.

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11.9 |
| LibreOffice | 7.x (for PDF export) |
| Gemini API key(s) | 1–4 keys |

Install dependencies:

```
pip install -r requirements.txt
```

---

## Run

```
streamlit run app.py --server.port 8501
```

Or double-click `run.bat`.

Open browser at `http://localhost:8501`

---

## Configuration (`config.json`)

Key settings to configure on first run:

| Key | Description |
|---|---|
| `rfq_folder` | Path to monthly RFQ folder (OneDrive, read-only) |
| `gemini_keys` | List of Gemini API keys for AI classification |
| `libreoffice_path` | Path to `soffice.exe` (auto-detected if blank) |
| `cam_ket_template` | Filename of CAM KET template in `templates/` |
| `quotation_template` | Filename of Quotation template in `templates/` |
| `db_path` | SQLite database path (default: `./bsmq.db`) |
| `log_dir` | Audit log directory (default: `logs/`) |

---

## Project Structure

```
app.py                        Main Streamlit shell (5 tabs)
config.json                   Runtime config (not committed)
requirements.txt

modules/
  config.py                   Config singleton: get_config(), save_config(), resolve_soffice()
  database.py                 SQLite + FTS5 layer (products, po_history, job_log)
  ai_classifier.py            Gemini batch classifier with 4-key rotation + RPM limiter
  watchdog_sync.py            Folder monitor (SQLite event storage + watchdog observer)
  folder_browser.py           OneDrive folder scanner
  data_validation.py          Input validation (F06-F12)
  notifications.py            Windows toast notifications

tools/
  tool1_autofill/
    engine.py                 Auto-fill logic: parse RFQ, fill templates, export PDF
    app.py                    Tool 1 UI tab
    gc_l2_wizard.py           Gia Cong L2 wizard (3-step workflow)
  tool2_pricetracker/
    engine.py                 BQMS analytics engine (Excel parsing, image capture)
    app.py                    Analytics + BC BQMS 2026 monitor UI tabs
  tool3_pofilter/
    engine.py                 PO filter engine (wraps ai_classifier + rules)
    app.py                    PO filter UI tab

tests/
  test_config.py              modules/config tests
  test_database.py            modules/database tests (31 tests total)
  test_ai_classifier.py       RPM limiter + key rotation tests

templates/                    Excel templates (read by tool1)
outputs/                      Generated files (auto-created)
logs/                         Audit logs (auto-created)
plans/                        Implementation plans
```

---

## Run Tests

```
python -m pytest tests/ -v
```

Expected: **31 passed**

---

## OneDrive Notes

- All OneDrive paths are **read-only** — the app never writes to OneDrive
- `rfq_folder` points into OneDrive but outputs go to `outputs/` (local)
- Folder monitoring watches OneDrive for new files (events stored locally in `bsmq_monitor.db`)
