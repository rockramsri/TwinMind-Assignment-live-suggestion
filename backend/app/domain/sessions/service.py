from __future__ import annotations

from app.models import SessionState

from .ports import SessionRepositoryPort


class SessionService:
    def __init__(self, repository: SessionRepositoryPort) -> None:
        self._repository = repository

    def create(self, groq_api_key: str | None = None) -> SessionState:
        return self._repository.create(groq_api_key=groq_api_key)

    def get(self, session_id: str) -> SessionState | None:
        return self._repository.get(session_id)

    def set_key(self, session_id: str, groq_api_key: str | None) -> SessionState | None:
        return self._repository.set_key(session_id, groq_api_key)

    def persist(self, session: SessionState) -> None:
        self._repository.persist(session)

