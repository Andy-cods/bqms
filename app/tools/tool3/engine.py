"""
tools/tool3_pofilter/engine.py
PO Filter engine — pure logic, no Streamlit.
Wraps ai_classifier with DB lookup + rules loading.
"""

import os
import sys
import json
from datetime import datetime

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from modules.ai_classifier import batch_classify, get_rpm_status, _get_gemini_keys


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
from modules.config import get_config as _load_config


# ---------------------------------------------------------------------------
# Similar history from SQLite
# ---------------------------------------------------------------------------

def get_similar_history(order: dict, limit: int = 5) -> list:
    """
    FTS5 search po_history for similar orders by BQMS code + spec keywords.
    Returns list of dicts sorted by relevance.
    """
    try:
        from modules.database import get_connection, _resolve_db_path
        db_path = _resolve_db_path()

        code = order.get('bqms', '') or order.get('bqms_code', '')
        spec = order.get('spec', '') or ''

        conn = get_connection(db_path)
        rows = []

        # Try exact BQMS code match first
        if code:
            rows = conn.execute(
                "SELECT * FROM po_history WHERE bqms_code = ? ORDER BY created_at DESC LIMIT ?",
                (code, limit)
            ).fetchall()

        # If no exact match, search by first 3 words of spec
        if not rows and spec.strip():
            keywords = spec.strip().split()[:3]
            for kw in keywords:
                if len(kw) > 3:
                    r = conn.execute(
                        "SELECT * FROM po_history WHERE spec LIKE ? LIMIT ?",
                        (f'%{kw}%', limit)
                    ).fetchall()
                    if r:
                        rows = r
                        break

        conn.close()
        return [dict(r) for r in rows[:limit]]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Filter rules
# ---------------------------------------------------------------------------

def load_filter_rules() -> list:
    """
    Load filter rules from config or Google Sheets (future).
    Returns list of rule strings.
    """
    cfg = _load_config()

    # Check for local rules file
    rules_path = os.path.join(_ROOT, 'cache', 'filter_rules.json')
    if os.path.exists(rules_path):
        try:
            with open(rules_path, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            pass

    # Default rules
    return [
        "Ưu tiên đơn Samsung Electronics Vietnam (SEV) chính hãng",
        "Ưu tiên Thương mại (TM) hơn Gia công (GC)",
        "Bỏ qua đơn hàng có deadline < 2 giờ",
        "Tham gia nếu win_rate lịch sử > 50%",
        "Xem lại nếu là loại hàng mới chưa có trong DB",
    ]


def save_filter_rules(rules: list) -> None:
    rules_path = os.path.join(_ROOT, 'cache', 'filter_rules.json')
    os.makedirs(os.path.dirname(rules_path), exist_ok=True)
    with open(rules_path, 'w', encoding='utf-8') as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def log_classification_override(
    order_id: str,
    original_decision: str,
    new_decision: str,
    reason: str = "Manual override"
) -> None:
    """Write override action to audit log file."""
    log_dir = os.path.join(_ROOT, _load_config().get('log_dir', 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'audit.jsonl')

    entry = {
        'ts':          datetime.now().isoformat(),
        'action':      'classification_override',
        'order_id':    order_id,
        'original':    original_decision,
        'new':         new_decision,
        'reason':      reason,
    }
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def log_classification_result(order_id: str, result: dict) -> None:
    """Write classification result to audit log."""
    log_dir  = os.path.join(_ROOT, _load_config().get('log_dir', 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'audit.jsonl')

    entry = {
        'ts':       datetime.now().isoformat(),
        'action':   'classification',
        'order_id': order_id,
        **{k: v for k, v in result.items() if k in
           ('decision', 'confidence', 'reason', 'similar_wins', 'key_used')},
    }
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


# ---------------------------------------------------------------------------
# Main batch process
# ---------------------------------------------------------------------------

def process_batch(
    orders: list,
    progress_callback=None
) -> list:
    """
    Classify a batch of orders.
    Returns list of results with order data merged in.
    """
    rules = load_filter_rules()

    def _similar(order):
        return get_similar_history(order, limit=5)

    raw_results = batch_classify(
        orders,
        similar_fn=_similar,
        rules=rules,
        progress_callback=progress_callback,
    )

    # Merge order data into results for UI
    merged = []
    for i, result in enumerate(raw_results):
        order = orders[i] if i < len(orders) else {}
        merged.append({
            **order,
            **result,
            'overridden': False,
            'final_decision': result.get('decision', 'maybe'),
        })
        # Log to audit
        log_classification_result(result.get('order_id', ''), result)

    return merged


def get_key_status() -> list:
    """Return RPM status for all configured keys."""
    keys = _get_gemini_keys()
    return get_rpm_status(keys)


def get_keys_count() -> int:
    return len(_get_gemini_keys())


# ---------------------------------------------------------------------------
# Stats calculation
# ---------------------------------------------------------------------------

def calc_batch_stats(results: list) -> dict:
    total   = len(results)
    yes_cnt = sum(1 for r in results if r.get('final_decision') == 'yes')
    no_cnt  = sum(1 for r in results if r.get('final_decision') == 'no')
    may_cnt = sum(1 for r in results if r.get('final_decision') == 'maybe')
    err_cnt = sum(1 for r in results if r.get('error'))
    avg_conf = (
        sum(r.get('confidence', 0) for r in results) / total
        if total > 0 else 0
    )
    return {
        'total':        total,
        'yes':          yes_cnt,
        'no':           no_cnt,
        'maybe':        may_cnt,
        'errors':       err_cnt,
        'avg_confidence': round(avg_conf * 100, 1),
    }
