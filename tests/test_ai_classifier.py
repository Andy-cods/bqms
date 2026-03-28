"""
tests/test_ai_classifier.py
Unit tests for modules/ai_classifier.py
Tests rate limiter and key rotation logic — Gemini HTTP is mocked.
"""

import sys
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_rpm_state():
    """Clear module-level rate-limit state between tests."""
    import modules.ai_classifier as ac
    with ac._rpm_lock:
        ac._rpm_counts.clear()
    with ac._key_lock:
        ac._current_key_idx = 0


# ---------------------------------------------------------------------------
# _get_gemini_keys via config
# ---------------------------------------------------------------------------

def test_get_gemini_keys_from_env(monkeypatch, tmp_path):
    """Keys from GEMINI_KEY_1..4 env vars are returned."""
    import modules.config as cfg_mod
    fake_cfg = tmp_path / "config.json"
    fake_cfg.write_text('{"gemini_keys": []}', encoding="utf-8")
    monkeypatch.setattr(cfg_mod, "_CONFIG_PATH", fake_cfg)

    monkeypatch.setenv("GEMINI_KEY_1", "key-aaa")
    monkeypatch.setenv("GEMINI_KEY_2", "key-bbb")
    monkeypatch.delenv("GEMINI_KEY_3", raising=False)
    monkeypatch.delenv("GEMINI_KEY_4", raising=False)

    from modules.ai_classifier import _get_gemini_keys
    keys = _get_gemini_keys()
    assert "key-aaa" in keys
    assert "key-bbb" in keys


# ---------------------------------------------------------------------------
# RPM rate limiter
# ---------------------------------------------------------------------------

def test_rpm_starts_at_zero():
    from modules.ai_classifier import _get_rpm
    _reset_rpm_state()
    assert _get_rpm(0) == 0


def test_record_and_count_rpm():
    from modules.ai_classifier import _record_request, _get_rpm
    _reset_rpm_state()
    _record_request(0)
    _record_request(0)
    _record_request(0)
    assert _get_rpm(0) == 3


def test_rpm_counts_different_keys_independently():
    from modules.ai_classifier import _record_request, _get_rpm
    _reset_rpm_state()
    _record_request(0)
    _record_request(0)
    _record_request(1)
    assert _get_rpm(0) == 2
    assert _get_rpm(1) == 1


def test_is_key_available_below_limit():
    from modules.ai_classifier import _is_key_available, RPM_LIMIT, RPM_BUFFER
    _reset_rpm_state()
    assert _is_key_available(0) is True


def test_is_key_available_at_limit():
    from modules.ai_classifier import _is_key_available, _record_request, RPM_LIMIT, RPM_BUFFER
    _reset_rpm_state()
    import modules.ai_classifier as ac
    # Fill up to effective limit
    effective = RPM_LIMIT - RPM_BUFFER
    for _ in range(effective):
        _record_request(0)
    assert _is_key_available(0) is False


# ---------------------------------------------------------------------------
# get_rpm_status
# ---------------------------------------------------------------------------

def test_get_rpm_status_structure():
    from modules.ai_classifier import get_rpm_status, _record_request
    _reset_rpm_state()
    _record_request(0)
    status = get_rpm_status(["key-a", "key-b"])
    assert len(status) == 2
    assert status[0]["index"] == 0
    assert status[0]["rpm"] == 1
    assert "available" in status[0]
    assert "limit" in status[0]


# ---------------------------------------------------------------------------
# batch_classify — mock Gemini HTTP
# ---------------------------------------------------------------------------

def test_batch_classify_empty_list():
    """Empty input → empty output, no API calls."""
    from modules.ai_classifier import batch_classify
    result = batch_classify([], similar_fn=lambda o: [], rules=[])
    assert result == []


def test_batch_classify_calls_classify_order():
    """batch_classify delegates to classify_order for each item."""
    from modules.ai_classifier import batch_classify

    mock_result = {
        "decision": "BID",
        "confidence": 0.9,
        "reasoning": "Good margin",
        "key_used": 0,
    }

    with patch("modules.ai_classifier.classify_order", return_value=mock_result) as mock_cls:
        orders = [{"rfq_no": "R001"}, {"rfq_no": "R002"}]
        results = batch_classify(orders, similar_fn=lambda o: [], rules=[])
        assert len(results) == 2
        assert mock_cls.call_count == 2
        assert results[0]["decision"] == "BID"


def test_batch_classify_progress_callback():
    """progress_callback is called once per item."""
    from modules.ai_classifier import batch_classify

    mock_result = {"decision": "SKIP", "confidence": 0.5, "reasoning": "", "key_used": 0}
    calls = []

    def on_progress(current, total, order_id, result):
        calls.append((current, total))

    with patch("modules.ai_classifier.classify_order", return_value=mock_result):
        batch_classify(
            [{"rfq_no": "R001"}, {"rfq_no": "R002"}],
            similar_fn=lambda o: [],
            rules=[],
            progress_callback=on_progress,
        )

    assert calls == [(1, 2), (2, 2)]
