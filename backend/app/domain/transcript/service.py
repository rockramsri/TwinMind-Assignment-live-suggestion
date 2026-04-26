from __future__ import annotations

from app.domain.transcript.audio import append_transcript_chunk, build_rolling_window
from app.models import SessionState, TranscriptChunk

from .ports import EmbeddingPort


class TranscriptService:
    def __init__(self, embedding_service: EmbeddingPort) -> None:
        self._embedding_service = embedding_service

    def append_chunk(
        self,
        session: SessionState,
        *,
        text: str,
        start_ms: int,
        end_ms: int,
    ) -> TranscriptChunk:
        return append_transcript_chunk(
            session,
            text=text,
            start_ms=start_ms,
            end_ms=end_ms,
            embedding_service=self._embedding_service,
        )

    def rolling_window(
        self,
        session: SessionState,
        *,
        window_seconds: int,
    ) -> tuple[int, int, list[TranscriptChunk]]:
        return build_rolling_window(session=session, window_seconds=window_seconds)

