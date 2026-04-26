from __future__ import annotations

import json
from pathlib import Path

from app.adapters.memory.faiss_index import FaissMemoryIndex
from app.config import get_settings
from app.export import build_session_export
from app.models import SessionState


def _snapshot_path(session_id: str) -> Path:
    settings = get_settings()
    base = Path(settings.OPTIONAL_PERSISTENCE_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{session_id}.json"


def persist_session_snapshot(session: SessionState) -> None:
    settings = get_settings()
    if not settings.ENABLE_OPTIONAL_PERSISTENCE:
        return
    payload = build_session_export(session)
    payload["vector_index_metadata"] = {
        name: index.metadata() for name, index in session.faiss_indexes.items()
    }
    _snapshot_path(session.session_id).write_text(json.dumps(payload), encoding="utf-8")


def load_session_snapshot(session_id: str) -> SessionState | None:
    settings = get_settings()
    if not settings.ENABLE_OPTIONAL_PERSISTENCE:
        return None
    path = _snapshot_path(session_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Lightweight restore for optional mode: keep metadata and transcript history.
    # Vector indexes are rebuilt lazily for active runtime usage.
    state = SessionState(
        session_id=payload["session_id"],
        created_at_ms=int(payload["created_at_ms"]),
        faiss_indexes={
            "transcript_chunk_index": FaissMemoryIndex(),
            "topic_summary_index": FaissMemoryIndex(),
            "suggestion_preview_index": FaissMemoryIndex(),
        },
        session_config=payload.get("session_config", {}),
    )
    return state
