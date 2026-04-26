from __future__ import annotations

import uuid

from app.embeddings import EmbeddingService
from app.models import SessionState, TranscriptChunk
from app.utils.time_utils import now_ms


def is_low_signal_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    tokens = [token for token in stripped.split() if token.isalpha()]
    if len(tokens) < 3:
        return True
    unique_ratio = len(set(tokens)) / max(1, len(tokens))
    return unique_ratio < 0.35


def append_transcript_chunk(
    session: SessionState,
    *,
    text: str,
    start_ms: int,
    end_ms: int,
    embedding_service: EmbeddingService,
) -> TranscriptChunk:
    chunk_id = f"chunk_{uuid.uuid4().hex[:10]}"
    low_signal = is_low_signal_text(text)
    embedding = embedding_service.embed_text(text) if not low_signal else []
    chunk = TranscriptChunk(
        chunk_id=chunk_id,
        text=text,
        start_ms=start_ms,
        end_ms=end_ms,
        created_at_ms=now_ms(),
        embedding=embedding,
        is_low_signal=low_signal,
    )
    session.transcript_chunks.append(chunk)

    if embedding:
        session.faiss_indexes["transcript_chunk_index"].add(chunk_id, embedding)

    return chunk


def build_rolling_window(
    session: SessionState,
    *,
    window_seconds: int,
) -> tuple[int, int, list[TranscriptChunk]]:
    if not session.transcript_chunks:
        return 0, 0, []
    window_end_ms = max(chunk.end_ms for chunk in session.transcript_chunks)
    window_start_ms = max(0, window_end_ms - (window_seconds * 1000))
    window_chunks = [
        chunk
        for chunk in session.transcript_chunks
        if chunk.end_ms >= window_start_ms and chunk.start_ms <= window_end_ms
    ]
    return window_start_ms, window_end_ms, window_chunks
