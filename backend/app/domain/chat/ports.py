from __future__ import annotations

from collections.abc import Generator
from typing import Any, Protocol

from app.models import SessionState


class CardChatServicePort(Protocol):
    def open_card(
        self,
        *,
        session: SessionState,
        card_id: str,
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        ...

    def stream_chat(
        self,
        *,
        session: SessionState,
        card_id: str,
        user_message: str,
    ) -> Generator[str, None, None]:
        ...

