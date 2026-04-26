from __future__ import annotations

from app.adapters.in_memory.session_store import create_session, get_session, persist_session, set_session_key
from app.models import SessionState


class InMemorySessionRepository:
    def create(self, groq_api_key: str | None = None) -> SessionState:
        return create_session(groq_api_key=groq_api_key)

    def get(self, session_id: str) -> SessionState | None:
        return get_session(session_id)

    def set_key(self, session_id: str, groq_api_key: str | None) -> SessionState | None:
        return set_session_key(session_id, groq_api_key)

    def persist(self, session: SessionState) -> None:
        persist_session(session)

