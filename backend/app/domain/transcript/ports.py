from __future__ import annotations

from typing import Protocol

from app.models import SessionState, TranscriptChunk


class EmbeddingPort(Protocol):
    def embed_text(self, text: str) -> list[float]:
        ...


class TranscriptServicePort(Protocol):
    def append_chunk(
        self,
        session: SessionState,
        *,
        text: str,
        start_ms: int,
        end_ms: int,
    ) -> TranscriptChunk:
        ...

    def rolling_window(
        self,
        session: SessionState,
        *,
        window_seconds: int,
    ) -> tuple[int, int, list[TranscriptChunk]]:
        ...

