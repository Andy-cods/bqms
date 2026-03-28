"""
BSMQ API Backend v6.0 — FastAPI, thay thế Streamlit app.py
Chạy: uvicorn app_api:app --reload --port 8000 --host 127.0.0.1
"""
from __future__ import annotations

import asyncio
import json
import os
import glob
import re
import sqlite3
import sys
import uuid
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import unquote

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# App + Middleware
# ---------------------------------------------------------------------------
app = FastAPI(title="BSMQ API v6", version="6.0.0", docs_url=None, redoc_url=None)

# GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1024)

# CORS: restrict to localhost only (single-user local tool)
_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
)

# Static files (favicon, icons)
_STATIC_DIR = _ROOT / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Serve the main dashboard HTML
@app.get("/", response_class=FileResponse)
async def serve_index():
    return FileResponse(str(_ROOT / "BSMQ_Dashboard_v6.html"), media_type="text/html")

# In-memory job store (single-user, no persistence needed)
jobs: Dict[str, dict] = {}

# Health check cache — avoids 7 I/O ops on every System tab visit
_health_cache: dict = {}
_health_ts: float = 0.0
_HEALTH_TTL: float = 30.0  # seconds


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------
def _safe_path(user_input: str, base: Path = None) -> Path:
    """Resolve and validate a user-supplied path against path traversal.
    Raises ValueError if path escapes the base directory (if provided).
    """
    p = Path(user_input).resolve()
    if base is not None:
        base_resolved = base.resolve()
        try:
            p.relative_to(base_resolved)
        except ValueError:
            raise ValueError(f"Path escapes allowed directory: {user_input}")
    return p


def _sanitize_str(s: str, max_len: int = 1024) -> str:
    """Strip and truncate a string to prevent oversized inputs."""
    return str(s or "").strip()[:max_len]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_db_path() -> str:
    try:
        from modules.config import get_config
        cfg = get_config()
    except Exception:
        cfg = {}
    raw = cfg.get("db_path", "./bsmq.db").lstrip("./")
    return str(_ROOT / raw)


def _load_audit_entries(limit: int = 100) -> List[dict]:
    try:
        from modules.config import get_config
        cfg = get_config()
        log_dir = _ROOT / cfg.get("log_dir", "logs")
    except Exception:
        log_dir = _ROOT / "logs"
    log_path = log_dir / "audit.jsonl"
    if not log_path.exists():
        return []
    rows: List[dict] = []
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows[-limit:] if limit > 0 else rows


def _err(msg: str, code: int = 500) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=code)


def _module_state(ok: bool, detail: str = "") -> dict:
    return {
        "status": "ok" if ok else "error",
        "detail": detail,
        "ok": ok,
    }


def _norm_type(v: str) -> str:
    s = str(v or "").strip().lower()
    if s == "gc":
        return "GC"
    return "TM" if s == "tm" else str(v or "")


def _norm_price_status(v: str) -> str:
    s = str(v or "").strip().lower()
    if s == "ok" or s == "valid":
        return "valid"
    if s == "expired":
        return "expired"
    return "noprice"


