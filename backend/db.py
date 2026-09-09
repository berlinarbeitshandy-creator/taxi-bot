"""SQLite-Zugriff. Bewusst schlank gehalten - keine ORM-Abhaengigkeit."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    label         TEXT    NOT NULL DEFAULT '',
    phone         TEXT    NOT NULL UNIQUE,
    api_id        INTEGER NOT NULL,
    api_hash_enc  TEXT    NOT NULL,
    session_enc   TEXT,
    proxy         TEXT,
    device_id     TEXT    NOT NULL DEFAULT 'desktop_windows',
    status        TEXT    NOT NULL DEFAULT 'pending',
    tg_user_id    INTEGER,
    username      TEXT,
    first_name    TEXT,
    is_premium    INTEGER NOT NULL DEFAULT 0,
    last_error    TEXT,
    last_check    REAL,
    adds_used     INTEGER NOT NULL DEFAULT 0,
    cooldown_until REAL,
    created_at    REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS pool (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    note        TEXT    NOT NULL DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'new',
    reason      TEXT    NOT NULL DEFAULT '',
    assigned_to INTEGER,
    tg_user_id  INTEGER,
    display     TEXT,
    is_premium  INTEGER NOT NULL DEFAULT 0,
    checked_at  REAL,
    created_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT    NOT NULL,
    account_id  INTEGER,
    target      TEXT    NOT NULL DEFAULT '',
    status      TEXT    NOT NULL DEFAULT 'queued',
    params      TEXT    NOT NULL DEFAULT '{}',
    stats       TEXT    NOT NULL DEFAULT '{}',
    log         TEXT    NOT NULL DEFAULT '[]',
    created_at  REAL    NOT NULL,
    finished_at REAL
);

CREATE INDEX IF NOT EXISTS idx_pool_status ON pool(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    conn = _connect()
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with cursor() as cur:
        cur.executescript(SCHEMA)
        _migrate(cur)


def _migrate(cur: sqlite3.Cursor) -> None:
    """Bringt aeltere Datenbanken auf den aktuellen Stand."""
    columns = {row[1] for row in cur.execute("PRAGMA table_info(pool)").fetchall()}
    if "reason" not in columns:
        cur.execute("ALTER TABLE pool ADD COLUMN reason TEXT NOT NULL DEFAULT ''")
    if "assigned_to" not in columns:
        cur.execute("ALTER TABLE pool ADD COLUMN assigned_to INTEGER")

    columns = {row[1] for row in cur.execute("PRAGMA table_info(accounts)").fetchall()}
    if "adds_used" not in columns:
        cur.execute(
            "ALTER TABLE accounts ADD COLUMN adds_used INTEGER NOT NULL DEFAULT 0"
        )
    if "cooldown_until" not in columns:
        cur.execute("ALTER TABLE accounts ADD COLUMN cooldown_until REAL")

    columns = {row[1] for row in cur.execute("PRAGMA table_info(jobs)").fetchall()}
    if "params" not in columns:
        cur.execute("ALTER TABLE jobs ADD COLUMN params TEXT NOT NULL DEFAULT '{}'")

    # 'invalid' hiess frueher, was heute 'dead' heisst.
    cur.execute(
        "UPDATE pool SET status = 'dead', reason = 'existiert nicht' "
        "WHERE status = 'invalid'"
    )


def query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with cursor() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def query_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = ()) -> int:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.lastrowid


def now() -> float:
    return time.time()


def loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
