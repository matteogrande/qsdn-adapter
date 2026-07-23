"""SQLite-backed audit store.

Concurrency: a single persistent connection in WAL mode, guarded by a short lock
around each insert. This removes the per-write connect/close overhead (and the
rollback-journal fsync) that serialised the whole provisioning pipeline — every
request emits ~8 awaited audit writes, so the audit path is on the critical path
for throughput. WAL + synchronous=NORMAL lets writers append quickly while
readers stay non-blocking.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from shared.models import AuditEvent


class AuditStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        # One shared connection across the FastAPI threadpool workers.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS events (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       request_id TEXT, service TEXT, event_type TEXT,
                       timestamp TEXT, payload TEXT)"""
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_request_id ON events(request_id)"
            )
            self._conn.commit()

    def add(self, event: AuditEvent) -> None:
        payload = event.model_dump_json()
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (request_id, service, event_type, timestamp, payload)"
                " VALUES (?, ?, ?, ?, ?)",
                (event.request_id, event.service, event.event_type,
                 event.timestamp, payload),
            )
            self._conn.commit()

    def query(self, request_id: str | None = None, limit: int = 200) -> list[dict]:
        sql = "SELECT payload FROM events"
        params: list = []
        if request_id:
            sql += " WHERE request_id = ?"
            params.append(request_id)
        sql += " ORDER BY id ASC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [json.loads(r["payload"]) for r in rows]
