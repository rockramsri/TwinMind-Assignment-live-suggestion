from __future__ import annotations

from typing import Any

from app.models import SessionState


def build_session_export(session: SessionState) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "created_at_ms": session.created_at_ms,
        "transcript_chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "start_ms": chunk.start_ms,
                "end_ms": chunk.end_ms,
                "created_at_ms": chunk.created_at_ms,
                "is_low_signal": chunk.is_low_signal,
                "topic_tags": chunk.topic_tags,
            }
            for chunk in session.transcript_chunks
        ],
        "topic_clusters": [
            {
                "topic_id": topic.topic_id,
                "title": topic.title,
                "rolling_summary": topic.rolling_summary,
                "chunk_ids": topic.chunk_ids,
                "last_touched_ms": topic.last_touched_ms,
            }
            for topic in session.topic_clusters.values()
        ],
        "suggestion_batches": [
            {
                "batch_id": batch.batch_id,
                "created_at_ms": batch.created_at_ms,
                "window_start_ms": batch.window_start_ms,
                "window_end_ms": batch.window_end_ms,
                "route_decision": batch.route_decision,
                "cards": [
                    {
                        "card_id": card.card_id,
                        "type": card.type,
                        "title": card.title,
                        "preview": card.preview,
                        "why_now": card.why_now,
                        "priority": card.priority,
                        "topic_ids": card.topic_ids,
                        "evidence_chunk_ids": card.evidence_chunk_ids,
                        "created_at_ms": card.created_at_ms,
                    }
                    for card in batch.cards
                ],
            }
            for batch in session.suggestion_batches
        ],
        "unresolved_ledger": [
            {
                "ledger_item_id": item.ledger_item_id,
                "kind": item.kind,
                "title": item.title,
                "summary": item.summary,
                "topic_id": item.topic_id,
                "evidence_chunk_ids": item.evidence_chunk_ids,
                "status": item.status,
                "updated_at_ms": item.updated_at_ms,
            }
            for item in session.unresolved_ledger.values()
        ],
        "card_chat_threads": {
            card_id: [
                {
                    "role": msg.role,
                    "text": msg.text,
                    "created_at_ms": msg.created_at_ms,
                    "citations": msg.citations,
                }
                for msg in messages
            ]
            for card_id, messages in session.card_chat_threads.items()
        },
        "session_config": session.session_config,
    }
