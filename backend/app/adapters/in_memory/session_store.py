from __future__ import annotations

import threading
import uuid

from app.adapters.in_memory.persistence import load_session_snapshot, persist_session_snapshot
from app.adapters.memory.faiss_index import FaissMemoryIndex
from app.config import get_settings
from app.models import SessionState
from app.utils.time_utils import now_ms

_sessions: dict[str, SessionState] = {}
_lock = threading.Lock()


def create_session(groq_api_key: str | None = None) -> SessionState:
    settings = get_settings()
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
        session_config={
            "live_window_seconds": settings.LIVE_WINDOW_SECONDS,
            "live_context_token_cap": settings.LIVE_CONTEXT_TOKEN_CAP,
            "chat_context_token_cap": settings.CHAT_CONTEXT_TOKEN_CAP,
            "tick_cadence_seconds": settings.UI_REFRESH_SECONDS,
            "live_suggestions_prompt": None,
            "card_detail_prompt": None,
            "card_chat_prompt": None,
        },
    )
    with _lock:
        _sessions[session_id] = state
    persist_session_snapshot(state)
    return state


def get_session(session_id: str) -> SessionState | None:
    with _lock:
        in_memory = _sessions.get(session_id)
        if in_memory is not None:
            return in_memory
    restored = load_session_snapshot(session_id)
    if restored is not None:
        with _lock:
            _sessions[session_id] = restored
    return restored


def set_session_key(session_id: str, groq_api_key: str | None) -> SessionState | None:
    with _lock:
        session = _sessions.get(session_id)
        if session is None:
            return None
        session.user_groq_api_key_in_memory = (groq_api_key or "").strip() or None
        persist_session_snapshot(session)
        return session


def persist_session(session: SessionState) -> None:
    persist_session_snapshot(session)


def clear_all_sessions() -> None:
    with _lock:
        _sessions.clear()
