"""SQLite persistence (WAL). A fresh connection per operation keeps it restart- and thread-safe."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import SCHEMA

DEFAULT_DB = Path(__file__).resolve().parents[2] / "var" / "bmh.sqlite3"


def db_path() -> Path:
    return Path(os.environ.get("BMH_DB_PATH") or DEFAULT_DB)


def connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


@contextmanager
def transaction():
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def get_package(package_id: str) -> Optional[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute("SELECT * FROM packages WHERE package_id=?", (package_id,)).fetchone()
    finally:
        conn.close()


def save_package(conn, package_id, status, request, spec, trip, reference=None, group_id=None, option=None):
    ts = now()
    existing = conn.execute("SELECT created_at, group_id, option_label FROM packages WHERE package_id=?", (package_id,)).fetchone()
    conn.execute(
        """INSERT INTO packages(package_id, group_id, option_label, status, reference, request_json, spec_json,
                                trip_json, total_inr, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(package_id) DO UPDATE SET status=excluded.status, reference=excluded.reference,
             request_json=excluded.request_json, spec_json=excluded.spec_json, trip_json=excluded.trip_json,
             total_inr=excluded.total_inr, updated_at=excluded.updated_at""",
        (package_id, group_id or (existing["group_id"] if existing else None), option or (existing["option_label"] if existing else None),
         status, reference, json.dumps(request), json.dumps(spec), json.dumps(trip), trip["total_inr"],
         existing["created_at"] if existing else ts, ts))


def get_reservation(reference: str) -> Optional[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute("SELECT * FROM reservations WHERE reference=?", (reference,)).fetchone()
    finally:
        conn.close()
