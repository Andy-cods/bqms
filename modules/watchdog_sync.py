"""
modules/watchdog_sync.py
Merged: db_monitor.py + watcher.py
Unified folder monitoring: SQLite event storage + watchdog observer.

Drop-in replacement for both old modules:
    from modules.watchdog_sync import (
        add_folder, get_folders, insert_event, get_events,
        mark_processed, count_unprocessed, get_stats,
        start_or_refresh, stop, is_running, get_status, drain_queue
    )
"""

import os
import json
import sqlite3
import time
import threading
import queue
from datetime import datetime, timedelta

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# ---------------------------------------------------------------------------
# DB path — resolved from config.json
# ---------------------------------------------------------------------------

def _get_monitor_db_path() -> str:
    cfg = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    try:
        with open(cfg, encoding='utf-8') as f:
            path = json.load(f).get('monitor_db', './bsmq_monitor.db')
        base = os.path.dirname(os.path.abspath(cfg))
        return os.path.normpath(os.path.join(base, path)) if not os.path.isabs(path) else path
    except Exception:
        return os.path.join(os.path.dirname(__file__), '..', 'bsmq_monitor.db')


def _get_conn() -> sqlite3.Connection:
    db = _get_monitor_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(db)), exist_ok=True)
    conn = sqlite3.connect(db, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Schema init (idempotent)
# ---------------------------------------------------------------------------

def _init_monitor_db() -> None:
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS watched_folders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            path        TEXT NOT NULL UNIQUE,
            label       TEXT,
            recursive   INTEGER DEFAULT 1,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            last_seen   TEXT
        );

        CREATE TABLE IF NOT EXISTS file_events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_id    INTEGER REFERENCES watched_folders(id),
            event_type   TEXT NOT NULL,
            file_path    TEXT NOT NULL,
            file_name    TEXT NOT NULL,
            file_ext     TEXT,
            file_size    INTEGER,
            dest_path    TEXT,
            is_processed INTEGER DEFAULT 0,
            ts           TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_events_folder ON file_events(folder_id);
        CREATE INDEX IF NOT EXISTS idx_events_ts     ON file_events(ts);
        CREATE INDEX IF NOT EXISTS idx_events_proc   ON file_events(is_processed);

        CREATE TABLE IF NOT EXISTS sync_state (
            folder_id    INTEGER NOT NULL,
            file_path    TEXT NOT NULL,
            mtime        REAL,
            file_size    INTEGER,
            PRIMARY KEY (folder_id, file_path)
        );
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Watched Folders API
# ---------------------------------------------------------------------------

