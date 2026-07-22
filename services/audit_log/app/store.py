"""SQLite-backed audit store. Thread-safe enough for the simulation."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from shared.models import AuditEvent

_LOCK = threading.Lock()


class AuditStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with _LOCK, self._conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS events (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       request_id TEXT, service TEXT, event_type TEXT,
                       timestamp TEXT, payload TEXT)"""
            )

    def add(self, event: AuditEvent) -> None:
        with _LOCK, self._conn() as conn:
            conn.execute(
                "INSERT INTO events (request_id, service, event_type, timestamp, payload)"
                " VALUES (?, ?, ?, ?, ?)",
                (event.request_id, event.service, event.event_type,
                 event.timestamp, event.model_dump_json()),
            )

    def query(self, request_id: str | None = None, limit: int = 200) -> list[dict]:
        sql = "SELECT payload FROM events"
        params: list = []
        if request_id:
            sql += " WHERE request_id = ?"
            params.append(request_id)
        sql += " ORDER BY id ASC LIMIT ?"
        params.append(limit)
        with _LOCK, self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [json.loads(r["payload"]) for r in rows]
