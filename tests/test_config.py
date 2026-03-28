"""
tests/test_config.py
Unit tests for modules/config.py
"""

import json
import os
import sys
import pytest
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_config(tmp_path, monkeypatch):
    """Redirect _CONFIG_PATH to a temp file so tests never touch real config."""
    import modules.config as cfg_mod
    fake_path = tmp_path / "config.json"
    monkeypatch.setattr(cfg_mod, "_CONFIG_PATH", fake_path)
    return fake_path


# ---------------------------------------------------------------------------
# get_config()
# ---------------------------------------------------------------------------

def test_get_config_returns_defaults_when_file_missing(tmp_config):
    from modules.config import get_config, _DEFAULTS
    result = get_config()
    assert isinstance(result, dict)
    for k, v in _DEFAULTS.items():
        assert result[k] == v


def test_get_config_reads_file(tmp_config):
    from modules.config import get_config
    tmp_config.write_text(json.dumps({"db_path": "/custom/bsmq.db", "my_key": "hello"}), encoding="utf-8")
    result = get_config()
    assert result["db_path"] == "/custom/bsmq.db"
    assert result["my_key"] == "hello"


def test_get_config_fills_missing_defaults(tmp_config):
    from modules.config import get_config
    # Write only one key — others should be filled from _DEFAULTS
    tmp_config.write_text(json.dumps({"db_path": "x.db"}), encoding="utf-8")
    result = get_config()
    assert result["db_path"] == "x.db"
    assert "rfq_folder" in result


def test_get_config_returns_defaults_on_corrupt_file(tmp_config):
    from modules.config import get_config, _DEFAULTS
    tmp_config.write_text("NOT JSON {{{{", encoding="utf-8")
    result = get_config()
    assert result == _DEFAULTS


# ---------------------------------------------------------------------------
# save_config()
# ---------------------------------------------------------------------------

def test_save_config_writes_json(tmp_config):
    from modules.config import save_config, get_config
    payload = {"db_path": "test.db", "rfq_folder": "/rfq"}
    ok = save_config(payload)
    assert ok is True
    written = json.loads(tmp_config.read_text(encoding="utf-8"))
    assert written["db_path"] == "test.db"


def test_save_then_get_roundtrip(tmp_config):
    from modules.config import save_config, get_config
    original = get_config()
    original["rfq_folder"] = "/updated/rfq"
    save_config(original)
    reloaded = get_config()
    assert reloaded["rfq_folder"] == "/updated/rfq"


def test_save_config_returns_false_on_bad_path(monkeypatch):
    import modules.config as cfg_mod
    from modules.config import save_config
    monkeypatch.setattr(cfg_mod, "_CONFIG_PATH", Path("/nonexistent/dir/config.json"))
    result = save_config({"key": "val"})
    assert result is False


# ---------------------------------------------------------------------------
# resolve_soffice()
# ---------------------------------------------------------------------------

def test_resolve_soffice_returns_existing_path(tmp_path, tmp_config):
    from modules.config import resolve_soffice, save_config
    fake_exe = tmp_path / "soffice.exe"
    fake_exe.write_bytes(b"")
    save_config({"libreoffice_path": str(fake_exe)})
    result = resolve_soffice()
    assert result == str(fake_exe)


def test_resolve_soffice_uses_cfg_path_arg(tmp_path, tmp_config):
    from modules.config import resolve_soffice
    fake_exe = tmp_path / "soffice_arg.exe"
    fake_exe.write_bytes(b"")
    result = resolve_soffice(str(fake_exe))
    assert result == str(fake_exe)


def test_resolve_soffice_raises_when_not_found(tmp_config, monkeypatch):
    from modules.config import resolve_soffice, save_config
    import shutil
    save_config({"libreoffice_path": "/no/such/path/soffice.exe"})
    monkeypatch.setattr(shutil, "which", lambda _: None)
    # Also make glob yield nothing by monkeypatching Path.glob
    from pathlib import Path
    monkeypatch.setattr(Path, "glob", lambda self, pattern: iter([]))
    with pytest.raises(FileNotFoundError):
        resolve_soffice()
