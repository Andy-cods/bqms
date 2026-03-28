"""
modules/ai_classifier.py
Gemini AI classifier with 4-key rotation + 60 rpm rate limiting.
Pure Python — no Streamlit dependency.
"""

import os
import re
import json
import time
import threading
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------
from modules.config import get_config as _load_config


def _get_gemini_keys() -> list:
    """Load keys from config.json gemini_keys[] or GEMINI_KEY_1..4 env vars."""
    cfg  = _load_config()
    keys = [k for k in cfg.get('gemini_keys', []) if k and k.strip()]
    # Supplement from env vars
    for i in range(1, 5):
        env_key = os.environ.get(f'GEMINI_KEY_{i}', '').strip()
        if env_key and env_key not in keys:
            keys.append(env_key)
    return keys


# ---------------------------------------------------------------------------
# Rate limiter — 60 req/min per key
# ---------------------------------------------------------------------------

RPM_LIMIT    = 60
RPM_BUFFER   = 5           # Use 55 as effective limit for safety
RPM_WINDOW   = 60.0        # seconds

_rpm_lock    = threading.Lock()
_rpm_counts: dict  = {}    # key_index -> list of timestamps


def _record_request(key_idx: int) -> None:
    now = time.time()
    with _rpm_lock:
        if key_idx not in _rpm_counts:
            _rpm_counts[key_idx] = []
        _rpm_counts[key_idx].append(now)
        # Prune old entries outside window
        cutoff = now - RPM_WINDOW
        _rpm_counts[key_idx] = [t for t in _rpm_counts[key_idx] if t > cutoff]


def _get_rpm(key_idx: int) -> int:
    now = time.time()
    with _rpm_lock:
        if key_idx not in _rpm_counts:
            return 0
        cutoff = now - RPM_WINDOW
        return sum(1 for t in _rpm_counts[key_idx] if t > cutoff)


def _is_key_available(key_idx: int) -> bool:
    return _get_rpm(key_idx) < (RPM_LIMIT - RPM_BUFFER)


def get_rpm_status(keys: list) -> list:
    """Return list of {index, rpm, available} for UI display."""
    return [
        {
            'index':     i,
            'rpm':       _get_rpm(i),
            'limit':     RPM_LIMIT,
            'available': _is_key_available(i),
        }
        for i in range(len(keys))
    ]


# ---------------------------------------------------------------------------
# Key rotation
# ---------------------------------------------------------------------------

_current_key_idx = 0
_key_lock        = threading.Lock()


def _pick_key(keys: list) -> tuple:
    """
    Round-robin key selection, skipping keys at rate limit.
    Returns (key_index, api_key) or raises RuntimeError if all exhausted.
    Waits up to RPM_WINDOW seconds if all keys are at limit.
    """
    global _current_key_idx
    n = len(keys)
    if n == 0:
        raise RuntimeError("Không có Gemini API key — điền vào config.json hoặc .env")

    deadline = time.time() + RPM_WINDOW
    while time.time() < deadline:
        with _key_lock:
            for _ in range(n):
                idx = _current_key_idx % n
                if _is_key_available(idx):
                    _current_key_idx = (idx + 1) % n
                    return idx, keys[idx]
                _current_key_idx = (_current_key_idx + 1) % n
        # All keys at limit — wait a bit and retry
        time.sleep(2)

    raise RuntimeError("Tất cả Gemini keys đã đạt giới hạn 60 rpm — thử lại sau.")


# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str, api_key: str, model: str = "gemini-1.5-flash") -> str:
    """
    Call Gemini API via google-generativeai.
    Returns response text or raises exception.
    """
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_obj = genai.GenerativeModel(model)
        response  = model_obj.generate_content(prompt)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}") from e


# ---------------------------------------------------------------------------
# JSON extraction from Gemini response
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Extract first JSON object from Gemini response text."""
    # Try to find ```json ... ``` block first
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        # Find first {...} block
        m = re.search(r'\{.*?\}', text, re.DOTALL)
        if m:
            raw = m.group(0)
        else:
            raise ValueError(f"Không tìm thấy JSON trong response: {text[:200]}")
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Classifier prompt
# ---------------------------------------------------------------------------

CLASSIFIER_SYSTEM_PROMPT = """
Bạn là AI phân tích đơn hàng linh kiện điện tử tại Samsung Vietnam.

Nhiệm vụ: Quyết định có nên tham gia báo giá đơn hàng này không.

