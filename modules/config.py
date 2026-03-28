"""
modules/config.py
Shared config singleton for BSMQ Tool1.
Single source of truth for config.json loading, saving, and path resolution.
"""

import json
import os
import shutil
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_CONFIG_PATH = _ROOT / "config.json"
_VERSION_PATH = _ROOT / "version.txt"

_DEFAULTS: dict = {
    "rfq_folder": "",
    "company_name": "Công ty Cổ phần AMA Bắc Ninh",
    "templates_dir": "./templates",
    "cam_ket_template": "CAM KẾT BÁN HÀNG CHÍNH HÃNG (GENUINE SALES COMMITMENT).xlsx",
    "quotation_template": "Commercial Quotation Form.xlsx",
    "output_base_path": "./outputs",
    "libreoffice_path": "C:/Program Files/LibreOffice/program/soffice.exe",
    "libreoffice_path_alt": "C:/Program Files (x86)/LibreOffice/program/soffice.exe",
    "db_path": "./bsmq.db",
    "monitor_db": "./bsmq_monitor.db",
    "log_dir": "logs",
    # Tool 4 credentials
    "bqms_username": "",
    "bqms_password": "",
    # ChromeDriver
    "chromedriver_cache_path": "",
    "chrome_headless": False,
    # Auto-update
    "update_url": "",
    "current_version": "6.0.0",
    "auto_check_updates": True,
}


def get_config() -> dict:
    """Load config.json, filling missing keys from defaults. Returns dict."""
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in _DEFAULTS.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            pass
    return dict(_DEFAULTS)


def save_config(cfg: dict) -> bool:
    """Persist cfg to config.json. Returns True on success."""
    try:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_current_version() -> str:
    """Return version from version.txt, fallback to config current_version."""
    try:
        if _VERSION_PATH.exists():
            return _VERSION_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return get_config().get("current_version", "6.0.0")


def is_first_run() -> bool:
    """True if rfq_folder is blank — config was never customized by user."""
    return not get_config().get("rfq_folder", "").strip()


def get_setup_status() -> dict:
    """Return setup completeness dict for the first-run wizard UI."""
    cfg = get_config()

    # OneDrive root detection
    onedrive_root = ""
    try:
        from modules.folder_browser import get_onedrive_root
        onedrive_root = get_onedrive_root() or ""
    except Exception:
        for env_key in ("OneDriveCommercial", "OneDriveConsumer", "OneDrive"):
            val = os.environ.get(env_key, "")
            if val and Path(val).exists():
                onedrive_root = val
                break

    # Chrome detection
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    chrome_found = bool(
        shutil.which("chrome") or
        shutil.which("google-chrome") or
        any(Path(p).exists() for p in chrome_paths)
    )

    # LibreOffice detection
    libreoffice_found = False
    try:
        resolve_soffice()
        libreoffice_found = True
    except FileNotFoundError:
        pass

    return {
        "first_run": is_first_run(),
        "rfq_folder": cfg.get("rfq_folder", ""),
        "company_name": cfg.get("company_name", ""),
        "gemini_keys_count": len([k for k in cfg.get("gemini_keys", []) if k]),
        "onedrive_root": onedrive_root,
        "chrome_found": chrome_found,
        "libreoffice_found": libreoffice_found,
        "sheets_configured": bool(cfg.get("sheets_id", "")),
        "bqms_configured": bool(cfg.get("bqms_username", "")),
        "current_version": get_current_version(),
        "update_url": cfg.get("update_url", ""),
        "auto_check_updates": cfg.get("auto_check_updates", True),
    }


def resolve_soffice(cfg_path: str = None) -> str:
    """Return a valid soffice.exe path, with auto-detection fallback.

    Priority: cfg_path arg -> config.json values -> PATH -> glob scan.
    Raises FileNotFoundError if LibreOffice cannot be found.
    """
    candidates = []
    if cfg_path:
        candidates.append(cfg_path)
    cfg = get_config()
    candidates.append(cfg.get("libreoffice_path", ""))
    candidates.append(cfg.get("libreoffice_path_alt", ""))

    for path in candidates:
        if path and Path(path).exists():
            return path

    found = shutil.which("soffice")
    if found:
        return found

    for p in Path("C:/Program Files").glob("LibreOffice*/program/soffice.exe"):
        return str(p)
    for p in Path("C:/Program Files (x86)").glob("LibreOffice*/program/soffice.exe"):
        return str(p)

    raise FileNotFoundError(
        "LibreOffice soffice.exe not found. Set libreoffice_path in config.json "
        "or add LibreOffice to your system PATH."
    )
