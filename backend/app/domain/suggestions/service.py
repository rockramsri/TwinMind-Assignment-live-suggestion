from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import SessionState, TranscriptChunk

from .ports import LiveContextPackerPort, SuggestionGeneratorPort, TopicRouterPort


@dataclass(frozen=True)
class SuggestionTickResult:
    window_start_ms: int
    window_end_ms: int
    window_chunks: list[TranscriptChunk]
    route_decision: dict[str, Any]
    cards: list[Any]
    batch: Any
    ledger_updates: list[dict[str, Any]]


class SuggestionService:
    def __init__(
        self,
        *,
        topic_router: TopicRouterPort,
        context_packer: LiveContextPackerPort,
        generator: SuggestionGeneratorPort,
    ) -> None:
        self._topic_router = topic_router
        self._context_packer = context_packer
        self._generator = generator

    def run_tick(
        self,
        *,
        session: SessionState,
        window_start_ms: int,
        window_end_ms: int,
        window_chunks: list[TranscriptChunk],
    ) -> SuggestionTickResult:
        route_decision = self._topic_router.route(
            session=session,
            window_chunks=window_chunks,
        )
        context_payload = self._context_packer.build(
            session=session,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
            window_chunks=window_chunks,
            route_decision=route_decision,
        )
        batch, ledger_updates = self._generator.generate(
            session=session,
            context_payload=context_payload,
            route_decision=route_decision,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
            window_chunk_ids=[chunk.chunk_id for chunk in window_chunks],
        )
        return SuggestionTickResult(
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
            window_chunks=window_chunks,
            route_decision=route_decision,
            cards=batch.cards[:3],
            batch=batch,
            ledger_updates=ledger_updates,
        )