Thông tin đơn:
- Mã BQMS: {bqms_code}
- Spec: {spec}
- Maker: {maker}
- Loại: {loai_hang}
- Số lượng: {qty}
- Hạn: {deadline}

Lịch sử tương tự từ DB (top-5 giống nhất):
{similar_history}

Filter Rules hiện tại:
{rules}

Trả lời ĐÚNG format JSON (không thêm text ngoài):
{{
  "decision": "yes",
  "confidence": 0.85,
  "reason": "Giải thích ngắn gọn bằng tiếng Việt (1-2 câu)",
  "similar_wins": 3,
  "price_hint": "Giá tham khảo nếu có, hoặc null"
}}

decision: "yes" (tham gia) | "no" (bỏ qua) | "maybe" (xem lại)
confidence: 0.0 đến 1.0
""".strip()


# ---------------------------------------------------------------------------
# Single-order classification
# ---------------------------------------------------------------------------

def classify_order(
    order: dict,
    similar_history: list,
    rules: list,
    keys: list,
    retry: int = 3
) -> dict:
    """
    Classify a single order using Gemini.
    Returns: {decision, confidence, reason, similar_wins, price_hint, key_used, error}
    """
    history_text = _format_history(similar_history)
    rules_text   = _format_rules(rules)

    prompt = CLASSIFIER_SYSTEM_PROMPT.format(
        bqms_code      = order.get('bqms', '') or order.get('bqms_code', ''),
        spec           = (order.get('spec', '') or '')[:400],
        maker          = order.get('maker', ''),
        loai_hang      = order.get('loai_hang', ''),
        qty            = order.get('so_luong', ''),
        deadline       = order.get('han_bg', ''),
        similar_history= history_text,
        rules          = rules_text,
    )

    last_err = None
    for attempt in range(retry):
        try:
            key_idx, api_key = _pick_key(keys)
            _record_request(key_idx)
            raw_text = _call_gemini(prompt, api_key)
            data     = _extract_json(raw_text)

            return {
                'decision':     data.get('decision', 'maybe'),
                'confidence':   float(data.get('confidence', 0.5)),
                'reason':       data.get('reason', ''),
                'similar_wins': int(data.get('similar_wins', 0)),
                'price_hint':   data.get('price_hint'),
                'key_used':     key_idx,
                'error':        None,
            }
        except RuntimeError as e:
            # Rate limit — propagate immediately
            raise
        except Exception as e:
            last_err = str(e)
            if attempt < retry - 1:
                time.sleep(1.5 * (attempt + 1))

    return {
        'decision':     'maybe',
        'confidence':   0.0,
        'reason':       f'Lỗi AI: {last_err}',
        'similar_wins': 0,
        'price_hint':   None,
        'key_used':     -1,
        'error':        last_err,
    }


# ---------------------------------------------------------------------------
# Batch classification
# ---------------------------------------------------------------------------

def batch_classify(
    orders: list,
    similar_fn,          # callable(order) -> list[dict] — returns similar history
    rules: list,
    progress_callback=None,   # fn(current, total, order_id, result)
) -> list:
    """
    Classify a list of orders.
    Returns list of result dicts (same order as input).
    """
    keys    = _get_gemini_keys()
    results = []
    total   = len(orders)

    for i, order in enumerate(orders):
        order_id = order.get('don_hang') or order.get('bqms', f'#{i}')

        try:
            history = similar_fn(order) if similar_fn else []
            result  = classify_order(order, history, rules, keys)
        except RuntimeError as e:
            result = {
                'decision': 'maybe', 'confidence': 0.0,
                'reason': str(e), 'similar_wins': 0,
                'price_hint': None, 'key_used': -1, 'error': str(e),
            }

        result['order_id']    = order_id
        result['order_index'] = i
        results.append(result)

        if progress_callback:
            progress_callback(i + 1, total, order_id, result)

    return results


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_history(history: list) -> str:
    if not history:
        return "Không có lịch sử tương tự."
    lines = []
    for i, h in enumerate(history[:5], 1):
        status = h.get('status', '?')
        won    = '✓ Thắng' if status == 'won' else ('✗ Thua' if status == 'lost' else status)
        lines.append(
            f"{i}. [{won}] {h.get('bqms_code','')} — {h.get('spec','')[:60]}"
            f" | Giá: {h.get('price_submitted','?')} | Vòng: {h.get('round','?')}"
        )
    return "\n".join(lines)


def _format_rules(rules: list) -> str:
    if not rules:
        return "Không có rules. Phân tích dựa trên lịch sử."
    return "\n".join(f"- {r}" for r in rules[:20])