def add_folder(path: str, label: str = "", recursive: bool = True):
    """Add folder to watch. Returns new id or None if already exists."""
    norm_path = os.path.normpath((path or "").rstrip("/\\"))
    if not norm_path:
        return None
    label = label or os.path.basename(norm_path)
    conn = _get_conn()
    try:
        existed = conn.execute(
            "SELECT id FROM watched_folders WHERE LOWER(path)=LOWER(?) LIMIT 1",
            (norm_path,),
        ).fetchone()
        if existed:
            return None
        cur = conn.execute(
            "INSERT INTO watched_folders (path, label, recursive) VALUES (?, ?, ?)",
            (norm_path, label, 1 if recursive else 0)
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_folders(active_only: bool = False) -> list:
    conn = _get_conn()
    if active_only:
        rows = conn.execute("SELECT * FROM watched_folders WHERE is_active=1 ORDER BY id").fetchall()
    else:
        rows = conn.execute("SELECT * FROM watched_folders ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_folder_active(folder_id: int, active: bool) -> None:
    conn = _get_conn()
    conn.execute("UPDATE watched_folders SET is_active=? WHERE id=?", (1 if active else 0, folder_id))
    conn.commit()
    conn.close()


def delete_folder(folder_id: int) -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM file_events WHERE folder_id=?", (folder_id,))
    conn.execute("DELETE FROM watched_folders WHERE id=?", (folder_id,))
    conn.commit()
    conn.close()


def update_folder_seen(folder_id: int) -> None:
    conn = _get_conn()
    conn.execute(
        "UPDATE watched_folders SET last_seen=? WHERE id=?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), folder_id)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# File Events API
# ---------------------------------------------------------------------------

def insert_event(folder_id: int, event_type: str, file_path: str,
                 file_size=None, dest_path=None) -> None:
    file_name = os.path.basename(file_path)
    file_ext  = os.path.splitext(file_name)[1].lower()
    conn = _get_conn()
    conn.execute(
        """INSERT INTO file_events
           (folder_id, event_type, file_path, file_name, file_ext, file_size, dest_path)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (folder_id, event_type, file_path, file_name, file_ext, file_size, dest_path)
    )
    conn.commit()
    conn.close()


def get_events(folder_id=None, limit: int = 200,
               unprocessed_only: bool = False, ext_filter=None) -> list:
    conn = _get_conn()
    clauses, params = [], []
    if folder_id is not None:
        clauses.append("folder_id=?")
        params.append(folder_id)
    if unprocessed_only:
        clauses.append("is_processed=0")
    if ext_filter:
        exts = [e.strip().lower() for e in ext_filter.split(",") if e.strip()]
        placeholders = ",".join("?" * len(exts))
        clauses.append(f"file_ext IN ({placeholders})")
        params.extend(exts)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT e.*, f.label AS folder_label, f.path AS folder_path "
        f"FROM file_events e LEFT JOIN watched_folders f ON e.folder_id=f.id "
        f"{where} ORDER BY e.id DESC LIMIT ?",
        params + [limit]
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_processed(event_id: int) -> None:
    conn = _get_conn()
    conn.execute("UPDATE file_events SET is_processed=1 WHERE id=?", (event_id,))
    conn.commit()
    conn.close()


def mark_all_processed() -> None:
    conn = _get_conn()
    conn.execute("UPDATE file_events SET is_processed=1 WHERE is_processed=0")
    conn.commit()
    conn.close()


def count_unprocessed() -> int:
    try:
        conn = _get_conn()
        n = conn.execute("SELECT COUNT(*) FROM file_events WHERE is_processed=0").fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


def cleanup_old_events(days: int = 30) -> None:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()
    conn.execute("DELETE FROM file_events WHERE ts < ?", (cutoff,))
    conn.commit()
    conn.close()


def get_stats() -> dict:
    try:
        conn = _get_conn()
        today    = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        today_cnt = conn.execute("SELECT COUNT(*) FROM file_events WHERE ts >= ?", (today,)).fetchone()[0]
        week_cnt  = conn.execute("SELECT COUNT(*) FROM file_events WHERE ts >= ?", (week_ago,)).fetchone()[0]
        total_cnt = conn.execute("SELECT COUNT(*) FROM file_events").fetchone()[0]
        unread    = conn.execute("SELECT COUNT(*) FROM file_events WHERE is_processed=0").fetchone()[0]
        conn.close()
        return {"today": today_cnt, "week": week_cnt, "total": total_cnt, "unread": unread}
    except Exception:
        return {"today": 0, "week": 0, "total": 0, "unread": 0}


def manual_sync(folder_id: int = None, max_files: int = 8000) -> dict:
    """
    Manual synchronization by snapshot diff (no continuous watcher required).
    Returns counters for created/modified/deleted events.
    """
    folders = get_folders(active_only=True)
    if folder_id is not None:
        folders = [f for f in folders if f.get("id") == folder_id]

    summary = {
        "folders": 0,
        "scanned_files": 0,
        "created": 0,
        "modified": 0,
        "deleted": 0,
        "errors": 0,
    }
    if not folders:
        return summary

    conn = _get_conn()
    try:
        for f in folders:
            f_id = int(f["id"])
            root = f.get("path", "")
            recursive = bool(f.get("recursive", 1))
            if not os.path.isdir(root):
                summary["errors"] += 1
                continue

            summary["folders"] += 1
            prev_rows = conn.execute(
                "SELECT file_path, mtime, file_size FROM sync_state WHERE folder_id=?",
                (f_id,),
            ).fetchall()
            prev = {r["file_path"]: (r["mtime"], r["file_size"]) for r in prev_rows}
            curr = {}

            walker = os.walk(root) if recursive else [(root, [], os.listdir(root))]
            stop_scan = False
            for base, _, files in walker:
                for name in files:
                    path = os.path.join(base, name)
                    if _should_ignore(path):
                        continue
                    try:
                        st = os.stat(path)
                    except OSError:
                        continue
                    curr[path] = (float(st.st_mtime), int(st.st_size))
                    summary["scanned_files"] += 1
                    if summary["scanned_files"] >= max_files:
                        stop_scan = True
                        break
                if stop_scan:
                    break

            for p, (mt, sz) in curr.items():
                old = prev.get(p)
                if old is None:
                    insert_event(f_id, "created", p, file_size=sz)
                    summary["created"] += 1
                elif abs((old[0] or 0) - mt) > 0.0001 or int(old[1] or 0) != int(sz):
                    insert_event(f_id, "modified", p, file_size=sz)
                    summary["modified"] += 1

            for p in prev.keys():
                if p not in curr:
                    insert_event(f_id, "deleted", p)
                    summary["deleted"] += 1

            conn.execute("DELETE FROM sync_state WHERE folder_id=?", (f_id,))
            if curr:
                conn.executemany(
                    "INSERT INTO sync_state(folder_id, file_path, mtime, file_size) VALUES (?, ?, ?, ?)",
                    [(f_id, p, mt, sz) for p, (mt, sz) in curr.items()],
                )
            conn.commit()
            update_folder_seen(f_id)
    finally:
        conn.close()

    return summary


# ---------------------------------------------------------------------------
# Watchdog Observer
# ---------------------------------------------------------------------------

_observer = None
_observer_lock = threading.Lock()
_event_queue: queue.Queue = queue.Queue()

_IGNORED_PREFIXES   = ("~$", ".~", "~")
_IGNORED_EXTENSIONS = {".tmp", ".crdownload", ".partial", ".lnk", ".ini"}
_IGNORED_NAMES      = {"desktop.ini", "thumbs.db", ".ds_store"}
_debounce: dict     = {}
_DEBOUNCE_SECS      = 2.0


def _should_ignore(path: str) -> bool:
    name = os.path.basename(path)
    ext  = os.path.splitext(name)[1].lower()
    nl   = name.lower()
    return (
        any(nl.startswith(p) for p in _IGNORED_PREFIXES)
        or ext in _IGNORED_EXTENSIONS
        or nl in _IGNORED_NAMES
        or nl.startswith(".")
    )


def _debounced(path: str, event_type: str) -> bool:
    """Suppress duplicate events within DEBOUNCE_SECS window."""
    key = (path, event_type)
    now = time.time()
    if key in _debounce and now - _debounce[key] < _DEBOUNCE_SECS:
        return True
    _debounce[key] = now
    if len(_debounce) > 500:
        cutoff = now - 60
        for k in [k for k, v in list(_debounce.items()) if v < cutoff]:
            _debounce.pop(k, None)
    return False


class _BSMQHandler(FileSystemEventHandler):
    def __init__(self, folder_id: int):
        self.folder_id = folder_id

    def _record(self, event_type: str, path: str, dest_path=None) -> None:
        if _should_ignore(path):
            return
        if _debounced(path, event_type):
            return
        size = None
        if event_type != "deleted" and os.path.isfile(path):
            try:
                size = os.path.getsize(path)
            except OSError:
                pass
        insert_event(
            folder_id=self.folder_id,
            event_type=event_type,
            file_path=path,
            file_size=size,
            dest_path=dest_path,
        )
        update_folder_seen(self.folder_id)
        _event_queue.put({
            "folder_id":  self.folder_id,
            "event_type": event_type,
            "file_path":  path,
            "ts":         datetime.now().strftime("%H:%M:%S"),
        })

    def on_created(self, event):
        if not event.is_directory:
            self._record("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._record("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._record("deleted", event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._record("moved", event.src_path, dest_path=event.dest_path)


# ---------------------------------------------------------------------------
# Public watcher API
# ---------------------------------------------------------------------------

def start_or_refresh() -> None:
    """Start/restart watchdog observer with active folders from DB."""
    global _observer
    with _observer_lock:
        if _observer is not None:
            try:
                _observer.stop()
                _observer.join(timeout=3)
            except Exception:
                pass
            _observer = None

        try:
            folders = get_folders(active_only=True)
        except Exception:
            return

        if not folders:
            return

        obs = Observer()
        for f in folders:
            path = f["path"]
            if not os.path.isdir(path):
                continue
            handler   = _BSMQHandler(folder_id=f["id"])
            recursive = bool(f.get("recursive", True))
            obs.schedule(handler, path, recursive=recursive)

        obs.start()
        _observer = obs


def stop() -> None:
    global _observer
    with _observer_lock:
        if _observer is not None:
            try:
                _observer.stop()
                _observer.join(timeout=3)
            except Exception:
                pass
            _observer = None


def is_running() -> bool:
    return _observer is not None and _observer.is_alive()


def get_status() -> dict:
    try:
        folders = get_folders(active_only=True)
        missing = [f["path"] for f in folders if not os.path.isdir(f["path"])]
        return {"running": is_running(), "watching": len(folders), "missing": missing}
    except Exception:
        return {"running": False, "watching": 0, "missing": []}


def drain_queue(max_items: int = 50) -> list:
    """Drain recent events from in-memory queue (non-blocking)."""
    items = []
    try:
        for _ in range(max_items):
            items.append(_event_queue.get_nowait())
    except queue.Empty:
        pass
    return items


# ---------------------------------------------------------------------------
# Init on import
# ---------------------------------------------------------------------------

try:
    _init_monitor_db()
except Exception:
    pass  # Graceful — watchdog is non-critical
