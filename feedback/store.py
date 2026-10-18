"""Append-only session-linked feedback store (JSONL).

Session linkage is enforced: events referencing an unknown session are
QUARANTINED, never silently dropped. They can be adopted later once the
session is registered.
"""

from __future__ import annotations

import json
from pathlib import Path

from .capture import FeedbackEvent


class FeedbackStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._sessions: dict[str, str] = {}          # session_id -> user_id
        self._quarantine: dict[str, FeedbackEvent] = {}  # event_id -> event
        self._sessions_path = self.path.with_suffix(self.path.suffix + ".sessions")
        # Quarantined (orphan) events are persisted too, so a restart cannot drop them.
        self._quarantine_path = self.path.with_suffix(self.path.suffix + ".quarantine")
        if self._sessions_path.exists():
            self._sessions = json.loads(self._sessions_path.read_text())
        if self._quarantine_path.exists():
            for line in self._quarantine_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    e = FeedbackEvent.from_dict(json.loads(line))
                    self._quarantine[e.event_id] = e

    def _save_quarantine(self) -> None:
        self._quarantine_path.parent.mkdir(parents=True, exist_ok=True)
        self._quarantine_path.write_text(
            "".join(json.dumps(e.to_dict()) + "\n" for e in self._quarantine.values()),
            encoding="utf-8")

    def _save_sessions(self) -> None:
        self._sessions_path.write_text(json.dumps(self._sessions))

    def register_session(self, session_id: str, user_id: str) -> None:
        self._sessions[session_id] = user_id
        self._save_sessions()

    def known_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    def append(self, event: FeedbackEvent) -> str:
        """Store an event. Returns 'stored' or 'quarantined'."""
        if not self.known_session(event.session_id):
            self._quarantine[event.event_id] = event
            self._save_quarantine()
            return "quarantined"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict()) + "\n")
        return "stored"

    def quarantined(self) -> list[FeedbackEvent]:
        return list(self._quarantine.values())

    def adopt(self, event_id: str, session_id: str) -> FeedbackEvent:
        """Link a quarantined event to a now-known session and store it."""
        if event_id not in self._quarantine:
            raise KeyError(f"no quarantined event {event_id!r}")
        if not self.known_session(session_id):
            raise ValueError(f"session {session_id!r} is not registered")
        event = self._quarantine[event_id]
        event.session_id = session_id
        if self.append(event) != "stored":  # explicit check: asserts vanish under python -O
            raise RuntimeError(f"event {event_id!r} could not be stored")
        del self._quarantine[event_id]
        self._save_quarantine()
        return event

    def _iter_stored(self):
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield FeedbackEvent.from_dict(json.loads(line))

    def query(self, session_id: str | None = None,
              user_id: str | None = None,
              since: float | None = None,
              until: float | None = None,
              event_type: str | None = None) -> list[FeedbackEvent]:
        out = []
        for e in self._iter_stored():
            if session_id is not None and e.session_id != session_id:
                continue
            if user_id is not None and self._sessions.get(e.session_id) != user_id:
                continue
            if since is not None and e.timestamp < since:
                continue
            if until is not None and e.timestamp > until:
                continue
            if event_type is not None and e.event_type != event_type:
                continue
            out.append(e)
        return out

    def count(self) -> int:
        return sum(1 for _ in self._iter_stored())
