from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Protocol

from pydantic import ValidationError

from .schemas import SessionState

logger = logging.getLogger(__name__)


class SessionStore(Protocol):
    kind: str

    def get_or_create(self, session_id: str, age_group: str | None = None) -> SessionState: ...

    def save(self, state: SessionState) -> None: ...

    def clear(self, session_id: str) -> bool: ...


class MemorySessionStore:
    kind = "memory"

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = RLock()

    def get_or_create(self, session_id: str, age_group: str | None = None) -> SessionState:
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


class SQLiteSessionStore:
    """Persist anonymous conversation state without collecting identity fields.

    The database stores one JSON document per random session id. SQLite is used so
    the competition prototype survives backend restarts while remaining easy to
    inspect, reset and run without external services.
    """

    kind = "sqlite"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
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
        self._connection.commit()

    def get_or_create(self, session_id: str, age_group: str | None = None) -> SessionState:
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

    def close(self) -> None:
        with self._lock:
            self._connection.close()
