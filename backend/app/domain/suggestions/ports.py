from __future__ import annotations

from typing import Any, Protocol

from app.models import SessionState, SuggestionBatch, TranscriptChunk


class TopicRouterPort(Protocol):
    def route(
        self,
        *,
        session: SessionState,
        window_chunks: list[TranscriptChunk],
    ) -> dict[str, Any]:
        ...


class LiveContextPackerPort(Protocol):
    def build(
        self,
        *,
        session: SessionState,
        window_start_ms: int,
        window_end_ms: int,
        window_chunks: list[TranscriptChunk],
        route_decision: dict[str, Any],
    ) -> dict[str, Any]:
        ...


class SuggestionGeneratorPort(Protocol):
    def generate(
        self,
        *,
        session: SessionState,
        context_payload: dict[str, Any],
        route_decision: dict[str, Any],
        window_start_ms: int,
        window_end_ms: int,
        window_chunk_ids: list[str],
    ) -> tuple[SuggestionBatch, list[dict[str, Any]]]:
        ...

