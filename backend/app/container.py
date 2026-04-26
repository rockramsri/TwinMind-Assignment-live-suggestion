from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.adapters.in_memory.session_repository import InMemorySessionRepository
from app.adapters.runtime import SuggestionGeneratorAdapter, TopicRouterAdapter
from app.domain.chat.service import CardChatService
from app.domain.memory.service import LiveContextPackerService
from app.domain.sessions.service import SessionService
from app.domain.suggestions.service import SuggestionService
from app.domain.transcript.service import TranscriptService
from app.adapters.memory.embeddings import EmbeddingService


@dataclass(frozen=True)
class AppContainer:
    embedding_service: EmbeddingService
    session_service: SessionService
    transcript_service: TranscriptService
    suggestion_service: SuggestionService
    card_chat_service: CardChatService


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    embedding_service = EmbeddingService()
    session_repository = InMemorySessionRepository()
    session_service = SessionService(repository=session_repository)
    transcript_service = TranscriptService(embedding_service=embedding_service)
    suggestion_service = SuggestionService(
        topic_router=TopicRouterAdapter(embedding_service=embedding_service),
        context_packer=LiveContextPackerService(),
        generator=SuggestionGeneratorAdapter(embedding_service=embedding_service),
    )
    card_chat_service = CardChatService()
    return AppContainer(
        embedding_service=embedding_service,
        session_service=session_service,
        transcript_service=transcript_service,
        suggestion_service=suggestion_service,
        card_chat_service=card_chat_service,
    )

