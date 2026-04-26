from __future__ import annotations

from typing import Any

from app.domain.memory.context_packer import build_card_chat_payload, build_live_prompt_payload
from app.models import SessionState, SuggestionCard, TranscriptChunk


class LiveContextPackerService:
    def build(
        self,
        *,
        session: SessionState,
        window_start_ms: int,
        window_end_ms: int,
        window_chunks: list[TranscriptChunk],
        route_decision: dict[str, Any],
    ) -> dict[str, Any]:
        return build_live_prompt_payload(
            session=session,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
            window_chunks=window_chunks,
            route_decision=route_decision,
        )


class CardContextPackerService:
    def build(
        self,
        *,
        session: SessionState,
        card: SuggestionCard,
        latest_user_message: str | None = None,
    ) -> dict[str, Any]:
        return build_card_chat_payload(
            session=session,
            card=card,
            latest_user_message=latest_user_message,
        )

