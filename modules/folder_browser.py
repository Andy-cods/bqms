"""
modules/folder_browser.py
OneDrive folder scanner + watched-folder management.
Read-only: NEVER writes to OneDrive paths.
"""

import os
import time
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# OneDrive root detection
# ---------------------------------------------------------------------------

def get_onedrive_root() -> Optional[str]:
    """
    Detect OneDrive root path from Windows environment variables.
    Priority: Commercial > Consumer > Generic.
    Returns None if not found.
    """
    candidates = [
        os.environ.get("OneDriveCommercial"),
        os.environ.get("OneDriveConsumer"),
        os.environ.get("OneDrive"),
    ]
    for p in candidates:
        if p and os.path.isdir(p):
            return p
    return None


def get_songchau_onedrive() -> Optional[str]:
    """Detect OneDrive 'SONG CHAU CO., LTD' folder on any Windows machine.

    Mọi máy trong team đều đăng nhập cùng OneDrive account nên folder name
    giống nhau: 'OneDrive - SONG CHAU CO., LTD'. Chỉ khác {username} Windows.
    """
    home = os.path.expanduser("~")
    # Primary: look for exact folder name
    target = os.path.join(home, "OneDrive - SONG CHAU CO., LTD")
    if os.path.isdir(target):
        return target
    # Fallback: scan home dir for any OneDrive folder with SONG CHAU
    try:
        for name in os.listdir(home):
            if "SONG CHAU" in name.upper() and os.path.isdir(os.path.join(home, name)):
                return os.path.join(home, name)
    except OSError:
        pass
    return None


def get_bqms_root() -> Optional[str]:
    """Get BQMS folder path: OneDrive/Puplic/BQMS."""
    od = get_songchau_onedrive()
    if not od:
        return None
    for sub in ["Puplic/BQMS", "Public/BQMS"]:
        p = os.path.join(od, sub)
        if os.path.isdir(p):
            return p
    return None


# ---------------------------------------------------------------------------
# Folder scanner — depth-first, early-stop
# ---------------------------------------------------------------------------

def scan_folders(
    root: str,
    max_depth: int = 5,
    max_count: int = 2000,
    skip_hidden: bool = True,
    skip_prefixes: tuple = (".", "_", "$", "~"),
) -> list[dict]:
    """
    Scan all subdirectories under root up to max_depth levels.
    Uses BFS so all siblings at the same level are discovered before going deeper.
    Returns list of {path, name, depth, parent, rel_path, file_count, has_xlsx, has_children}.
    Stops after max_count folders.
    """
    from collections import deque

    results = []
    root = str(root).rstrip("/\\")
    seen = set()

    # BFS queue: (current_path, depth)
    queue = deque()
    queue.append((root, 0))

    while queue and len(results) < max_count:
        current_path, depth = queue.popleft()
        if depth >= max_depth:
            continue
        try:
            entries = sorted(os.scandir(current_path), key=lambda e: e.name.lower())
        except PermissionError:
            continue

        for entry in entries:
            if len(results) >= max_count:
                break
            if not entry.is_dir(follow_symlinks=False):
                continue
            name = entry.name
            if skip_hidden and any(name.startswith(p) for p in skip_prefixes):
                continue
            ep = entry.path
            if ep in seen:
                continue
            seen.add(ep)

            # Count files + detect xlsx + check for sub-dirs
            file_count = 0
            has_xlsx = False
            has_sub = False
            try:
                for f in os.scandir(ep):
                    if f.is_file():
                        file_count += 1
                        if f.name.lower().endswith((".xlsx", ".xls")):
                            has_xlsx = True
                    elif f.is_dir(follow_symlinks=False):
                        n = f.name
                        if not (skip_hidden and any(n.startswith(p) for p in skip_prefixes)):
                            has_sub = True
            except PermissionError:
                pass

            child_depth = depth + 1
            rel = os.path.relpath(ep, root)
            results.append({
                "path":         ep,
                "name":         name,
                "depth":        child_depth,
                "parent":       current_path,
                "rel_path":     rel,
                "file_count":   file_count,
                "has_xlsx":     has_xlsx,
                "has_children": has_sub and child_depth < max_depth,
            })

            if child_depth < max_depth:
                queue.append((ep, child_depth))

    return results


