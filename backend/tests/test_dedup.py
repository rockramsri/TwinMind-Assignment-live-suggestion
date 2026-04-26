from __future__ import annotations

from app.faiss_index import FaissMemoryIndex
from app.models import SessionState, SuggestionBatch, SuggestionCard
from app.suggestion_engine import is_duplicate_preview
from app.utils.text_normalize import preview_hash
from app.utils.time_utils import now_ms


class DummyEmbeddingService:
    def embed_text(self, text: str) -> list[float]:
        lowered = text.lower()
        if "budget" in lowered:
            return [1.0, 0.0]
        return [0.0, 1.0]


def test_dedup_detects_hash_and_embedding_similarity() -> None:
    current = now_ms()
    preview_index = FaissMemoryIndex()
    existing_card = SuggestionCard(
        card_id="card_1",
        type="info_to_surface",
        title="Budget note",
        preview="Discuss budget assumptions this quarter",
        why_now="Critical now",
        priority="high",
        topic_ids=["topic_budget"],
        evidence_chunk_ids=["chunk_1"],
        created_at_ms=current,
        preview_hash=preview_hash("Discuss budget assumptions this quarter"),
        preview_embedding=[1.0, 0.0],
    )
    preview_index.add(existing_card.card_id, existing_card.preview_embedding)

    session = SessionState(
        session_id="dedup_session",
        created_at_ms=current,
        faiss_indexes={
            "transcript_chunk_index": FaissMemoryIndex(),
            "topic_summary_index": FaissMemoryIndex(),
            "suggestion_preview_index": preview_index,
        },
        suggestion_batches=[
            SuggestionBatch(
                batch_id="batch_1",
                created_at_ms=current,
                window_start_ms=0,
                window_end_ms=30000,
                cards=[existing_card],
            )
        ],
    )

    assert is_duplicate_preview(
        preview_text="Discuss budget assumptions this quarter.",
        session=session,
        embedding_service=DummyEmbeddingService(),
    )
    assert not is_duplicate_preview(
        preview_text="Follow up with recruiting team on hiring metrics",
        session=session,
        embedding_service=DummyEmbeddingService(),
    )
