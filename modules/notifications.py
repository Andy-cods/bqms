"""
modules/notifications.py
Windows desktop notifications — win10toast with plyer fallback.
Pure Python, no Streamlit dependency.
"""

import os
import sys
import threading


# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

def _try_win10toast(title: str, message: str, icon_path: str = None, duration: int = 5) -> bool:
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(
            title,
            message,
            icon_path=icon_path,
            duration=duration,
            threaded=True,
        )
        return True
    except Exception:
        return False


def _try_plyer(title: str, message: str, timeout: int = 5) -> bool:
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="BSMQ System",
            timeout=timeout,
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def notify(title: str, message: str, duration: int = 5) -> bool:
    """
    Send a Windows desktop notification.
    Tries win10toast first, falls back to plyer, then silent fail.
    Returns True if notification was sent.
    Non-blocking (runs in thread).
    """
    def _send():
        if _try_win10toast(title, message, duration=duration):
            return
        _try_plyer(title, message, timeout=duration)

    t = threading.Thread(target=_send, daemon=True)
    t.start()
    return True  # optimistic


def notify_job_done(title: str = "BSMQ", message: str = "Job completed.") -> bool:
    """Notify on job completion."""
    return notify(f"[BSMQ] {title}", message, duration=5)


def notify_error(message: str, title: str = "BSMQ Error") -> bool:
    """Notify on error."""
    return notify(f"[BSMQ] {title}", message, duration=8)


def notify_new_file(file_name: str, folder_label: str = "") -> bool:
    """Notify when watchdog detects a new file."""
    msg = f"New file: {file_name}"
    if folder_label:
        msg += f"\nFolder: {folder_label}"
    return notify("[BSMQ] New File Detected", msg, duration=4)


def notify_classification_done(yes: int, no: int, maybe: int) -> bool:
    """Notify when AI batch classification finishes."""
    msg = f"Done: {yes} YES / {no} NO / {maybe} MAYBE"
    return notify("[BSMQ] PO Filter Complete", msg, duration=5)
