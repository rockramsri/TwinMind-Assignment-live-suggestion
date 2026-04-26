from __future__ import annotations

from collections.abc import Generator
from typing import Any

from app.domain.chat.engine import open_card_explanation, stream_card_chat_answer
from app.models import SessionState


class CardChatService:
    def open_card(
        self,
        *,
        session: SessionState,
        card_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        return open_card_explanation(session=session, card_id=card_id)

    def stream_chat(
        self,
        *,
        session: SessionState,
        card_id: str,
        user_message: str,
    ) -> Generator[str, None, None]:
        return stream_card_chat_answer(
            session=session,
            card_id=card_id,
            user_message=user_message,
        )