def _ensure_price_history_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL,
            price REAL,
            source TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
        """
        )


def _is_blankish(v) -> bool:
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except Exception:
        pass
    s = str(v).strip()
    if s == "":
        return True
    if s.lower() in {"nan", "none", "nat", "null"}:
        return True
    return False


def _normalize_tool2_dataframe(df: pd.DataFrame, dataset: str = "analytics") -> pd.DataFrame:
    """
    Final safety layer for UI sync:
    1) remove blank/noise rows
    2) sort newest -> oldest
    """
    if df is None or len(df) == 0:
        return df

    data = df.copy()
    ds = str(dataset or "analytics").strip().lower()
    if ds == "bc":
        signal_cols = [
            "rfq_no", "bqms_code", "spec", "maker", "status_raw",
            "note", "qty_forecast", "deadline_text", "loai_hang",
        ]
    elif ds == "giao_hang":
        signal_cols = [
            "date", "rfq_no", "bqms_code", "spec", "maker",
            "qty_forecast", "in_vnd", "supplier", "status_raw", "note",
        ]
    else:
        signal_cols = [
            "date", "rfq_no", "bqms_code", "spec", "maker",
            "qty_forecast", "in_vnd", "quote_v1", "quote_v2", "quote_v3",
            "quote_v4", "supplier", "status_raw", "note",
        ]
    existing_signal = [c for c in signal_cols if c in data.columns]
    if not existing_signal:
        existing_signal = list(data.columns)

    keep_mask = []
    for _, row in data.iterrows():
        has_signal = False
        for c in existing_signal:
            if not _is_blankish(row.get(c)):
                has_signal = True
                break
        keep_mask.append(has_signal)
    data = data[pd.Series(keep_mask, index=data.index)]

    if len(data) == 0:
        return data.reset_index(drop=True)

    if "date" in data.columns:
        data["__sort_date"] = pd.to_datetime(data["date"], errors="coerce")
    else:
        data["__sort_date"] = pd.NaT
    if "excel_row" in data.columns:
        data["__sort_row"] = pd.to_numeric(data["excel_row"], errors="coerce")
    else:
        data["__sort_row"] = -1
    data = data.sort_values(["__sort_date", "__sort_row"], ascending=[False, False], na_position="last")
    data = data.drop(columns=["__sort_date", "__sort_row"], errors="ignore").reset_index(drop=True)
    return data


def _gc_norm_rfq(v: str) -> str:
    s = str(v or "").strip().upper()
    return re.sub(r"[^A-Z0-9]", "", s)


def _gc_find_bqms_root() -> str:
    try:
        from modules.config import get_config
        cfg = get_config()
    except Exception:
        cfg = {}

    candidates = []
    cfg_root = str(cfg.get("rfq_folder", "") or "").strip()
    if cfg_root:
        candidates.append(cfg_root)
    # Auto-detect OneDrive Song Chau on any machine
    from modules.folder_browser import get_bqms_root
    auto = get_bqms_root()
    if auto:
        candidates.append(auto)
    # Legacy fallback paths
    home = os.path.expanduser("~")
    candidates.extend([
        os.path.join(home, "OneDrive - SONG CHAU CO., LTD", "Puplic", "BQMS"),
        os.path.join(home, "OneDrive - SONG CHAU CO., LTD", "Public", "BQMS"),
    ])
    seen = set()
    for raw in candidates:
        p = os.path.normpath(str(raw))
        if p.lower() in seen:
            continue
        seen.add(p.lower())
        if os.path.isdir(p):
            if os.path.basename(p).lower() == "rfq":
                return os.path.dirname(p)
            return p
    return os.path.normpath(candidates[0]) if candidates else ""


def _gc_get_rfq_root() -> str:
    bqms_root = _gc_find_bqms_root()
    p = os.path.join(bqms_root, "RFQ")
    if os.path.isdir(p):
        return os.path.normpath(p)
    # fallback if config already points to RFQ
    if os.path.basename(bqms_root).lower() == "rfq" and os.path.isdir(bqms_root):
        return os.path.normpath(bqms_root)
    return os.path.normpath(p)


def _gc_rfq_year_dirs(rfq_root: str) -> list[str]:
    if not os.path.isdir(rfq_root):
        return []
    out = []
    for n in os.listdir(rfq_root):
        p = os.path.join(rfq_root, n)
        if os.path.isdir(p) and re.search(r"\brfq\b", n.lower()):
            out.append(p)
    out.sort(reverse=True)
    return out


def _gc_month_dirs(year_dir: str) -> list[str]:
    if not os.path.isdir(year_dir):
        return []
    out = []
    for n in os.listdir(year_dir):
        p = os.path.join(year_dir, n)
        if os.path.isdir(p) and re.search(r"thang\s*\d+", n.lower()):
            out.append(p)
    out.sort(
        key=lambda x: int(re.search(r"(\d+)", os.path.basename(x)).group(1))
        if re.search(r"(\d+)", os.path.basename(x))
        else 0,
        reverse=True,
    )
    return out


def _gc_rfq_folders(month_dir: str) -> list[str]:
    if not os.path.isdir(month_dir):
        return []
    out = [os.path.join(month_dir, n) for n in os.listdir(month_dir) if os.path.isdir(os.path.join(month_dir, n))]
    out.sort(reverse=True)
    return out


def _gc_extract_rfq_no(folder_name: str) -> str:
    base = os.path.basename(folder_name or "")
    m = re.match(r"([A-Za-z]{1,3}\d{6,})", base)
    if m:
        return m.group(1).upper()
    return base.split(" ")[0].strip()


def _gc_find_rfq_candidates(rfq_no: str, limit: int = 30) -> list[str]:
    key = _gc_norm_rfq(rfq_no)
    if not key:
        return []
    rfq_root = _gc_get_rfq_root()
    if not os.path.isdir(rfq_root):
        return []

    cands = []
    for y in _gc_rfq_year_dirs(rfq_root):
        for m in _gc_month_dirs(y):
            for p in _gc_rfq_folders(m):
                base = os.path.basename(p)
                bkey = _gc_norm_rfq(base)
                if key in bkey:
                    score = 2 if bkey.startswith(key) else 1
                    try:
                        mt = os.path.getmtime(p)
                    except Exception:
                        mt = 0
                    cands.append((score, mt, p))
    cands.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [x[2] for x in cands[: max(1, int(limit))]]


def _gc_history_candidates(limit: int = 20) -> list[str]:
    roots = []
    primary = _gc_find_bqms_root()
    if primary:
        roots.append(primary)
    from modules.folder_browser import get_bqms_root
    auto = get_bqms_root()
    if auto and auto not in roots:
        roots.append(auto)
    home = os.path.expanduser("~")
    for sub in ["Puplic/BQMS", "Public/BQMS"]:
        p = os.path.join(home, "OneDrive - SONG CHAU CO., LTD", sub)
        if p not in roots:
            roots.append(p)

    files = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for pat in [
            os.path.join(root, "*Thong*ke*hoi*hang*.xls*"),
            os.path.join(root, "*thong*ke*hoi*hang*.xls*"),
            os.path.join(root, "*.xls*"),
        ]:
            files.extend(glob.glob(pat))

    cleaned = []
    seen = set()
    for f in files:
        p = os.path.normpath(f)
        if p.lower() in seen:
            continue
        seen.add(p.lower())
        if not os.path.isfile(p):
            continue
        if os.path.basename(p).startswith("~$"):
            continue
        cleaned.append(p)
    cleaned.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return cleaned[: max(1, int(limit))]


def _gc_num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        if pd.isna(v):
            return None
        return Decimal(str(v))
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(" ", "").replace(",", "")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _gc_build_selected_price_map(selected_rows: list, level_num: int) -> tuple[dict, list]:
    selected_price_map = {}
    details = []
    level = max(1, min(int(level_num or 2), 4))
    prev_col = f"quote_v{max(level - 1, 1)}"
    cur_col = f"quote_v{level}"

    for row in (selected_rows or []):
        code = str(row.get("bqms_code", "")).strip()
        if not code:
            continue
        if level == 1:
            v1 = _gc_num(row.get("quote_v1"))
            if v1 is None:
                continue
            value = float(v1)
            selected_price_map[code] = value
            details.append({
                "bqms_code": code,
                "source_col": "quote_v1",
                "value": value,
            })
            continue
        vp = _gc_num(row.get(prev_col))
        vc = _gc_num(row.get(cur_col))
        if vp is None or vc is None:
            continue
        value = float(vp - vc)
        selected_price_map[code] = value
        details.append({
            "bqms_code": code,
            "source_col": f"{prev_col}-{cur_col}",
            "prev": float(vp),
            "curr": float(vc),
            "value": value,
        })
    return selected_price_map, details


def _gc_log_export_sheet_status(
    rfq_no: str,
    quote_level: int,
    workflow_type: str,
    output_dir: str,
    export_result: dict,
) -> None:
    db_path = _get_db_path()
    run_id = f"gcwiz_{uuid.uuid4().hex[:12]}"
    profile = str(export_result.get("export_profile", "locked_template_fit_width"))
    rows = export_result.get("sheet_report", []) or []
    if not rows and export_result.get("files"):
        rows = [
            {
                "sheet": os.path.splitext(os.path.basename(p))[0],
                "code": "",
                "status": "ok",
                "pdf_file": p,
                "error": "",
            }
            for p in export_result.get("files", [])
        ]

    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gc_export_sheet_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                created_at TEXT,
                rfq_no TEXT,
                quote_level INTEGER,
                workflow_type TEXT,
                output_dir TEXT,
                sheet_name TEXT,
                bqms_code TEXT,
                status TEXT,
                pdf_file TEXT,
                error_msg TEXT,
                export_profile TEXT
            )
            """
        )
        now = datetime.now().isoformat(timespec="seconds")
        for r in rows:
            conn.execute(
                """
                INSERT INTO gc_export_sheet_log
                (run_id, created_at, rfq_no, quote_level, workflow_type, output_dir,
                 sheet_name, bqms_code, status, pdf_file, error_msg, export_profile)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    now,
                    rfq_no,
                    int(quote_level or 0),
                    workflow_type,
                    output_dir or "",
                    str(r.get("sheet", "")),
                    str(r.get("code", "")),
                    str(r.get("status", "")),
                    str(r.get("pdf_file", "")),
                    str(r.get("error", "")),
                    profile,
                ),
            )
        conn.commit()
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Root — serve HTML dashboard
# ---------------------------------------------------------------------------
@app.get("/")
async def serve_dashboard():
    html_path = _ROOT / "BSMQ_Dashboard_v6.html"
    if not html_path.exists():
        return JSONResponse({"error": "BSMQ_Dashboard_v6.html not found. Build it first."}, status_code=404)
    return FileResponse(str(html_path), media_type="text/html")


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health(force: bool = False):
    global _health_cache, _health_ts
    import time as _time
    if not force and _health_cache and (_time.time() - _health_ts) < _HEALTH_TTL:
        return JSONResponse(_health_cache)

    result: dict = {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "modules": {},
        "paths": {},
        "database": {},
    }
    cfg = {}

    # Config + important paths
    try:
        from modules.config import get_config
        cfg = get_config()
        result["modules"]["config"] = _module_state(True, "config.json loaded")
    except Exception as e:
        result["modules"]["config"] = _module_state(False, str(e))

    # Folder browser / OneDrive
    onedrive_root = ""
    try:
        from modules.folder_browser import get_onedrive_root
        onedrive_root = get_onedrive_root() or ""
        detail = onedrive_root if onedrive_root else "OneDrive root not found"
        result["modules"]["folder_browser"] = _module_state(True, detail)
    except Exception as e:
        result["modules"]["folder_browser"] = _module_state(False, str(e))

    # Check DB
    db_ok = False
    try:
        from modules.database import init_sqlite_db, get_db_stats
        db = _get_db_path()
        init_sqlite_db(db)
        s = get_db_stats(db)
        db_ok = True
        result["modules"]["database"] = _module_state(True, f"{s.get('total', 0)} products")
        size_mb = round((Path(db).stat().st_size / (1024 * 1024)), 2) if Path(db).exists() else 0.0
        result["database"] = {
            "status": "ok",
            "fts5": True,
            "size_mb": size_mb,
            "product_count": s.get("total", 0),
        }
    except Exception as e:
        result["modules"]["database"] = _module_state(False, str(e))
        result["database"] = {
            "status": "error",
            "fts5": False,
            "size_mb": 0,
            "product_count": 0,
        }
        db_ok = False

    # Check watchdog
    watch_ok = False
    try:
        from modules.watchdog_sync import get_status
        wd = get_status() or {}
        running = bool(wd.get("running", False))
        result["modules"]["watchdog"] = _module_state(True, f"running={running}")
        watch_ok = running
    except Exception as e:
        result["modules"]["watchdog"] = _module_state(False, str(e))
        watch_ok = False

    # Check AI classifier
    try:
        import modules.ai_classifier  # noqa
        result["modules"]["ai_classifier"] = _module_state(True, "import ok")
    except Exception as e:
        result["modules"]["ai_classifier"] = _module_state(False, str(e))

    # Check Tool 1 engine
    try:
        import tools.tool1_autofill.engine  # noqa
        result["modules"]["tool1_engine"] = _module_state(True, "import ok")
    except Exception as e:
        result["modules"]["tool1_engine"] = _module_state(False, str(e))

    # Extra paths for System page
    db_path = _get_db_path()
    log_dir = str((_ROOT / str(cfg.get("log_dir", "logs"))).resolve())
    monitor_db = str((_ROOT / str(cfg.get("monitor_db", "./bsmq_monitor.db")).lstrip("./")).resolve())
    libre_a = cfg.get("libreoffice_path", "")
    libre_b = cfg.get("libreoffice_path_alt", "")
    libre = libre_a if libre_a and Path(libre_a).exists() else (libre_b if libre_b and Path(libre_b).exists() else libre_a or libre_b or "")
    result["paths"] = {
        "one_drive_root": onedrive_root,
        "rfq_folder": cfg.get("rfq_folder", ""),
        "db_path": db_path,
        "monitor_db": monitor_db,
        "log_dir": log_dir,
        "libreoffice": libre,
    }

    # Legacy flags used by some clients
    result["db_ok"] = db_ok
    result["watchdog_ok"] = watch_ok
    if any(v.get("status") != "ok" for v in result["modules"].values()):
        result["status"] = "degraded"

    # Update server-side cache
    import time as _time
    _health_cache = result
    _health_ts = _time.time()

    return JSONResponse(result)


# ---------------------------------------------------------------------------
# GET /api/stats  — pipeline snapshot
# ---------------------------------------------------------------------------
@app.get("/api/stats")
async def get_stats():
    db_stats = {"total": 0, "ok": 0, "expired": 0, "none": 0, "gc": 0, "tm": 0, "query_ms": 0}
    watch_unprocessed = 0
    watch_folders = 0
    watch_running = False
    ai_total = ai_yes = ai_no = ai_maybe = ai_override = 0

    try:
        from modules.database import init_sqlite_db, get_db_stats
        db = _get_db_path()
        init_sqlite_db(db)
        db_stats = get_db_stats(db)
    except Exception:
        pass

    try:
        from modules.watchdog_sync import count_unprocessed, get_status
        watch_unprocessed = count_unprocessed()
        wd = get_status() or {}
        watch_folders = int(wd.get("folders", 0) or 0)
        watch_running = bool(wd.get("running", False))
    except Exception:
        pass

    audit = _load_audit_entries(limit=500)
    decisions = [
        r.get("final_decision") or r.get("decision")
        for r in audit
        if r.get("action") in ("classification", "classification_override")
    ]
    if decisions:
        c = Counter(decisions)
        ai_total = sum(c.values())
        ai_yes = c.get("yes", 0)
        ai_no = c.get("no", 0)
        ai_maybe = c.get("maybe", 0)
    ai_override = sum(1 for r in audit if r.get("action") == "classification_override")

    # Pipeline counters for dashboard cards/steps
    fill_done = sum(1 for j in jobs.values() if j.get("status") == "done")
    submit_count = 0
    try:
        db = _get_db_path()
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM po_history WHERE LOWER(status)='win'")
        submit_count = int(cur.fetchone()[0] or 0)
        conn.close()
    except Exception:
        submit_count = 0

    payload = {
        # Legacy/new dashboard shape (frontend v6 expects these keys)
        "total_products": db_stats.get("total", 0),
        "valid_prices": db_stats.get("ok", 0),
        "expired_prices": db_stats.get("expired", 0),
        "no_price": db_stats.get("none", 0),
        "ai_decisions": ai_total,
        "pipeline_receive": watch_unprocessed,
        "pipeline_classify": ai_total,
        "pipeline_price": db_stats.get("ok", 0) + db_stats.get("expired", 0),
        "pipeline_fill": fill_done,
        "pipeline_submit": submit_count,
        # Extended diagnostics
        "db": db_stats,
        "watch_unprocessed": watch_unprocessed,
        "watch_folders": watch_folders,
        "watch_running": watch_running,
        "ai_total": ai_total,
        "ai_yes": ai_yes,
        "ai_no": ai_no,
        "ai_maybe": ai_maybe,
        "ai_override": ai_override,
    }
    return JSONResponse(payload)


# ---------------------------------------------------------------------------
# GET /api/audit-log
# ---------------------------------------------------------------------------
@app.get("/api/audit-log")
async def get_audit_log(limit: int = 100):
    return JSONResponse(_load_audit_entries(limit=limit))


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------
@app.get("/api/config")
async def get_config_endpoint():
    try:
        from modules.config import get_config
        return JSONResponse(get_config())
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Database endpoints
# ---------------------------------------------------------------------------
@app.get("/api/db/stats")
async def db_stats():
    try:
        from modules.database import init_sqlite_db, get_db_stats
        db = _get_db_path()
        init_sqlite_db(db)
        s = get_db_stats(db)
        return JSONResponse({
            **s,
            "valid": s.get("ok", 0),
            "no_price": s.get("none", 0),
        })
    except Exception as e:
        return _err(str(e))


@app.get("/api/db/search")
async def db_search(q: str = "", type: str = "", status: str = "", filter: str = "", limit: int = 50):
    try:
        from modules.database import search_products
        db = _get_db_path()
        f = (filter or "").strip().lower()
        type_filter = type if type in ("gc", "tm") else None
        status_filter = status if status in ("ok", "expired", "none") else None

        # Frontend v6 filter pills contract
        if f in ("gc", "tm"):
            type_filter = f
        elif f == "valid":
            status_filter = "ok"
        elif f == "expired":
            status_filter = "expired"
        elif f in ("noprice", "none"):
            status_filter = "none"

        cap = max(1, min(limit, 500))
        results = search_products(
            q,
            type_filter=type_filter,
            status_filter=status_filter,
            db_path=db,
            limit=cap,
        )
        normalized = []
        for r in results:
            item = dict(r)
            item["type"] = _norm_type(item.get("type"))
            item["price_status"] = _norm_price_status(item.get("price_status"))
            normalized.append(item)
        # Quick total count for UI "showing N of M" indicator
        total = len(normalized)
        if len(normalized) == cap:
            try:
                conn2 = sqlite3.connect(db)
                _where, _params = [], []
                if type_filter:
                    _where.append("type = ?"); _params.append(type_filter)
                if status_filter:
                    _where.append("price_status = ?"); _params.append(status_filter)
                _wc = ("WHERE " + " AND ".join(_where)) if _where else ""
                total = conn2.execute(f"SELECT COUNT(*) FROM products {_wc}", _params).fetchone()[0]
                conn2.close()
            except Exception:
                total = len(normalized)
        return JSONResponse({"results": normalized, "count": len(normalized), "total": total})
    except Exception as e:
        return _err(str(e))


@app.get("/api/db/product/{code}")
async def db_product(code: str):
    try:
        db = _get_db_path()
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        _ensure_price_history_table(conn)
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE code = ? LIMIT 1", (code,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return _err("Product not found", 404)
        product = dict(row)
        product["type"] = _norm_type(product.get("type"))
        product["price_status"] = _norm_price_status(product.get("price_status"))
        # Price history
        try:
            cur.execute(
                "SELECT * FROM price_history WHERE product_code = ? ORDER BY created_at DESC LIMIT 20",
                (code,)
            )
            history = []
            for r in cur.fetchall():
                h = dict(r)
                history.append({
                    **h,
                    "source": h.get("source", ""),
                    "date": h.get("created_at"),
                })
        except Exception:
            history = []
        conn.close()
        payload = {**product, "price_history": history, "product": product}
        return JSONResponse(payload)
    except Exception as e:
        return _err(str(e))


@app.post("/api/db/price")
async def db_update_price(payload: dict):
    try:
        code = payload.get("code", "")
        price = payload.get("price")
        source = payload.get("source", "manual")
        notes = payload.get("notes", "")
        if not code or price is None:
            return _err("code and price required", 400)
        db = _get_db_path()
        conn = sqlite3.connect(db)
        _ensure_price_history_table(conn)
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE products SET price=?, price_status='ok', updated_at=? WHERE code=?",
            (price, now, code)
        )
        try:
            conn.execute(
                "INSERT INTO price_history (product_code, price, source, notes, created_at) VALUES (?,?,?,?,?)",
                (code, price, source, notes, now)
            )
        except Exception:
            pass
        conn.commit()
        conn.close()
        return JSONResponse({"ok": True, "code": code, "updated_at": now})
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Watchdog & Folders
# ---------------------------------------------------------------------------
@app.get("/api/watchdog/status")
async def watchdog_status():
    try:
        from modules.watchdog_sync import count_unprocessed, get_status
        wd = get_status() or {}
        return JSONResponse({
            "running": bool(wd.get("running", False)),
            "folders": int(wd.get("folders", 0) or 0),
            "unprocessed_events": count_unprocessed(),
        })
    except Exception as e:
        return _err(str(e))


@app.get("/api/watchdog/events")
async def watchdog_events(limit: int = 50):
    try:
        from modules.folder_browser import get_recent_events
        raw_events = get_recent_events(limit=limit) or []
        mapped = []
        for ev in raw_events:
            row = dict(ev)
            ts = row.get("ts") or row.get("created_at") or ""
            ts_iso = ts.replace(" ", "T") if isinstance(ts, str) and " " in ts else ts
            mapped.append({
                **row,
                "filename": row.get("file_name") or os.path.basename(row.get("file_path", "")),
                "path": row.get("file_path", ""),
                "timestamp": ts_iso,
                "folder": row.get("folder_label") or row.get("folder_path", ""),
            })
        return JSONResponse(mapped)
    except Exception as e:
        return _err(str(e))


@app.get("/api/folders/scan")
async def folders_scan():
    try:
        from modules.folder_browser import get_onedrive_root, scan_folders, get_watched_folders
        root = get_onedrive_root()
        if not root:
            return _err("OneDrive root not found")
        # Offload recursive directory walk to thread pool — avoids blocking the event loop
        loop = asyncio.get_event_loop()
        folders = await loop.run_in_executor(None, lambda: scan_folders(root, max_depth=6, max_count=800))
        watched_rows = get_watched_folders() or []
        watched = [
            (w.get("path", "") or "").rstrip("/\\")
            for w in watched_rows
            if int(w.get("is_active", w.get("active", 1)) or 0) == 1
        ]
        return JSONResponse({"root": root, "folders": folders, "watched": watched})
    except Exception as e:
        return _err(str(e))


@app.get("/api/folders/watched")
async def folders_watched():
    try:
        from modules.folder_browser import get_watched_folders
        rows = get_watched_folders() or []
        normalized = []
        for w in rows:
            row = dict(w)
            row["active"] = int(row.get("is_active", row.get("active", 1)) or 0) == 1
            normalized.append(row)
        return JSONResponse(normalized)
    except Exception as e:
        return _err(str(e))


@app.post("/api/folders/watch")
async def folders_add_watch(payload: dict):
    try:
        from modules.folder_browser import add_watch_folder
        path = payload.get("path", "")
        label = payload.get("label", os.path.basename(path))
        if not path:
            return _err("path required", 400)
        created = add_watch_folder(path, label)
        return JSONResponse({
            "ok": True,
            "created": bool(created),
            "message": None if created else "Folder is already watched",
        })
    except Exception as e:
        return _err(str(e))


@app.delete("/api/folders/watch/{folder_ref:path}")
async def folders_remove_watch(folder_ref: str):
    try:
        from modules.folder_browser import remove_watch_folder, get_watched_folders
        raw = (folder_ref or "").strip()
        if not raw:
            return _err("folder ref is required", 400)

        # 1) Numeric id (legacy behavior)
        if raw.isdigit():
            remove_watch_folder(int(raw))
            return JSONResponse({"ok": True, "removed": True})

        # 2) Path-based remove (frontend v6 behavior)
        target = os.path.normpath(unquote(raw)).rstrip("/\\").lower()
        watched = get_watched_folders() or []
        for w in watched:
            wp = os.path.normpath(str(w.get("path", ""))).rstrip("/\\").lower()
            is_active = int(w.get("is_active", w.get("active", 1)) or 0) == 1
            if wp == target and is_active:
                remove_watch_folder(int(w.get("id")))
                return JSONResponse({"ok": True, "removed": True})
        return JSONResponse({"ok": True, "removed": False, "message": "Folder not watched"})
    except Exception as e:
        return _err(str(e))


@app.post("/api/watchdog/sync")
async def watchdog_sync():
    global _health_ts
    try:
        from modules.watchdog_sync import manual_sync
        result = manual_sync(max_files=12000)
        _health_ts = 0.0  # invalidate health cache — watchdog state changed
        return JSONResponse(result)
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Tool 1 — Auto Fill
# ---------------------------------------------------------------------------
@app.post("/api/tool1/upload-bcbqms")
async def tool1_upload(file: UploadFile = File(...)):
    try:
        from tools.tool1_autofill.engine import parse_bc_bqms
        content = await file.read()
        orders = parse_bc_bqms(content)
        # Serialise datetimes
        safe = []
        for o in orders:
            row = {}
            for k, v in o.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
                else:
                    row[k] = v
            # Compatibility fields for HTML dashboard v6
            rfq = row.get("don_hang") or row.get("rfq_no") or row.get("rfq") or ""
            loai = str(row.get("loai_hang") or row.get("type") or "TM").upper()
            row["rfq"] = rfq
            row["rfq_no"] = rfq
            row["type"] = "GC" if loai == "GC" else "TM"
            row["name"] = row.get("short_name") or row.get("name") or row.get("spec", "")
            row["deadline"] = row.get("han_bg") or row.get("deadline", "")
            row["urgent"] = bool(row.get("is_urgent", False))
            safe.append(row)
        return JSONResponse({"orders": safe, "count": len(safe), "filename": file.filename})
    except Exception as e:
        return _err(str(e))


@app.post("/api/tool1/run")
async def tool1_run(payload: dict, background_tasks: BackgroundTasks):
    orders = payload.get("orders", [])
    options = payload.get("options", {})
    if not orders:
        return _err("orders list is empty", 400)
    normalized_orders = []
    for o in orders:
        row = dict(o)
        if "don_hang" not in row:
            row["don_hang"] = row.get("rfq") or row.get("rfq_no", "")
        if "loai_hang" not in row:
            row["loai_hang"] = str(row.get("type", "TM")).upper()
        if "bqms" not in row:
            row["bqms"] = row.get("bqms_code", "")
        if "short_name" not in row:
            row["short_name"] = row.get("name") or row.get("spec") or ""
        normalized_orders.append(row)

    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {
        "status": "running",
        "progress": 0.0,
        "status_msg": "Starting job...",
        "logs": [],
        "result": None,
        "files": [],
        "error": None,
        "output_dir": None,
    }
    background_tasks.add_task(_run_autofill_task, job_id, normalized_orders, options)
    return JSONResponse({"job_id": job_id})


async def _run_autofill_task(job_id: str, orders: list, options: dict):
    try:
        from tools.tool1_autofill.engine import run_auto_fill_job, load_config, set_log_callback
        cfg = load_config()
        logs: list = []

        def _cb(msg, level="info"):
            logs.append({"msg": str(msg), "level": level, "ts": datetime.now().strftime("%H:%M:%S")})
            jobs[job_id]["progress"] = min(0.9, len(logs) * 0.05)
            jobs[job_id]["status_msg"] = str(msg)
            jobs[job_id]["logs"] = logs[-20:]

        set_log_callback(_cb)

        # Filter TM only (GC not supported)
        tm_orders = [o for o in orders if str(o.get("loai_hang", "")).lower() != "gc"]

        result = run_auto_fill_job(
            products=tm_orders,
            config=cfg,
            images_map={},
            progress_callback=_cb,
        )
        jobs[job_id].update({
            "status": "done" if result.get("success") else "error",
            "progress": 1.0,
            "status_msg": "Completed" if result.get("success") else "Completed with errors",
            "result": result.get("files", []),
            "files": result.get("files", []),
            "error": "; ".join(result.get("errors", [])) if result.get("errors") else None,
            "output_dir": result.get("output_dir"),
            "rfq_no": result.get("rfq_no"),
        })
    except Exception as e:
        import traceback
        jobs[job_id].update({
            "status": "error",
            "progress": 1.0,
            "status_msg": "Job failed",
            "error": f"{e}\n{traceback.format_exc()[-500:]}",
        })


@app.get("/api/tool1/job/{job_id}")
async def tool1_job_status(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        return _err("Job not found", 404)
    out = dict(job)
    p = out.get("progress", 0)
    if isinstance(p, (int, float)) and p > 1:
        p = p / 100.0
    out["progress"] = max(0.0, min(1.0, float(p or 0)))
    out["logs"] = [
        f"[{r.get('ts', '--:--:--')}] {r.get('msg', '')}" if isinstance(r, dict) else str(r)
        for r in (out.get("logs") or [])
    ]
    out["files"] = out.get("files") or out.get("result") or []
    return JSONResponse(out)


@app.get("/api/tool1/download/{job_id}/{filename}")
async def tool1_download(job_id: str, filename: str):
    job = jobs.get(job_id)
    if not job:
        return _err("Job not found", 404)
    output_dir = job.get("output_dir")
    if not output_dir:
        return _err("No output dir for this job", 404)
    file_path = Path(output_dir) / filename
    if not file_path.exists():
        return _err("File not found", 404)
    return FileResponse(str(file_path), filename=filename)


# ---------------------------------------------------------------------------
# Tool 3 — AI Classifier
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Tool 1 - Gia Cong Wizard
# ---------------------------------------------------------------------------
@app.get("/api/tool1/gia-cong/bootstrap")
async def tool1_gc_bootstrap():
    try:
        bqms_root = _gc_find_bqms_root()
        rfq_root = _gc_get_rfq_root()
        history = _gc_history_candidates(limit=30)
        return JSONResponse({
            "ok": True,
            "bqms_root": bqms_root,
            "rfq_root": rfq_root,
            "history_candidates": history,
        })
    except Exception as e:
        return _err(str(e))


@app.get("/api/tool1/gia-cong/rfq-candidates")
async def tool1_gc_rfq_candidates(rfq_no: str = "", limit: int = 30):
    try:
        if not str(rfq_no or "").strip():
            return JSONResponse({"ok": True, "items": []})
        paths = _gc_find_rfq_candidates(rfq_no, limit=max(1, min(limit, 100)))
        items = []
        for p in paths:
            items.append({
                "path": p,
                "folder": os.path.basename(p),
                "rfq_no": _gc_extract_rfq_no(os.path.basename(p)),
                "month_folder": os.path.basename(os.path.dirname(p)),
                "label": f"{os.path.basename(p)} [{os.path.basename(os.path.dirname(p))}]",
            })
        return JSONResponse({"ok": True, "items": items})
    except Exception as e:
        return _err(str(e))


@app.post("/api/tool1/gia-cong/preview")
async def tool1_gc_preview(payload: dict):
    try:
        rfq_no = str(payload.get("rfq_no", "") or "").strip()
        raw_history = str(payload.get("history_path", "") or "").strip()
        page = max(1, int(payload.get("page", 1) or 1))
        limit = max(1, min(int(payload.get("limit", 200) or 200), 1000))
        quote_level = max(1, min(int(payload.get("quote_level", 2) or 2), 4))

        if not rfq_no:
            return _err("rfq_no is required", 400)
        if not raw_history:
            return _err("history_path is required", 400)

        history_path = os.path.normpath(raw_history)
        if not os.path.isfile(history_path):
            alt = _resolve_tool2_input_path("analytics_path", history_path)
            if alt and os.path.isfile(alt):
                history_path = alt
        if not os.path.isfile(history_path):
            return _err(f"History file not found: {raw_history}", 404)

        from tools.tool2_pricetracker.engine import load_bqms_analytics
        res = load_bqms_analytics(history_path)
        if not res.get("ok"):
            return _err(res.get("error", "Cannot load history file"), 400)

        df = _normalize_tool2_dataframe(res.get("df"), dataset="analytics")
        if df is None or df.empty:
            return JSONResponse({
                "ok": True,
                "meta": {
                    "history_path": history_path,
                    "rows_by_rfq": 0,
                    "rows_with_quote": 0,
                    "unique_bqms": 0,
                },
                "records": [],
                "total": 0,
                "page": 1,
                "pages": 1,
                "limit": limit,
                "default_pick_indices": [],
            })

        rfq_key = _gc_norm_rfq(rfq_no)
        if "rfq_no" in df.columns:
            m = df[df["rfq_no"].map(_gc_norm_rfq) == rfq_key].copy()
        else:
            m = df.iloc[0:0].copy()

        m = _normalize_tool2_dataframe(m, dataset="analytics")
        qcols = [c for c in ["quote_v1", "quote_v2", "quote_v3", "quote_v4"] if c in m.columns]
        if qcols:
            price_rows = m[m[qcols].notna().any(axis=1)]
        else:
            price_rows = m.iloc[0:0]

        show_cols = [
            "date", "rfq_no", "bqms_code", "spec", "maker", "qty_forecast",
            "quote_v1", "quote_v2", "quote_v3", "quote_v4", "note", "supplier", "round", "result",
        ]
        show_cols = [c for c in show_cols if c in m.columns]
        view = m[show_cols].copy().reset_index(drop=True)

        default_pick = []
        if not view.empty:
            prev_col = f"quote_v{max(quote_level - 1, 1)}"
            cur_col = f"quote_v{quote_level}"
            if quote_level == 1 and "quote_v1" in view.columns:
                cands = view[view["quote_v1"].notna()].index.tolist()
                if cands:
                    default_pick = [int(cands[0])]
            elif prev_col in view.columns and cur_col in view.columns:
                cands = view[view[prev_col].notna() & view[cur_col].notna()].index.tolist()
                if cands:
                    default_pick = [int(cands[0])]
            if not default_pick:
                default_pick = [0]

        paged = _df_to_paged(view, page=page, limit=limit)
        return JSONResponse({
            "ok": True,
            "meta": {
                "history_path": history_path,
                "rows_by_rfq": int(len(m)),
                "rows_with_quote": int(len(price_rows)),
                "unique_bqms": int(price_rows["bqms_code"].astype(str).str.strip().nunique()) if "bqms_code" in price_rows.columns else 0,
                "quote_level": quote_level,
            },
            "columns": show_cols,
            "default_pick_indices": default_pick,
            **paged,
        })
    except Exception as e:
        return _err(str(e))


async def _run_gc_prepare_task(job_id: str, payload: dict):
    try:
        from tools.tool1_autofill.engine import run_gia_cong_prepare_job
        logs = []

        def _cb(step_idx, total, msg):
            pct = min(0.95, float(step_idx) / max(float(total or 1), 1.0))
            logs.append({"msg": str(msg), "level": "info", "ts": datetime.now().strftime("%H:%M:%S")})
            jobs[job_id]["progress"] = pct
            jobs[job_id]["status_msg"] = str(msg)
            jobs[job_id]["logs"] = logs[-50:]

        rfq_no = str(payload.get("rfq_no", "") or "").strip()
        history_path = os.path.normpath(str(payload.get("history_path", "") or "").strip())
        rfq_folder_path = os.path.normpath(str(payload.get("rfq_folder_path", "") or "").strip())
        quote_level = max(1, min(int(payload.get("quote_level", 2) or 2), 4))
        manual_timeout_sec = max(60, min(int(payload.get("manual_timeout_sec", 300) or 300), 1800))
        workflow_type = str(payload.get("workflow_type", "gia_cong") or "gia_cong").lower().replace(" ", "_")
        selected_rows = payload.get("selected_rows") or []
        selected_price_map, price_detail = _gc_build_selected_price_map(selected_rows, quote_level)

        if not rfq_no:
            raise ValueError("rfq_no is required")
        if not os.path.isfile(history_path):
            raise ValueError(f"History file not found: {history_path}")
        if not selected_price_map:
            raise ValueError("No valid selected rows for current quote level")

        rfq_root = _gc_get_rfq_root()
        if not os.path.isdir(rfq_root):
            raise ValueError(f"RFQ root not found: {rfq_root}")

        out = run_gia_cong_prepare_job(
            rfq_no=rfq_no,
            history_path=history_path,
            rfq_root_dir=rfq_root,
            rfq_folder_override=rfq_folder_path if rfq_folder_path and os.path.isdir(rfq_folder_path) else "",
            manual_timeout_sec=manual_timeout_sec,
            selected_v2_map=selected_price_map,
            quote_level=quote_level,
            workflow_type=workflow_type,
            progress_callback=_cb,
        )
        ok = bool(out.get("success"))
        jobs[job_id].update({
            "status": "done" if ok else "error",
            "progress": 1.0,
            "status_msg": "Prepare completed" if ok else "Prepare failed",
            "logs": logs[-50:],
            "prepare_result": out,
            "result": out,
            "files": [],
            "output_dir": out.get("output_dir"),
            "excel_path": out.get("excel_path"),
            "rfq_no": rfq_no,
            "selected_price_detail": price_detail,
            "error": "; ".join(out.get("errors", [])) if out.get("errors") else None,
        })
    except Exception as e:
        jobs[job_id].update({
            "status": "error",
            "progress": 1.0,
            "status_msg": "Prepare failed",
            "error": str(e),
        })


async def _run_gc_export_task(job_id: str, prepare_result: dict, payload: dict):
    try:
        from tools.tool1_autofill.engine import run_gia_cong_export_job
        logs = []

        def _cb(step_idx, total, msg):
            pct = min(0.95, float(step_idx) / max(float(total or 1), 1.0))
            logs.append({"msg": str(msg), "level": "info", "ts": datetime.now().strftime("%H:%M:%S")})
            jobs[job_id]["progress"] = pct
            jobs[job_id]["status_msg"] = str(msg)
            jobs[job_id]["logs"] = logs[-50:]

        rfq_no = str(payload.get("rfq_no") or prepare_result.get("rfq_no") or "").strip()
        level = int(payload.get("quote_level") or prepare_result.get("level") or 2)
        workflow_type = str(payload.get("workflow_type", "gia_cong") or "gia_cong")
        excel_path = str(prepare_result.get("excel_path", "") or "")
        output_dir = str(prepare_result.get("output_dir", "") or "")
        sheet_items = prepare_result.get("sheet_items", []) or []

        exp = run_gia_cong_export_job(
            rfq_no=rfq_no,
            excel_path=excel_path,
            output_dir=output_dir,
            level=level,
            sheet_items=sheet_items,
            progress_callback=_cb,
        )
        try:
            _gc_log_export_sheet_status(
                rfq_no=rfq_no,
                quote_level=level,
                workflow_type=workflow_type,
                output_dir=output_dir,
                export_result=exp,
            )
        except Exception:
            pass

        file_paths = exp.get("files", []) or []
        file_names = [os.path.basename(str(p)) for p in file_paths if str(p).strip()]
        ok = bool(exp.get("success"))
        jobs[job_id].update({
            "status": "done" if ok else "error",
            "progress": 1.0,
            "status_msg": "Export completed" if ok else "Export failed",
            "logs": logs[-50:],
            "export_result": exp,
            "result": exp,
            "files": file_names,
            "output_dir": output_dir,
            "rfq_no": rfq_no,
            "error": "; ".join(exp.get("errors", [])) if exp.get("errors") else None,
        })
    except Exception as e:
        jobs[job_id].update({
            "status": "error",
            "progress": 1.0,
            "status_msg": "Export failed",
            "error": str(e),
        })


@app.post("/api/tool1/gia-cong/prepare")
async def tool1_gc_prepare(payload: dict, background_tasks: BackgroundTasks):
    try:
        rfq_no = str(payload.get("rfq_no", "") or "").strip()
        history_path = str(payload.get("history_path", "") or "").strip()
        selected_rows = payload.get("selected_rows") or []
        if not rfq_no:
            return _err("rfq_no is required", 400)
        if not history_path:
            return _err("history_path is required", 400)
        if not isinstance(selected_rows, list) or not selected_rows:
            return _err("selected_rows is required", 400)

        job_id = uuid.uuid4().hex[:10]
        jobs[job_id] = {
            "type": "gc_prepare",
            "status": "running",
            "progress": 0.01,
            "status_msg": "Preparing Gia Cong edit stage...",
            "logs": [],
            "result": None,
            "files": [],
            "error": None,
            "output_dir": None,
        }
        background_tasks.add_task(_run_gc_prepare_task, job_id, payload)
        return JSONResponse({"ok": True, "job_id": job_id})
    except Exception as e:
        return _err(str(e))


@app.post("/api/tool1/gia-cong/export")
async def tool1_gc_export(payload: dict, background_tasks: BackgroundTasks):
    try:
        prepare_job_id = str(payload.get("prepare_job_id", "") or "").strip()
        if not prepare_job_id:
            return _err("prepare_job_id is required", 400)
        prepare_job = jobs.get(prepare_job_id) or {}
        prepare_result = prepare_job.get("prepare_result") or prepare_job.get("result")
        if not prepare_result:
            return _err("Prepare result not found", 404)
        if not prepare_result.get("success"):
            return _err("Prepare stage not successful", 400)

        job_id = uuid.uuid4().hex[:10]
        jobs[job_id] = {
            "type": "gc_export",
            "status": "running",
            "progress": 0.01,
            "status_msg": "Exporting PDF...",
            "logs": [],
            "result": None,
            "files": [],
            "error": None,
            "output_dir": prepare_result.get("output_dir"),
            "prepare_job_id": prepare_job_id,
        }
        background_tasks.add_task(_run_gc_export_task, job_id, prepare_result, payload)
        return JSONResponse({"ok": True, "job_id": job_id})
    except Exception as e:
        return _err(str(e))


@app.post("/api/tool3/upload")
async def tool3_upload(file: UploadFile = File(...)):
    try:
        from tools.tool1_autofill.engine import parse_bc_bqms
        content = await file.read()
        orders = parse_bc_bqms(content)
        rfq_codes: list[str] = []
        seen = set()
        for o in orders:
            rfq = str(o.get("don_hang") or o.get("rfq_no") or o.get("rfq") or "").strip()
            if rfq and rfq not in seen:
                seen.add(rfq)
                rfq_codes.append(rfq)
        return JSONResponse({"ok": True, "rfq_codes": rfq_codes, "count": len(rfq_codes)})
    except Exception as e:
        return _err(str(e))


@app.post("/api/tool3/classify")
async def tool3_classify(payload: dict):
    try:
        orders = payload.get("orders", [])
        if not orders:
            rfq_codes = payload.get("rfq_codes") or []
            orders = [
                {
                    "rfq": str(rfq),
                    "rfq_no": str(rfq),
                    "don_hang": str(rfq),
                    "type": "TM",
                    "loai_hang": "TM",
                    "spec": "",
                    "maker": "",
                }
                for rfq in rfq_codes
                if str(rfq).strip()
            ]
        if not orders:
            return JSONResponse({"results": [], "count": 0})
        from tools.tool3_pofilter.engine import process_batch
        raw_results = process_batch(orders)
        results = []
        for r in raw_results:
            row = dict(r)
            rfq = row.get("rfq") or row.get("don_hang") or row.get("rfq_no") or row.get("order_id") or ""
            decision = row.get("final_decision") or row.get("decision") or "maybe"
            row["rfq"] = rfq
            row["decision"] = decision
            results.append(row)
        return JSONResponse({"results": results, "count": len(results)})
    except Exception as e:
        return _err(str(e))


@app.post("/api/tool3/override")
async def tool3_override(payload: dict):
    try:
        rfq = payload.get("rfq", "")
        original = payload.get("original", "") or payload.get("current", "")
        new_decision = payload.get("new_decision", "") or payload.get("decision", "")
        reason = payload.get("reason", "")
        if not rfq:
            return _err("rfq required", 400)
        if not new_decision:
            return _err("decision required", 400)
        # Write to audit log
        try:
            from modules.config import get_config
            cfg = get_config()
            log_dir = _ROOT / cfg.get("log_dir", "logs")
        except Exception:
            log_dir = _ROOT / "logs"
        log_dir.mkdir(exist_ok=True)
        entry = {
            "ts": datetime.now().isoformat(),
            "action": "classification_override",
            "order_id": rfq,
            "original": original,
            "new": new_decision,
            "final_decision": new_decision,
            "reason": reason,
        }
        with open(log_dir / "audit.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return JSONResponse({"ok": True, "rfq": rfq, "decision": new_decision})
    except Exception as e:
        return _err(str(e))


@app.get("/api/tool3/rules")
async def tool3_rules():
    return JSONResponse({"rules": [], "note": "Rules not yet configured"})


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
@app.get("/api/analytics/summary")
async def analytics_summary():
    audit = _load_audit_entries(limit=1000)
    class_rows = [r for r in audit if r.get("action") == "classification"]
    override_rows = [r for r in audit if r.get("action") == "classification_override"]
    total = len(class_rows)
    c = Counter((r.get("decision") or r.get("final_decision") or "maybe") for r in class_rows)
    yes, no, maybe = c.get("yes", 0), c.get("no", 0), c.get("maybe", 0)
    avg_conf = 0.0
    if total:
        confs = [float(r.get("confidence", 0) or 0) for r in class_rows]
        avg_conf = round(sum(confs) / total * 100, 1)
    override_ratio = round(len(override_rows) / total * 100, 1) if total else 0.0
    # Win rate from po_history
    win_rate = 0.0
    try:
        db = _get_db_path()
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM po_history")
        po_total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM po_history WHERE LOWER(status)='win'")
        wins = cur.fetchone()[0]
        conn.close()
        if po_total:
            win_rate = round(wins / po_total * 100, 1)
    except Exception:
        pass
    no_to_yes = 0
    yes_to_no = 0
    for r in override_rows:
        old = str(r.get("original", "")).lower()
        new = str(r.get("new") or r.get("final_decision") or "").lower()
        if old == "no" and new == "yes":
            no_to_yes += 1
        elif old == "yes" and new == "no":
            yes_to_no += 1

    return JSONResponse({
        # Frontend v6 expected keys
        "total": total,
        "join_count": yes,
        "skip_count": no,
        "maybe_count": maybe,
        "avg_confidence": avg_conf,
        "win_rate": win_rate,
        "overrides": {
            "total": len(override_rows),
            "no_to_yes": no_to_yes,
            "yes_to_no": yes_to_no,
            "ratio": override_ratio,
        },
        # Backward-compatible keys
        "ai_total": total,
        "yes": yes,
        "no": no,
        "maybe": maybe,
        "avg_conf": avg_conf,
        "override_count": len(override_rows),
        "override_ratio": override_ratio,
    })


@app.get("/api/analytics/makers")
async def analytics_makers():
    try:
        db = _get_db_path()
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(
            "SELECT maker, COUNT(*) n FROM products WHERE maker IS NOT NULL AND maker != '' "
            "GROUP BY maker ORDER BY n DESC LIMIT 8"
        )
        rows = [{"maker": r[0], "count": r[1]} for r in cur.fetchall()]
        conn.close()
        return JSONResponse(rows)
    except Exception as e:
        return _err(str(e))


@app.get("/api/analytics/price-status")
async def analytics_price_status():
    try:
        db = _get_db_path()
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT price_status, COUNT(*) FROM products GROUP BY price_status")
        data = dict(cur.fetchall())
        cur.execute("SELECT type, COUNT(*) FROM products WHERE type IS NOT NULL GROUP BY type")
        types = dict(cur.fetchall())
        conn.close()
        valid = data.get("ok", 0)
        expired = data.get("expired", 0)
        no_price = data.get("none", 0) + data.get(None, 0)
        return JSONResponse({
            # Frontend v6 expected keys
            "valid": valid,
            "expired": expired,
            "no_price": no_price,
            # Backward-compatible keys
            "ok": valid,
            "none": no_price,
            "gc": types.get("gc", 0),
            "tm": types.get("tm", 0),
        })
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Tool 2 — BQMS Analytics & BC BQMS 2026
# ---------------------------------------------------------------------------
def _get_tool2_path(key: str) -> str:
    try:
        from modules.config import get_config
        return get_config().get(key, "")
    except Exception:
        return ""


def _normalize_tool2_path(p: str) -> str:
    s = str(p or "").strip().strip('"').strip("'")
    if not s:
        return ""
    if s.startswith(":\\"):
        s = "C" + s
    return os.path.normpath(s)


def _score_analytics_file(path: str) -> tuple[int, float]:
    n = os.path.basename(path).lower().replace("_", " ").replace("-", " ")
    score = 0
    if "hoi hang" in n:
        score += 45
    if "bqms" in n:
        score += 45
    if "thong ke" in n:
        score += 20
    if "dat hang" in n:
        score -= 25
    if "gia phoi" in n:
        score -= 20
    return (score, os.path.getmtime(path))


def _score_bc_file(path: str) -> tuple[int, float]:
    month = datetime.now().month
    n = os.path.basename(path).lower().replace("_", " ").replace("-", " ")
    score = 0
    if "bc bqms" in n:
        score += 60
    if "thang" in n:
        score += 20
    if f"thang {month}" in n or f"thang{month}" in n:
        score += 80
    if "origin" in n:
        score -= 10
    return (score, os.path.getmtime(path))


def _score_giao_hang_file(path: str) -> tuple[int, int, float]:
    year = datetime.now().year
    n = os.path.basename(path).lower().replace("_", " ").replace("-", " ")
    score = 0
    if "giao hang" in n:
        score += 60
    if "thong ke" in n:
        score += 25
    # Prefer current/newer year files.
    years = [int(y) for y in re.findall(r"(20\d{2})", n)]
    best_year = max(years) if years else 0
    if best_year == year:
        score += 50
    elif best_year == year - 1:
        score += 25
    return (score, best_year, os.path.getmtime(path))


def _resolve_excel_candidates(base_path: str, recursive_depth: int = 1) -> list[str]:
    p = _normalize_tool2_path(base_path)
    if not p:
        return []

    # Exact file
    if os.path.isfile(p):
        return [p]

    # Try extension completion (user may enter path without extension)
    root, ext = os.path.splitext(p)
    if not ext:
        by_ext = [root + e for e in (".xlsx", ".xlsm", ".xls", ".xlsb")]
        hit = [x for x in by_ext if os.path.isfile(x)]
        if hit:
            return [os.path.normpath(hit[0])]

    candidates: list[str] = []

    # Directory scan
    if os.path.isdir(p):
        candidates.extend(glob.glob(os.path.join(p, "*.xls*")))
        if recursive_depth > 0:
            try:
                for name in os.listdir(p):
                    sub = os.path.join(p, name)
                    if os.path.isdir(sub):
                        candidates.extend(glob.glob(os.path.join(sub, "*.xls*")))
            except Exception:
                pass
        return [os.path.normpath(x) for x in candidates if os.path.isfile(x)]

    # Partial path / stem scan from parent directory
    parent = os.path.dirname(p) or "."
    stem = os.path.basename(root if not ext else p).lower()
    if os.path.isdir(parent):
        for x in glob.glob(os.path.join(parent, "*.xls*")):
            bn = os.path.basename(x).lower()
            if not stem or stem in bn:
                candidates.append(x)
    return [os.path.normpath(x) for x in candidates if os.path.isfile(x)]


def _resolve_tool2_input_path(key: str, raw_value: str) -> str:
    """
    Resolve config path into an actual Excel file path.
    Accepts exact file / folder / partial filename.
    """
    raw = _normalize_tool2_path(raw_value)
    if not raw:
        return ""

    # Direct hit first
    if os.path.isfile(raw):
        return raw

    cands = _resolve_excel_candidates(raw, recursive_depth=1)
    if not cands:
        return ""

    if key == "bc_bqms_path":
        cands.sort(key=_score_bc_file, reverse=True)
    elif key == "giao_hang_path":
        cands.sort(key=_score_giao_hang_file, reverse=True)
    else:  # analytics_path / analytics_extra_path
        cands.sort(key=_score_analytics_file, reverse=True)
    return cands[0] if cands else ""


def _df_to_paged(df, page: int = 1, limit: int = 50) -> dict:
    """Serialize DataFrame slice to JSON-safe dict with pagination info."""
    import math
    try:
        import numpy as np
        has_np = True
    except ImportError:
        has_np = False
    try:
        import pandas as pd
        has_pd = True
    except ImportError:
        has_pd = False

    total = len(df)
    start = (page - 1) * limit
    end = start + limit
    rows = df.iloc[start:end]
    records = []
    for _, row in rows.iterrows():
        rec = {}
        for k, v in row.items():
            if v is None:
                rec[k] = None
                continue
            if isinstance(v, (bytes, bytearray, memoryview)):
                # Keep payload JSON-safe; frontend uses has_image for display logic.
                rec[k] = None
                continue
            if has_pd:
                try:
                    if pd.isna(v):
                        rec[k] = None
                        continue
                except Exception:
                    pass
            if hasattr(v, "isoformat"):
                try:
                    rec[k] = v.isoformat()
                    continue
                except Exception:
                    pass
            if has_np and isinstance(v, (float,)) and (v != v):  # NaN
                rec[k] = None
            elif has_np and isinstance(v, np.integer):
                rec[k] = int(v)
            elif has_np and isinstance(v, np.floating):
                rec[k] = None if (v != v) else float(v)
            else:
                rec[k] = v
        records.append(rec)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, math.ceil(total / limit)),
        "records": records,
    }


@app.get("/api/tool2/analytics")
async def tool2_analytics(page: int = 1, limit: int = 50):
    try:
        raw_path = _get_tool2_path("analytics_path")
        raw_extra = _get_tool2_path("analytics_extra_path")
        path = _resolve_tool2_input_path("analytics_path", raw_path)
        extra = _resolve_tool2_input_path("analytics_extra_path", raw_extra) if raw_extra else ""
        if not path:
            msg = "analytics_path not configured" if not raw_path else f"File not found: {raw_path}"
            return JSONResponse({"ok": False, "error": msg, "meta": {}, "records": [], "total": 0, "pages": 0})
        from tools.tool2_pricetracker.engine import load_bqms_analytics
        res = load_bqms_analytics(path, extra_path=extra)
        if not res.get("ok"):
            return JSONResponse({"ok": False, "error": res.get("error", "Load failed"), "meta": {}, "records": [], "total": 0, "pages": 0})
        meta = {k: v for k, v in res["meta"].items() if k not in ("mapped_debug",)}
        meta["resolved_path"] = path
        if extra:
            meta["resolved_extra_path"] = extra
        raw_df = res["df"]
        clean_df = _normalize_tool2_dataframe(raw_df, dataset="analytics")
        meta["raw_rows_after_engine"] = int(len(raw_df)) if raw_df is not None else 0
        meta["blank_rows_filtered"] = int(max(meta["raw_rows_after_engine"] - int(len(clean_df)), 0))
        meta["display_order"] = "newest_to_oldest"
        paged = _df_to_paged(clean_df, page=page, limit=limit)
        return JSONResponse({"ok": True, "meta": meta, **paged})
    except Exception as e:
        return _err(str(e))


@app.get("/api/tool2/bc-bqms")
async def tool2_bc_bqms(page: int = 1, limit: int = 50, include_images: int = 1):
    try:
        raw_path = _get_tool2_path("bc_bqms_path")
        path = _resolve_tool2_input_path("bc_bqms_path", raw_path)
        if not path:
            msg = "bc_bqms_path not configured" if not raw_path else f"File not found: {raw_path}"
            return JSONResponse({"ok": False, "error": msg, "meta": {}, "records": [], "total": 0, "pages": 0})
        from tools.tool2_pricetracker.engine import load_bc_bqms_2026
        want_images = bool(int(include_images or 0))
        res = load_bc_bqms_2026(path, include_colors=False, include_images=want_images)
        if not res.get("ok"):
            return JSONResponse({"ok": False, "error": res.get("error", "Load failed"), "meta": {}, "records": [], "total": 0, "pages": 0})
        meta = {k: v for k, v in res["meta"].items() if k not in ("mapped_debug",)}
        meta["resolved_path"] = path
        meta["include_images"] = want_images
        raw_df = res["df"]
        clean_df = _normalize_tool2_dataframe(raw_df, dataset="bc")
        meta["raw_rows_after_engine"] = int(len(raw_df)) if raw_df is not None else 0
        meta["blank_rows_filtered"] = int(max(meta["raw_rows_after_engine"] - int(len(clean_df)), 0))
        meta["display_order"] = "newest_to_oldest"
        try:
            meta["image_rows"] = int(clean_df["has_image"].fillna(0).astype(int).sum()) if "has_image" in clean_df.columns else 0
        except Exception:
            meta["image_rows"] = 0
        paged = _df_to_paged(clean_df, page=page, limit=limit)
        return JSONResponse({"ok": True, "meta": meta, **paged})
    except Exception as e:
        return _err(str(e))


@app.get("/api/tool2/bc-bqms/image")
async def tool2_bc_bqms_image(excel_row: int, col_letter: str = "I"):
    try:
        raw_path = _get_tool2_path("bc_bqms_path")
        path = _resolve_tool2_input_path("bc_bqms_path", raw_path)
        if not path:
            msg = "bc_bqms_path not configured" if not raw_path else f"File not found: {raw_path}"
            return _err(msg, 404)

        from tools.tool2_pricetracker.engine import (
            capture_bc_row_image_via_com,
            _try_openpyxl_image_fallback,
        )
        cols_try = []
        for c in [col_letter, "I", "P", "H", "J", "K"]:
            c0 = str(c or "").strip().upper()
            if c0 and c0 not in cols_try:
                cols_try.append(c0)

        img_bytes = b""
        detail = ""
        for c in cols_try:
            img_bytes, detail = capture_bc_row_image_via_com(path, excel_row, col_letter=c)
            if img_bytes:
                break
        if not img_bytes:
            try:
                img_bytes = _try_openpyxl_image_fallback(path, int(excel_row))
            except Exception:
                img_bytes = b""
        if not img_bytes:
            return _err(detail or f"No image for row {excel_row}", 404)
        return Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        return _err(str(e))


@app.get("/api/tool2/giao-hang")
async def tool2_giao_hang(page: int = 1, limit: int = 50):
    """Load 'Thong ke giao hang' file using the generic analytics engine."""
    try:
        raw_path = _get_tool2_path("giao_hang_path")
        path = _resolve_tool2_input_path("giao_hang_path", raw_path)
        if not path:
            msg = "giao_hang_path not configured" if not raw_path else f"Thong ke giao hang: File not found: {raw_path}"
            return JSONResponse({"ok": False, "error": msg, "meta": {}, "records": [], "total": 0, "pages": 0})
        from tools.tool2_pricetracker.engine import load_bqms_analytics
        res = load_bqms_analytics(path)
        if not res.get("ok"):
            return JSONResponse({"ok": False, "error": res.get("error", "Load failed"), "meta": {}, "records": [], "total": 0, "pages": 0})
        meta = {k: v for k, v in res["meta"].items() if k not in ("mapped_debug",)}
        meta["resolved_path"] = path
        raw_df = res["df"]
        clean_df = _normalize_tool2_dataframe(raw_df, dataset="giao_hang")
        meta["raw_rows_after_engine"] = int(len(raw_df)) if raw_df is not None else 0
        meta["blank_rows_filtered"] = int(max(meta["raw_rows_after_engine"] - int(len(clean_df)), 0))
        meta["display_order"] = "newest_to_oldest"
        paged = _df_to_paged(clean_df, page=page, limit=limit)
        return JSONResponse({"ok": True, "meta": meta, **paged})
    except Exception as e:
        return _err(str(e))


@app.post("/api/tool2/set-paths")
async def tool2_set_paths(payload: dict):
    try:
        from modules.config import get_config, save_config
        cfg = get_config()
        for key in ("analytics_path", "analytics_extra_path", "bc_bqms_path", "giao_hang_path"):
            if key in payload:
                cfg[key] = _normalize_tool2_path(payload[key])
        save_config(cfg)
        return JSONResponse({"ok": True})
    except Exception as e:
        return _err(str(e))


@app.post("/api/tool2/watch-setup")
async def tool2_watch_setup():
    """Add folders containing the 3 watched files to watchdog."""
    try:
        from modules.folder_browser import add_watch_folder
        added: list = []
        errors: list = []
        file_labels = {
            "analytics_path": "Thong Ke Hoi Hang",
            "bc_bqms_path": "BC BQMS 2026",
            "giao_hang_path": "Thong Ke Giao Hang",
        }
        for cfg_key, label in file_labels.items():
            raw_fp = _get_tool2_path(cfg_key)
            fp = _resolve_tool2_input_path(cfg_key, raw_fp)
            if not fp or not os.path.isfile(fp):
                if raw_fp:
                    errors.append(f"{label}: file not found from '{raw_fp}'")
                continue
            folder = os.path.dirname(fp)
            try:
                created = add_watch_folder(folder, label)
                if created:
                    added.append({"folder": folder, "label": label, "file": fp})
                else:
                    errors.append(f"{label}: already watched")
            except Exception as ex:
                errors.append(f"{label}: {ex}")
        return JSONResponse({"ok": True, "added": added, "errors": errors})
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Setup / First-run Wizard
# ---------------------------------------------------------------------------

@app.get("/api/setup/status")
async def setup_status():
    """Return setup completeness for the first-run wizard."""
    try:
        from modules.config import get_setup_status
        return JSONResponse(get_setup_status())
    except Exception as e:
        return _err(str(e))


@app.post("/api/setup/wizard")
async def setup_wizard(payload: dict):
    """Accept wizard form and persist to config.json.
    Sensitive credentials (bqms_password) stored in Windows Credential Manager via keyring.
    """
    try:
        from modules.config import get_config, save_config
        cfg = get_config()
        allowed = [
            "rfq_folder", "company_name", "gemini_keys",
            "bc_bqms_path", "giao_hang_path", "analytics_path",
            "bqms_username", "update_url", "auto_check_updates",
        ]
        for k in allowed:
            if k in payload:
                cfg[k] = _sanitize_str(str(payload[k])) if isinstance(payload[k], str) else payload[k]

        # Store password in Windows Credential Manager (not config.json)
        if "bqms_password" in payload and payload["bqms_password"]:
            _store_credential("bsmq_bqms", cfg.get("bqms_username", "bsmq"), payload["bqms_password"])

        # Validate rfq_folder path exists if provided
        rfq = cfg.get("rfq_folder", "")
        if rfq and not Path(rfq).exists():
            return JSONResponse({"ok": False, "warning": f"Thư mục RFQ không tồn tại: {rfq}"})

        ok = save_config(cfg)
        return JSONResponse({"ok": ok})
    except Exception as e:
        return _err(str(e))


def _store_credential(service: str, username: str, password: str) -> bool:
    """Store credential in Windows Credential Manager. Fallback to config.json."""
    try:
        import keyring
        keyring.set_password(service, username, password)
        return True
    except Exception:
        # Fallback: store in config.json (less secure but functional)
        try:
            from modules.config import get_config, save_config
            cfg = get_config()
            cfg["bqms_password"] = password
            save_config(cfg)
        except Exception:
            pass
        return False


def _get_credential(service: str, username: str) -> str:
    """Retrieve credential from Windows Credential Manager, fallback config.json."""
    try:
        import keyring
        pw = keyring.get_password(service, username)
        if pw:
            return pw
    except Exception:
        pass
    try:
        from modules.config import get_config
        return get_config().get("bqms_password", "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Auto-update
# ---------------------------------------------------------------------------

@app.get("/api/update/check")
async def update_check():
    """Check for a newer version at update_url. Returns version info."""
    try:
        from modules.config import get_config, get_current_version
        import requests as _requests
        cfg = get_config()
        update_url = cfg.get("update_url", "").strip()
        current = get_current_version()

        if not update_url:
            return JSONResponse({
                "current": current, "latest": current,
                "has_update": False, "changelog": "",
                "error": "update_url chua duoc cau hinh"
            })

        # Expect remote manifest at {update_url}/manifest.json
        manifest_url = update_url.rstrip("/") + "/manifest.json"
        try:
            r = _requests.get(manifest_url, timeout=10)
            r.raise_for_status()
            manifest = r.json()
        except Exception as e:
            return JSONResponse({
                "current": current, "latest": current,
                "has_update": False, "changelog": "",
                "error": f"Khong ket noi duoc update server: {e}"
            })

        latest = manifest.get("version", current)
        changelog = manifest.get("changelog", "")
        has_update = _version_gt(latest, current)
        return JSONResponse({
            "current": current,
            "latest": latest,
            "has_update": has_update,
            "changelog": changelog,
            "patch_url": manifest.get("patch_url", ""),
        })
    except Exception as e:
        return _err(str(e))


@app.post("/api/update/apply")
async def update_apply(background_tasks: BackgroundTasks):
    """Download and apply the update patch in the background."""
    try:
        from modules.config import get_config, get_current_version
        import requests as _requests
        cfg = get_config()
        update_url = cfg.get("update_url", "").strip()
        current = get_current_version()

        if not update_url:
            return _err("update_url chua duoc cau hinh", 400)

        manifest_url = update_url.rstrip("/") + "/manifest.json"
        r = _requests.get(manifest_url, timeout=10)
        r.raise_for_status()
        manifest = r.json()

        patch_url = manifest.get("patch_url", "")
        if not patch_url:
            return _err("manifest.json thieu patch_url", 400)

        job_id = str(uuid.uuid4())[:8]
        jobs[job_id] = {"status": "running", "msg": "Dang tai ban cap nhat..."}
        background_tasks.add_task(_do_update, job_id, patch_url, manifest, current)
        return JSONResponse({"ok": True, "job_id": job_id})
    except Exception as e:
        return _err(str(e))


@app.get("/api/update/status/{job_id}")
async def update_status(job_id: str):
    return JSONResponse(jobs.get(job_id, {"status": "not_found"}))


def _version_gt(a: str, b: str) -> bool:
    """True if version a > version b (semver comparison)."""
    try:
        def parse(v):
            return tuple(int(x) for x in str(v).strip().split("."))
        return parse(a) > parse(b)
    except Exception:
        return a != b


def _do_update(job_id: str, patch_url: str, manifest: dict, old_version: str):
    """Background task: download patch ZIP, backup changed files, apply."""
    import zipfile, shutil, tempfile, requests as _requests
    from modules.config import get_config, save_config, _VERSION_PATH, _ROOT

    try:
        jobs[job_id]["msg"] = "Dang tai file cap nhat..."
        r = _requests.get(patch_url, timeout=60, stream=True)
        r.raise_for_status()

        tmp_zip = Path(tempfile.gettempdir()) / f"bsmq_patch_{job_id}.zip"
        with open(tmp_zip, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        jobs[job_id]["msg"] = "Dang ap dung cap nhat..."
        allowed_exts = {".py", ".html", ".js", ".css", ".txt"}
        protected = {"config.json", "version.txt"}
        skip_dirs = {"python", "logs", "outputs", "cache", "backups", "_setup"}

        backup_dir = _ROOT / "backups" / f"pre_update_{old_version}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(tmp_zip, "r") as zf:
            file_list = manifest.get("files", [
                n for n in zf.namelist()
                if not n.endswith("/") and Path(n).suffix in allowed_exts
            ])
            for fname in file_list:
                if fname in protected:
                    continue
                parts = Path(fname).parts
                if parts and parts[0] in skip_dirs:
                    continue
                if Path(fname).suffix not in allowed_exts:
                    continue

                dest = _ROOT / fname
                if dest.exists():
                    shutil.copy2(dest, backup_dir / Path(fname).name)

                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(fname) as src, open(dest, "wb") as dst:
                    dst.write(src.read())

        # Update version.txt
        new_version = manifest.get("version", old_version)
        _VERSION_PATH.write_text(new_version, encoding="utf-8")
        cfg = get_config()
        cfg["current_version"] = new_version
        save_config(cfg)

        tmp_zip.unlink(missing_ok=True)
        jobs[job_id] = {
            "status": "done",
            "msg": f"Cap nhat len v{new_version} thanh cong!",
            "version": new_version,
        }
    except Exception as e:
        jobs[job_id] = {"status": "error", "msg": str(e)}


# ---------------------------------------------------------------------------
# Market Search (Tool 5)
# ---------------------------------------------------------------------------

@app.post("/api/market/search")
async def market_search_start(req: Request, bg: BackgroundTasks):
    """Start a background market search job. Returns {job_id}."""
    body = await req.json()
    spec = _sanitize_str(body.get("spec", ""), 500)
    if not spec:
        return _err("spec is required", 400)
    platforms = body.get("platforms", ["alibaba", "1688", "taiwantrade", "ruten"])
    if not isinstance(platforms, list) or not platforms:
        platforms = ["alibaba", "1688", "taiwantrade", "ruten"]

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "running", "messages": [], "result": None, "error": None}
    bg.add_task(_run_market_search, job_id, body)
    return {"job_id": job_id}


def _run_market_search(job_id: str, body: dict):
    try:
        from tools.tool5_market_search.engine import search, init_market_tables
        db_path = _get_db_path()
        init_market_tables(db_path)

        def _cb(msg: str):
            jobs[job_id]["messages"].append(msg)

        platforms = body.get("platforms", ["alibaba", "1688", "taiwantrade", "ruten"])
        result = search(
            spec=_sanitize_str(body.get("spec", ""), 500),
            maker=_sanitize_str(body.get("maker", ""), 200),
            bqms_code=_sanitize_str(body.get("bqms_code", ""), 50),
            budget_usd=float(body.get("budget_usd") or 0),
            platforms=[str(p) for p in platforms if p],
            max_per_platform=max(10, min(40, int(body.get("max_per_platform") or 20))),
            use_cache=bool(body.get("use_cache", True)),
            db_path=db_path,
            progress_cb=_cb,
        )
        jobs[job_id]["status"] = "done"
        jobs[job_id]["result"] = {
            "query_params": result.query_params,
            "platform_stats": result.platform_stats,
            "verified_results": result.verified_results[:30],
            "synthesis": result.synthesis,
            "evaluation": result.evaluation,
            "total_duration_sec": result.total_duration_sec,
            "cache_used": result.cache_used,
        }
    except Exception as exc:
        import traceback
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(exc)
        jobs[job_id]["messages"].append(f"Lỗi: {exc}")


@app.get("/api/market/job/{job_id}")
async def market_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return _err("Job not found", 404)
    return job


@app.get("/api/market/saved")
async def market_get_saved(bqms_code: str = ""):
    from tools.tool5_market_search.engine import get_confirmed_prices, init_market_tables
    db_path = _get_db_path()
    init_market_tables(db_path)
    rows = get_confirmed_prices(_sanitize_str(bqms_code, 50), db_path)
    return {"items": rows}


@app.post("/api/market/save")
async def market_save_price(req: Request):
    body = await req.json()
    from tools.tool5_market_search.engine import save_confirmed_price, init_market_tables
    db_path = _get_db_path()
    init_market_tables(db_path)
    save_confirmed_price({
        "bqms_code":       _sanitize_str(body.get("bqms_code", ""), 50),
        "product_name":    _sanitize_str(body.get("product_name", ""), 200),
        "spec":            _sanitize_str(body.get("spec", ""), 500),
        "maker":           _sanitize_str(body.get("maker", ""), 100),
        "confirmed_price": float(body.get("confirmed_price") or 0),
        "currency":        _sanitize_str(body.get("currency", "USD"), 5),
        "supplier_name":   _sanitize_str(body.get("supplier_name", ""), 200),
        "supplier_url":    _sanitize_str(body.get("supplier_url", ""), 500),
        "platform":        _sanitize_str(body.get("platform", ""), 20),
        "moq":             int(body.get("moq") or 0),
        "notes":           _sanitize_str(body.get("notes", ""), 500),
    }, db_path)
    return {"ok": True}


@app.delete("/api/market/saved/{row_id}")
async def market_delete_saved(row_id: int):
    from tools.tool5_market_search.engine import delete_confirmed_price, init_market_tables
    db_path = _get_db_path()
    init_market_tables(db_path)
    delete_confirmed_price(row_id, db_path)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_api:app", host="0.0.0.0", port=8000, reload=True)
