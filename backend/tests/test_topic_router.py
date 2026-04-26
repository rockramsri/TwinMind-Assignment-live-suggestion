from __future__ import annotations

from app.models import SessionState, TopicCluster, TranscriptChunk
from app.adapters.memory.faiss_index import FaissMemoryIndex
from app.domain.suggestions.topic_router import route_topics
from app.utils.time_utils import now_ms


class DummyEmbeddingService:
    def embed_text(self, text: str) -> list[float]:
        lowered = text.lower()
        if "budget" in lowered:
            return [1.0, 0.0]
        if "hiring" in lowered:
            return [0.0, 1.0]
        return [0.5, 0.5]


def _base_session() -> SessionState:
    return SessionState(
        session_id="s1",
        created_at_ms=now_ms(),
        faiss_indexes={
            "transcript_chunk_index": FaissMemoryIndex(),
            "topic_summary_index": FaissMemoryIndex(),
            "suggestion_preview_index": FaissMemoryIndex(),
        },
    )


def test_single_topic_mode_when_recent_topic_score_high() -> None:
    session = _base_session()
    current = now_ms()
    session.topic_clusters["topic_budget"] = TopicCluster(
        topic_id="topic_budget",
        title="Budget",
        rolling_summary="Discussion about budget planning",
        centroid_embedding=[1.0, 0.0],
        summary_embedding=[1.0, 0.0],
        chunk_ids=[],
        last_touched_ms=current,
    )
    session.topic_clusters["topic_hiring"] = TopicCluster(
        topic_id="topic_hiring",
        title="Hiring",
        rolling_summary="Hiring pipeline and recruiting",
        centroid_embedding=[0.0, 1.0],
        summary_embedding=[0.0, 1.0],
        chunk_ids=[],
        last_touched_ms=current - 600_000,
    )
    session.faiss_indexes["topic_summary_index"].add("topic_budget", [1.0, 0.0])
    session.faiss_indexes["topic_summary_index"].add("topic_hiring", [0.0, 1.0])
    session.active_topic_id = "topic_budget"
    chunks = [
        TranscriptChunk(
            chunk_id="chunk_1",
            text="budget review and budget updates",
            start_ms=0,
            end_ms=5000,
            created_at_ms=current,
            is_low_signal=False,
        )
    ]

    decision = route_topics(
        session=session,
        window_chunks=chunks,
        embedding_service=DummyEmbeddingService(),
    )

    assert decision["mode"] == "single_topic"
    assert decision["selected_topics"][0]["topic_id"] == "topic_budget"


def test_fallback_mode_when_gap_is_too_small() -> None:
    session = _base_session()
    current = now_ms()
    session.topic_clusters["topic_a"] = TopicCluster(
        topic_id="topic_a",
        title="Topic A",
        rolling_summary="budget updates and planning",
        centroid_embedding=[0.65, 0.35],
        summary_embedding=[0.65, 0.35],
        chunk_ids=[],
        last_touched_ms=current,
    )
    session.topic_clusters["topic_b"] = TopicCluster(
        topic_id="topic_b",
        title="Topic B",
        rolling_summary="budget coordination with hiring",
        centroid_embedding=[0.55, 0.45],
        summary_embedding=[0.55, 0.45],
        chunk_ids=[],
        last_touched_ms=current,
    )
    session.faiss_indexes["topic_summary_index"].add("topic_a", [0.65, 0.35])
    session.faiss_indexes["topic_summary_index"].add("topic_b", [0.55, 0.45])
    session.active_topic_id = "topic_a"
    chunks = [
        TranscriptChunk(
            chunk_id="chunk_2",
            text="budget planning and hiring implications",
            start_ms=5000,
            end_ms=10000,
            created_at_ms=current,
            is_low_signal=False,
        )
    ]

    decision = route_topics(
        session=session,
        window_chunks=chunks,
        embedding_service=DummyEmbeddingService(),
    )

    assert decision["mode"] == "fallback_ranker"
    assert decision["selected_topics"]
