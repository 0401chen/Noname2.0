from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from time import monotonic
from typing import Protocol

from pydantic import ValidationError

from .schemas import SessionState

logger = logging.getLogger(__name__)


class SessionStore(Protocol):
    kind: str

    def get_or_create(self, session_id: str, age_group: str | None = None) -> SessionState: ...

    def save(self, state: SessionState) -> None: ...

    def clear(self, session_id: str) -> bool: ...

    def purge_expired(self, older_than: datetime) -> int: ...


class _RetentionMixin:
    retention: timedelta
    cleanup_interval_seconds: int
    _last_cleanup_at: float

    def _purge_if_due(self) -> None:
        now = monotonic()
        if now - self._last_cleanup_at < self.cleanup_interval_seconds:
            return
        self._last_cleanup_at = now
        cutoff = datetime.now(timezone.utc) - self.retention
        removed = self.purge_expired(cutoff)
        if removed:
            logger.info("Purged %s expired anonymous sessions", removed)


class MemorySessionStore(_RetentionMixin):
    kind = "memory"

    def __init__(
        self,
        *,
        retention_hours: int = 24,
        cleanup_interval_seconds: int = 300,
    ) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = RLock()
        self.retention = timedelta(hours=retention_hours)
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._last_cleanup_at = 0.0

    def get_or_create(self, session_id: str, age_group: str | None = None) -> SessionState:
        self._purge_if_due()
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                state = SessionState(session_id=session_id, age_group=age_group)
                self._sessions[session_id] = state
            elif age_group:
                state.age_group = age_group
            return state

    def save(self, state: SessionState) -> None:
        with self._lock:
            self._sessions[state.session_id] = state

    def clear(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def purge_expired(self, older_than: datetime) -> int:
        with self._lock:
            expired = [
                session_id
                for session_id, state in self._sessions.items()
                if state.updated_at < older_than
            ]
            for session_id in expired:
                del self._sessions[session_id]
            return len(expired)


class SQLiteSessionStore(_RetentionMixin):
    """Persist anonymous conversation state without collecting identity fields.

    The database stores one JSON document per random session id. SQLite is used so
    the competition prototype survives backend restarts while remaining easy to
    inspect, reset and run without external services. Records are automatically
    removed after the configured retention window.
    """

    kind = "sqlite"

    def __init__(
        self,
        path: str | Path,
        *,
        retention_hours: int = 24,
        cleanup_interval_seconds: int = 300,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.retention = timedelta(hours=retention_hours)
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self._last_cleanup_at = 0.0
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at)"
        )
        self._connection.commit()
        self._purge_if_due()

    def get_or_create(self, session_id: str, age_group: str | None = None) -> SessionState:
        self._purge_if_due()
        with self._lock:
            row = self._connection.execute(
                "SELECT state_json FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()

            if row is None:
                state = SessionState(session_id=session_id, age_group=age_group)
                self.save(state)
                return state

            try:
                state = SessionState.model_validate_json(row[0])
            except (ValidationError, ValueError) as exc:
                logger.warning("Invalid persisted session %s; resetting: %s", session_id, exc)
                state = SessionState(session_id=session_id, age_group=age_group)

            if age_group:
                state.age_group = age_group
            return state

    def save(self, state: SessionState) -> None:
        payload = state.model_dump_json()
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO sessions (session_id, state_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (state.session_id, payload, state.updated_at.isoformat()),
            )
            self._connection.commit()

    def clear(self, session_id: str) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            self._connection.commit()
            return cursor.rowcount > 0

    def purge_expired(self, older_than: datetime) -> int:
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM sessions WHERE updated_at < ?",
                (older_than.isoformat(),),
            )
            self._connection.commit()
            return max(cursor.rowcount, 0)

    def close(self) -> None:
        with self._lock:
            self._connection.close()