def get_visible_folders(all_folders: list[dict], root: str, expanded: set) -> list[dict]:
    """
    Return only folders that should be visible in the tree
    (depth-1 always shown; deeper only if all ancestors are expanded).
    """
    # Group by parent path
    by_parent: dict[str, list] = {}
    for f in all_folders:
        by_parent.setdefault(f["parent"], []).append(f)

    visible = []

    def _traverse(parent_path: str):
        for f in by_parent.get(parent_path, []):
            visible.append(f)
            if f["path"] in expanded:
                _traverse(f["path"])

    _traverse(root.rstrip("/\\"))
    return visible


# ---------------------------------------------------------------------------
# Recently modified Excel files in a folder (shallow scan)
# ---------------------------------------------------------------------------

def find_recent_excel(folder: str, days: int = 7) -> list[dict]:
    """
    Find .xlsx/.xls files modified within `days` days inside `folder` (non-recursive).
    Returns list of {name, path, size_kb, modified_ts, modified_str}.
    """
    results = []
    cutoff = time.time() - days * 86400
    try:
        for entry in sorted(os.scandir(folder), key=lambda e: e.stat().st_mtime, reverse=True):
            if not entry.is_file():
                continue
            if not entry.name.lower().endswith((".xlsx", ".xls")):
                continue
            stat = entry.stat()
            if stat.st_mtime < cutoff:
                continue
            results.append({
                "name":         entry.name,
                "path":         entry.path,
                "size_kb":      round(stat.st_size / 1024, 1),
                "modified_ts":  stat.st_mtime,
                "modified_str": _fmt_mtime(stat.st_mtime),
            })
    except (PermissionError, FileNotFoundError):
        pass
    return results


def _fmt_mtime(ts: float) -> str:
    import datetime
    dt = datetime.datetime.fromtimestamp(ts)
    now = datetime.datetime.now()
    delta = now - dt
    if delta.days == 0:
        return dt.strftime("Hôm nay %H:%M")
    elif delta.days == 1:
        return dt.strftime("Hôm qua %H:%M")
    elif delta.days < 7:
        return f"{delta.days} ngày trước"
    return dt.strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
# Watched folders helpers (wraps watchdog_sync)
# ---------------------------------------------------------------------------

def get_watched_folders() -> list[dict]:
    """Return list of currently watched folders from monitor DB."""
    try:
        from modules.watchdog_sync import get_folders
        return get_folders() or []
    except Exception:
        return []


def add_watch_folder(path: str, label: str = "") -> bool:
    """Add a folder to watchdog monitoring. Returns True on success."""
    try:
        from modules.watchdog_sync import add_folder
        norm_path = os.path.normpath((path or "").rstrip("/\\"))
        if not norm_path:
            return False
        row_id = add_folder(norm_path, label or os.path.basename(norm_path))
        return bool(row_id)
    except Exception:
        return False


def remove_watch_folder(folder_id: int) -> bool:
    """Deactivate a watched folder. Returns True on success."""
    try:
        from modules.watchdog_sync import set_folder_active
        set_folder_active(folder_id, False)
        return True
    except Exception:
        return False


def get_recent_events(limit: int = 50) -> list[dict]:
    """Fetch recent file-change events from monitor DB."""
    try:
        from modules.watchdog_sync import get_events
        return get_events(limit=limit) or []
    except Exception:
        return []


def get_watchdog_status() -> dict:
    """Return watchdog running status."""
    try:
        from modules.watchdog_sync import is_running, get_status
        return get_status()
    except Exception:
        return {"running": False, "folders": 0, "events": 0}
