"""
modules/database.py
SQLite + FTS5 database layer for BSMQ Automation System.
Tables: products, products_fts (FTS5), po_history, job_log
"""

import sqlite3
import os
import json
import time
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------
from modules.config import get_config as _mc_get_config


def _resolve_db_path(db_path: Optional[str] = None) -> str:
    if db_path:
        return db_path
    return _mc_get_config().get('db_path', './bsmq.db')


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema init
# ---------------------------------------------------------------------------

DDL_PRODUCTS = """
CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT    UNIQUE NOT NULL,
    name            TEXT,
    spec            TEXT,
    type            TEXT    CHECK(type IN ('gc', 'tm')),
    maker           TEXT,
    unit            TEXT    DEFAULT 'EA',
    price           REAL,
    price_source    TEXT,
    price_updated   DATE,
    price_status    TEXT    DEFAULT 'none',
    win_count       INTEGER DEFAULT 0,
    lose_count      INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

DDL_PRODUCTS_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
    code, name, spec, maker,
    content='products',
    content_rowid='id',
    tokenize='unicode61'
);
"""

DDL_PO_HISTORY = """
CREATE TABLE IF NOT EXISTS po_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rfq_no          TEXT    NOT NULL,
    bqms_code       TEXT,
    round           INTEGER DEFAULT 1,
    price_submitted REAL,
    deadline        TEXT,
    status          TEXT,
    ai_decision     TEXT,
    ai_confidence   REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

DDL_JOB_LOG = """
CREATE TABLE IF NOT EXISTS job_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type    TEXT,
    job_ref     TEXT,
    status      TEXT    DEFAULT 'running',
    progress    INTEGER DEFAULT 0,
    message     TEXT,
    started_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);
"""

# FTS triggers — keep FTS in sync with products table
DDL_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS products_ai AFTER INSERT ON products BEGIN
    INSERT INTO products_fts(rowid, code, name, spec, maker)
    VALUES (new.id, new.code, new.name, new.spec, new.maker);
END;

CREATE TRIGGER IF NOT EXISTS products_ad AFTER DELETE ON products BEGIN
    INSERT INTO products_fts(products_fts, rowid, code, name, spec, maker)
    VALUES ('delete', old.id, old.code, old.name, old.spec, old.maker);
END;

CREATE TRIGGER IF NOT EXISTS products_au AFTER UPDATE ON products BEGIN
    INSERT INTO products_fts(products_fts, rowid, code, name, spec, maker)
    VALUES ('delete', old.id, old.code, old.name, old.spec, old.maker);
    INSERT INTO products_fts(rowid, code, name, spec, maker)
    VALUES (new.id, new.code, new.name, new.spec, new.maker);
END;
"""


