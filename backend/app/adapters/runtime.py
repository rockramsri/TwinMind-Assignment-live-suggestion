from __future__ import annotations

from typing import Any

from app.domain.suggestions.engine import generate_suggestion_batch
from app.domain.suggestions.topic_router import route_topics
from app.models import SessionState, SuggestionBatch, TranscriptChunk


class TopicRouterAdapter:
    def __init__(self, embedding_service: Any) -> None:
        self._embedding_service = embedding_service

    def route(
        self,
        *,
        session: SessionState,
        window_chunks: list[TranscriptChunk],
    ) -> dict[str, Any]:
        return route_topics(
            session=session,
            window_chunks=window_chunks,
            embedding_service=self._embedding_service,
        )


class SuggestionGeneratorAdapter:
    def __init__(self, embedding_service: Any) -> None:
        self._embedding_service = embedding_service

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
        return generate_suggestion_batch(
            session=session,
            context_payload=context_payload,
            route_decision=route_decision,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
            window_chunk_ids=window_chunk_ids,
            embedding_service=self._embedding_service,
        )

