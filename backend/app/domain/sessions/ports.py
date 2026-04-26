from __future__ import annotations

from typing import Protocol

from app.models import SessionState


class SessionRepositoryPort(Protocol):
    def create(self, groq_api_key: str | None = None) -> SessionState:
        ...

    def get(self, session_id: str) -> SessionState | None:
        ...

    def set_key(self, session_id: str, groq_api_key: str | None) -> SessionState | None:
        ...

    def persist(self, session: SessionState) -> None:
        ...