DDL_MARKET = """
CREATE TABLE IF NOT EXISTS price_confirmed (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    bqms_code       TEXT,
    product_name    TEXT    NOT NULL,
    spec            TEXT,
    maker           TEXT,
    confirmed_price REAL    NOT NULL,
    currency        TEXT    DEFAULT 'USD',
    price_usd       REAL,
    supplier_name   TEXT,
    supplier_url    TEXT,
    platform        TEXT,
    moq             INTEGER,
    notes           TEXT,
    confirmed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS search_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key   TEXT    UNIQUE NOT NULL,
    platforms   TEXT,
    query       TEXT,
    result_json TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_sqlite_db(db_path: Optional[str] = None) -> None:
    """Create all tables + FTS virtual table + triggers. Idempotent."""
    path = _resolve_db_path(db_path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = get_connection(path)
    try:
        conn.executescript(
            DDL_PRODUCTS +
            DDL_PRODUCTS_FTS +
            DDL_PO_HISTORY +
            DDL_JOB_LOG +
            DDL_FTS_TRIGGERS +
            DDL_MARKET
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Product search
# ---------------------------------------------------------------------------

def _sanitize_fts_query(query: str) -> str:
    """Escape special FTS5 chars so raw input is safe."""
    # Wrap in quotes to treat as phrase, strip internal quotes
    q = query.replace('"', ' ').strip()
    if not q:
        return ''
    # If query has multiple words, use AND by default
    words = q.split()
    return ' '.join(f'"{w}"' for w in words)


def search_products(
    query: str = '',
    type_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    db_path: Optional[str] = None,
    limit: int = 200
) -> list[dict]:
    """
    FTS5 full-text search across code/name/spec/maker.
    Falls back to full table scan when query is empty.
    """
    path = _resolve_db_path(db_path)
    if not os.path.exists(path):
        return []

    conn = get_connection(path)
    try:
        conditions = []
        params = []

        if type_filter:
            conditions.append("p.type = ?")
            params.append(type_filter)
        if status_filter:
            conditions.append("p.price_status = ?")
            params.append(status_filter)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        if query.strip():
            fts_q = _sanitize_fts_query(query)
            sql = f"""
                SELECT p.*, rank
                FROM products p
                JOIN products_fts ON products_fts.rowid = p.id
                WHERE products_fts MATCH ?
                {"AND " + " AND ".join(conditions) if conditions else ""}
                ORDER BY rank
                LIMIT ?
            """
            params_fts = [fts_q] + params + [limit]
            rows = conn.execute(sql, params_fts).fetchall()
        else:
            sql = f"""
                SELECT * FROM products p
                {where_clause}
                ORDER BY updated_at DESC
                LIMIT ?
            """
            rows = conn.execute(sql, params + [limit]).fetchall()

        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_db_stats(db_path: Optional[str] = None) -> dict:
    """Return counts by type and price_status, plus query latency."""
    path = _resolve_db_path(db_path)
    if not os.path.exists(path):
        return {'total': 0, 'gc': 0, 'tm': 0, 'ok': 0, 'expired': 0, 'none': 0, 'query_ms': 0}

    t0 = time.monotonic()
    conn = get_connection(path)
    try:
        row = conn.execute("""
            SELECT
                COUNT(*)                                    AS total,
                SUM(CASE WHEN type='gc' THEN 1 ELSE 0 END) AS gc,
                SUM(CASE WHEN type='tm' THEN 1 ELSE 0 END) AS tm,
                SUM(CASE WHEN price_status='ok'      THEN 1 ELSE 0 END) AS ok,
                SUM(CASE WHEN price_status='expired' THEN 1 ELSE 0 END) AS expired,
                SUM(CASE WHEN price_status='none'    THEN 1 ELSE 0 END) AS none_count
            FROM products
        """).fetchone()
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            'total':    row['total']      or 0,
            'gc':       row['gc']         or 0,
            'tm':       row['tm']         or 0,
            'ok':       row['ok']         or 0,
            'expired':  row['expired']    or 0,
            'none':     row['none_count'] or 0,
            'query_ms': elapsed_ms,
        }
    except sqlite3.OperationalError:
        return {'total': 0, 'gc': 0, 'tm': 0, 'ok': 0, 'expired': 0, 'none': 0, 'query_ms': 0}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Product upsert
# ---------------------------------------------------------------------------

def upsert_product(data: dict, db_path: Optional[str] = None) -> int:
    """
    INSERT OR REPLACE product. Returns row id.
    FTS triggers handle index updates automatically.
    """
    path = _resolve_db_path(db_path)
    now = datetime.now().isoformat()
    conn = get_connection(path)
    try:
        cur = conn.execute("""
            INSERT INTO products
                (code, name, spec, type, maker, unit, price, price_source,
                 price_updated, price_status, win_count, lose_count, updated_at)
            VALUES
                (:code, :name, :spec, :type, :maker, :unit, :price, :price_source,
                 :price_updated, :price_status, :win_count, :lose_count, :updated_at)
            ON CONFLICT(code) DO UPDATE SET
                name          = excluded.name,
                spec          = excluded.spec,
                type          = excluded.type,
                maker         = excluded.maker,
                unit          = excluded.unit,
                price         = excluded.price,
                price_source  = excluded.price_source,
                price_updated = excluded.price_updated,
                price_status  = excluded.price_status,
                win_count     = excluded.win_count,
                lose_count    = excluded.lose_count,
                updated_at    = excluded.updated_at
        """, {
            'code':         data.get('code', ''),
            'name':         data.get('name'),
            'spec':         data.get('spec'),
            'type':         data.get('type'),
            'maker':        data.get('maker'),
            'unit':         data.get('unit', 'EA'),
            'price':        data.get('price'),
            'price_source': data.get('price_source'),
            'price_updated':data.get('price_updated'),
            'price_status': data.get('price_status', 'none'),
            'win_count':    data.get('win_count', 0),
            'lose_count':   data.get('lose_count', 0),
            'updated_at':   now,
        })
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# FTS index rebuild
# ---------------------------------------------------------------------------

def rebuild_fts_index(db_path: Optional[str] = None) -> None:
    """Full FTS5 index rebuild from products table."""
    path = _resolve_db_path(db_path)
    conn = get_connection(path)
    try:
        conn.execute("INSERT INTO products_fts(products_fts) VALUES('rebuild')")
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Job log
# ---------------------------------------------------------------------------

def add_job_log(job_type: str, job_ref: str = '', db_path: Optional[str] = None) -> int:
    """Insert a new job_log row (status='running'). Returns job_id."""
    path = _resolve_db_path(db_path)
    conn = get_connection(path)
    try:
        cur = conn.execute(
            "INSERT INTO job_log (job_type, job_ref, status, started_at) VALUES (?, ?, 'running', ?)",
            (job_type, job_ref, datetime.now().isoformat())
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_job_log(
    job_id: int,
    status: str,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    db_path: Optional[str] = None
) -> None:
    """Update job_log row. Set finished_at when status is done/error."""
    path = _resolve_db_path(db_path)
    conn = get_connection(path)
    try:
        finished = datetime.now().isoformat() if status in ('done', 'error', 'cancelled') else None
        conn.execute("""
            UPDATE job_log
            SET status      = ?,
                progress    = COALESCE(?, progress),
                message     = COALESCE(?, message),
                finished_at = COALESCE(?, finished_at)
            WHERE id = ?
        """, (status, progress, message, finished, job_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# PO history helpers
# ---------------------------------------------------------------------------

def add_po_history(data: dict, db_path: Optional[str] = None) -> int:
    path = _resolve_db_path(db_path)
    conn = get_connection(path)
    try:
        cur = conn.execute("""
            INSERT INTO po_history
                (rfq_no, bqms_code, round, price_submitted, deadline,
                 status, ai_decision, ai_confidence)
            VALUES
                (:rfq_no, :bqms_code, :round, :price_submitted, :deadline,
                 :status, :ai_decision, :ai_confidence)
        """, {
            'rfq_no':         data.get('rfq_no', ''),
            'bqms_code':      data.get('bqms_code'),
            'round':          data.get('round', 1),
            'price_submitted':data.get('price_submitted'),
            'deadline':       data.get('deadline'),
            'status':         data.get('status', 'pending'),
            'ai_decision':    data.get('ai_decision'),
            'ai_confidence':  data.get('ai_confidence'),
        })
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
