"""
tests/test_database.py
Unit tests for modules/database.py (all 8 public functions).
Uses a real in-memory / tmp SQLite so FTS5 triggers are exercised.
"""

import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db(tmp_path):
    """Fresh temp database for each test."""
    from modules.database import init_sqlite_db
    path = str(tmp_path / "test_bsmq.db")
    init_sqlite_db(path)
    return path


# ---------------------------------------------------------------------------
# init_sqlite_db
# ---------------------------------------------------------------------------

def test_init_creates_tables(db):
    from modules.database import get_connection
    conn = get_connection(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "products" in tables
    assert "po_history" in tables
    assert "job_log" in tables


def test_init_is_idempotent(db):
    from modules.database import init_sqlite_db
    init_sqlite_db(db)   # second call — must not raise
    init_sqlite_db(db)   # third call
    from modules.database import get_connection
    conn = get_connection(db)
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    conn.close()
    assert count == 0


# ---------------------------------------------------------------------------
# upsert_product + search_products
# ---------------------------------------------------------------------------

def test_upsert_and_search(db):
    from modules.database import upsert_product, search_products
    upsert_product({"code": "BQ001", "name": "Capacitor", "spec": "100uF 25V", "type": "tm", "maker": "Murata"}, db)
    results = search_products("Capacitor", db_path=db)
    assert len(results) == 1
    assert results[0]["code"] == "BQ001"


def test_upsert_updates_existing(db):
    from modules.database import upsert_product, search_products
    upsert_product({"code": "BQ002", "name": "Resistor", "type": "gc", "maker": "Yageo"}, db)
    upsert_product({"code": "BQ002", "name": "Resistor v2", "type": "gc", "maker": "Yageo"}, db)
    results = search_products("Resistor", db_path=db)
    # Only one row (upserted)
    assert len(results) == 1
    assert results[0]["name"] == "Resistor v2"


def test_search_empty_query_returns_all(db):
    from modules.database import upsert_product, search_products
    upsert_product({"code": "A001", "name": "Part A", "type": "tm"}, db)
    upsert_product({"code": "B001", "name": "Part B", "type": "gc"}, db)
    results = search_products("", db_path=db)
    assert len(results) == 2


def test_search_type_filter(db):
    from modules.database import upsert_product, search_products
    upsert_product({"code": "T001", "name": "TM part", "type": "tm"}, db)
    upsert_product({"code": "G001", "name": "GC part", "type": "gc"}, db)
    tm_results = search_products("", type_filter="tm", db_path=db)
    gc_results = search_products("", type_filter="gc", db_path=db)
    assert all(r["type"] == "tm" for r in tm_results)
    assert all(r["type"] == "gc" for r in gc_results)


def test_search_returns_empty_on_no_match(db):
    from modules.database import search_products
    results = search_products("zzznomatch", db_path=db)
    assert results == []


# ---------------------------------------------------------------------------
# get_db_stats
# ---------------------------------------------------------------------------

def test_get_db_stats_empty(db):
    from modules.database import get_db_stats
    stats = get_db_stats(db)
    assert stats["total"] == 0
    assert stats["gc"] == 0
    assert stats["tm"] == 0


def test_get_db_stats_counts(db):
    from modules.database import upsert_product, get_db_stats
    upsert_product({"code": "S001", "type": "tm", "price_status": "ok"}, db)
    upsert_product({"code": "S002", "type": "gc", "price_status": "none"}, db)
    stats = get_db_stats(db)
    assert stats["total"] == 2
    assert stats["tm"] == 1
    assert stats["gc"] == 1
    assert stats["ok"] == 1


# ---------------------------------------------------------------------------
# job_log
# ---------------------------------------------------------------------------

def test_add_and_update_job_log(db):
    from modules.database import add_job_log, update_job_log, get_connection
    job_id = add_job_log("autofill", "RFQ-001", db)
    assert isinstance(job_id, int) and job_id > 0

    update_job_log(job_id, "done", progress=100, message="Completed", db_path=db)
    conn = get_connection(db)
    row = conn.execute("SELECT * FROM job_log WHERE id=?", (job_id,)).fetchone()
    conn.close()
    assert row["status"] == "done"
    assert row["progress"] == 100
    assert row["finished_at"] is not None


# ---------------------------------------------------------------------------
# add_po_history
# ---------------------------------------------------------------------------

def test_add_po_history(db):
    from modules.database import add_po_history, get_connection
    po_id = add_po_history({
        "rfq_no": "RFQ-2026-001",
        "bqms_code": "BQ001",
        "round": 1,
        "price_submitted": 99.5,
        "status": "win",
        "ai_decision": "BID",
        "ai_confidence": 0.95,
    }, db)
    assert po_id > 0
    conn = get_connection(db)
    row = conn.execute("SELECT * FROM po_history WHERE id=?", (po_id,)).fetchone()
    conn.close()
    assert row["rfq_no"] == "RFQ-2026-001"
    assert row["ai_decision"] == "BID"
