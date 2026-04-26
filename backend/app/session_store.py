from __future__ import annotations

import threading
import uuid

from app.faiss_index import FaissMemoryIndex
from app.models import SessionState
from app.utils.time_utils import now_ms

_sessions: dict[str, SessionState] = {}
_lock = threading.Lock()


def create_session(groq_api_key: str | None = None) -> SessionState:
    session_id = str(uuid.uuid4())
    state = SessionState(
        session_id=session_id,
        created_at_ms=now_ms(),
        user_groq_api_key_in_memory=groq_api_key or None,
        faiss_indexes={
            "transcript_chunk_index": FaissMemoryIndex(),
            "topic_summary_index": FaissMemoryIndex(),
            "suggestion_preview_index": FaissMemoryIndex(),
        },
    )
    with _lock:
        _sessions[session_id] = state
    return state


def get_session(session_id: str) -> SessionState | None:
    with _lock:
        return _sessions.get(session_id)


def set_session_key(session_id: str, groq_api_key: str | None) -> SessionState | None:
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return None
        session.user_groq_api_key_in_memory = (groq_api_key or "").strip() or None
        return session


def clear_all_sessions() -> None:
    with _lock:
        _sessions.clear()
