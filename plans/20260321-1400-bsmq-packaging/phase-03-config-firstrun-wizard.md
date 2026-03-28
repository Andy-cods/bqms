# Phase 3: Config + First-Run Wizard

**Part of:** [BSMQ Packaging Plan](./plan.md)
**Status:** Pending
**Depends on:** Phase 2

---

## Overview

The distributed `config.json` ships with blank machine-specific paths. On first launch, the
app detects setup is incomplete and shows a browser-based wizard. Wizard collects:

1. RFQ folder path (OneDrive, required)
2. Company name (pre-filled)
3. Gemini API keys (1–4, optional)
4. Samsung BQMS credentials (Tool 4)
5. Analytics paths (optional)

Auto-detects OneDrive root via `get_onedrive_root()` and presents folder browser.

---

## Key Insights

1. **config.json ships with blanks.** Strip all `C:\Users\Admin\...` paths.

2. **First-run detection:** `is_first_run()` checks if `rfq_folder == ""`.

3. **OneDrive auto-detect already works.** `folder_browser.get_onedrive_root()` reads env vars
   `OneDriveCommercial`, `OneDriveConsumer`, `OneDrive` — works on any Windows machine.

4. **Wizard = browser overlay + 2 FastAPI endpoints.** Frontend checks `/api/setup/status`
   on page load; shows full-screen overlay if `first_run == true`.

5. **config.json stored locally** in tool folder (not in OneDrive path) — safe for credentials.

---

## Architecture

### New config.py functions

```python
def is_first_run() -> bool:
    return not get_config().get("rfq_folder", "").strip()

def get_setup_status() -> dict:
    cfg = get_config()
    from modules.folder_browser import get_onedrive_root
    import shutil, os
    onedrive_root = get_onedrive_root() or ""
    chrome_found = bool(
        shutil.which("chrome") or
        os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe") or
        os.path.exists(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe")
    )
    return {
        "first_run": is_first_run(),
        "rfq_folder": cfg.get("rfq_folder", ""),
        "company_name": cfg.get("company_name", ""),
        "gemini_keys_count": len([k for k in cfg.get("gemini_keys", []) if k]),
        "onedrive_root": onedrive_root,
        "chrome_found": chrome_found,
        "sheets_configured": bool(cfg.get("sheets_id", "")),
    }
```

### New app_api.py endpoints

```python
@app.get("/api/setup/status")
def setup_status():
    from modules.config import get_setup_status
    return get_setup_status()

@app.post("/api/setup/wizard")
def setup_wizard(payload: dict):
    from modules.config import get_config, save_config
    cfg = get_config()
    allowed = ["rfq_folder", "company_name", "gemini_keys",
               "bc_bqms_path", "giao_hang_path", "analytics_path",
               "bqms_username", "bqms_password"]
    for k in allowed:
        if k in payload:
            cfg[k] = payload[k]
    return {"ok": save_config(cfg)}
```

### Wizard UI flow

```
Page load → GET /api/setup/status
  → first_run == true?
    → Show full-screen overlay (z-index 9999)
    → Step 1: Welcome + auto-detected OneDrive root
    → Step 2: Browse/confirm RFQ folder (uses /api/folders/scan)
    → Step 3: Company + Gemini keys
    → Step 4: Optional — Samsung credentials, analytics paths
    → Step 5: Summary + "Save & Start" → POST /api/setup/wizard
    → On success: hide overlay, reload
  → first_run == false?
    → Normal dashboard load
```

---

## Distributed config.json (clean defaults)

```json
{
  "rfq_folder": "",
  "company_name": "Công ty Cổ phần AMA Bắc Ninh",
  "last_bc_file": "",
  "templates_dir": "./templates",
  "cam_ket_template": "CAM KẾT BÁN HÀNG CHÍNH HÃNG (GENUINE SALES COMMITMENT).xlsx",
  "quotation_template": "Commercial Quotation Form.xlsx",
  "output_base_path": "./outputs",
  "db_path": "./bsmq.db",
  "monitor_db": "./bsmq_monitor.db",
  "cache_dir": "./cache",
  "backup_dir": "./backups",
  "log_dir": "./logs",
  "quotation_prefix": "QTAMABN-SEV",
  "price_expiry_days": 60,
  "gemini_keys": [],
  "sheets_id": "",
  "sheets_creds": "./credentials.json",
  "libreoffice_path": "",
  "libreoffice_path_alt": "",
  "analytics_path": "",
  "bc_bqms_path": "",
  "giao_hang_path": "",
  "bqms_username": "",
  "bqms_password": ""
}
```

---

## Related Code Files

- `modules/config.py` — add `is_first_run()`, `get_setup_status()`, and `bqms_username/password` defaults
- `modules/folder_browser.py` — `get_onedrive_root()` (already exists, call from wizard)
- `app_api.py` — add two new endpoints after existing `/api/health`
- `BSMQ_Dashboard_v6.html` — add wizard overlay JS/HTML using existing `.mod`, `.card` CSS classes

---

## Todo List

- [ ] Add `is_first_run()` and `get_setup_status()` to config.py
- [ ] Add `bqms_username`, `bqms_password` to `_DEFAULTS` in config.py
- [ ] Add `/api/setup/status` endpoint to app_api.py
- [ ] Add `/api/setup/wizard` endpoint to app_api.py
- [ ] Design and implement wizard overlay in BSMQ_Dashboard_v6.html
- [ ] Clean config.json of all machine-specific paths
- [ ] Test wizard with blank rfq_folder (simulated first-run)
- [ ] Add "Reconfigure" button in System tab

---

## Success Criteria

- Fresh install shows wizard on first browser load
- Wizard auto-detects OneDrive root
- After wizard, config.json saved with user's paths
- Dashboard loads normally after wizard
- No machine-specific paths in distributed config.json

---

## Security Considerations

- config.json is local to tool folder — not synced to OneDrive
- Gemini API keys and BQMS password stored plaintext — document: do not share tool folder
- No credentials ever in the distribution ZIP

---

## Next Steps

Phase 4: ChromeDriver handling for Tool 4 (PO Tracker).
