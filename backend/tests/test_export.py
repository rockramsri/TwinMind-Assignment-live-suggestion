from __future__ import annotations

from app.export import build_session_export
from app.adapters.memory.faiss_index import FaissMemoryIndex
from app.models import (
    ChatMessage,
    LedgerItem,
    SessionState,
    SuggestionBatch,
    SuggestionCard,
    TopicCluster,
    TranscriptChunk,
)
from app.utils.time_utils import now_ms


def test_export_contains_expected_top_level_sections() -> None:
    current = now_ms()
    session = SessionState(
        session_id="export_session",
        created_at_ms=current,
        faiss_indexes={
            "transcript_chunk_index": FaissMemoryIndex(),
            "topic_summary_index": FaissMemoryIndex(),
            "suggestion_preview_index": FaissMemoryIndex(),
        },
    )
    session.transcript_chunks.append(
        TranscriptChunk(
            chunk_id="chunk_1",
            text="Discussed launch timeline.",
            start_ms=0,
            end_ms=5000,
            created_at_ms=current,
            is_low_signal=False,
        )
    )
    session.topic_clusters["topic_launch"] = TopicCluster(
        topic_id="topic_launch",
        title="Launch",
        rolling_summary="Launch timeline planning",
        centroid_embedding=[],
        summary_embedding=[],
        chunk_ids=["chunk_1"],
        last_touched_ms=current,
    )
    card = SuggestionCard(
        card_id="card_1",
        type="decision_nudge",
        title="Confirm launch date",
        preview="Need decision on launch milestone",
        why_now="Timeline risk raised",
        priority="high",
        topic_ids=["topic_launch"],
        evidence_chunk_ids=["chunk_1"],
        created_at_ms=current,
    )
    session.suggestion_batches.append(
        SuggestionBatch(
            batch_id="batch_1",
            created_at_ms=current,
            window_start_ms=0,
            window_end_ms=30000,
            cards=[card],
            route_decision={"mode": "single_topic"},
        )
    )
    session.unresolved_ledger["ledger_1"] = LedgerItem(
        ledger_item_id="ledger_1",
        kind="pending_decision",
        title="Pick launch date",
        summary="Decision still pending",
        topic_id="topic_launch",
        evidence_chunk_ids=["chunk_1"],
        status="open",
        updated_at_ms=current,
    )
    session.card_chat_threads["card_1"] = [
        ChatMessage(role="assistant", text="Initial explanation", created_at_ms=current)
    ]

    exported = build_session_export(session)

    assert exported["session_id"] == "export_session"
    assert exported["transcript_chunks"][0]["chunk_id"] == "chunk_1"
    assert exported["topic_clusters"][0]["topic_id"] == "topic_launch"
    assert exported["suggestion_batches"][0]["cards"][0]["card_id"] == "card_1"
    assert exported["unresolved_ledger"][0]["ledger_item_id"] == "ledger_1"
    assert exported["card_chat_threads"]["card_1"][0]["role"] == "assistant"
    assert "session_config" in exported
