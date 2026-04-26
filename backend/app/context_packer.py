from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.models import SessionState, SuggestionCard, TranscriptChunk
from app.utils.text_normalize import keyword_set
from app.utils.token_budget import clamp_text_to_token_cap


def _window_entries(window_chunks: list[TranscriptChunk]) -> list[dict[str, Any]]:
    entries = []
    for chunk in window_chunks:
        if chunk.is_low_signal and not chunk.text.strip():
            continue
        entries.append(
            {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "start_ms": chunk.start_ms,
                "end_ms": chunk.end_ms,
            }
        )
    return entries


def _topic_context(
    session: SessionState,
    selected_topic_ids: list[str],
) -> list[dict[str, Any]]:
    context = []
    for topic_id in selected_topic_ids:
        cluster = session.topic_clusters.get(topic_id)
        if not cluster:
            continue
        context.append(
            {
                "topic_id": cluster.topic_id,
                "title": cluster.title,
                "summary": cluster.rolling_summary,
                "chunk_ids": cluster.chunk_ids[-8:],
                "last_touched_ms": cluster.last_touched_ms,
            }
        )
    return context


def _retrieved_topic_chunks(
    session: SessionState,
    *,
    selected_topic_ids: list[str],
) -> list[dict[str, Any]]:
    settings = get_settings()
    chunks_by_id = {chunk.chunk_id: chunk for chunk in session.transcript_chunks}
    seen_chunk_ids: set[str] = set()
    retrieved: list[dict[str, Any]] = []

    for topic_id in selected_topic_ids:
        cluster = session.topic_clusters.get(topic_id)
        if not cluster:
            continue
        selected_ids = cluster.chunk_ids[-settings.RETRIEVE_CHUNKS_PER_TOPIC :]
        for chunk_id in selected_ids:
            if chunk_id in seen_chunk_ids:
                continue
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                continue
            seen_chunk_ids.add(chunk_id)
            retrieved.append(
                {
                    "topic_id": topic_id,
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "start_ms": chunk.start_ms,
                    "end_ms": chunk.end_ms,
                }
            )
    return retrieved


def _ledger_context(
    session: SessionState,
    *,
    window_text: str,
    selected_topic_ids: list[str],
) -> list[dict[str, Any]]:
    selected_topic_set = set(selected_topic_ids)
    window_tokens = keyword_set(window_text)
    scored = []
    for ledger in session.unresolved_ledger.values():
        if ledger.status != "open":
            continue
        score = 0.0
        if ledger.topic_id in selected_topic_set:
            score += 1.0
        overlap = keyword_set(ledger.summary).intersection(window_tokens)
        score += min(1.0, len(overlap) * 0.2)
        scored.append((score, ledger))
    scored.sort(key=lambda item: item[0], reverse=True)

    return [
        {
            "ledger_item_id": ledger.ledger_item_id,
            "kind": ledger.kind,
            "title": ledger.title,
            "summary": ledger.summary,
            "topic_id": ledger.topic_id,
            "evidence_chunk_ids": ledger.evidence_chunk_ids,
        }
        for _, ledger in scored[:10]
    ]


def _recent_card_history(session: SessionState) -> list[dict[str, Any]]:
    history = []
    for batch in session.suggestion_batches[-2:]:
        for card in batch.cards:
            history.append(
                {
                    "card_id": card.card_id,
                    "type": card.type,
                    "title": card.title,
                    "preview": card.preview,
                    "topic_ids": card.topic_ids,
                }
            )
    return history


def _trim_payload_for_cap(payload: dict[str, Any], token_cap: int) -> dict[str, Any]:
    # Keep structure stable but trim long text fields in priority order.
    # Approx budgets: window 55%, topic 25%, ledger 15%, history 5%.
    window_cap = int(token_cap * 0.55)
    topic_cap = int(token_cap * 0.25)
    ledger_cap = int(token_cap * 0.15)
    history_cap = token_cap - window_cap - topic_cap - ledger_cap

    for entry in payload.get("current_window_chunks", []):
        entry["text"] = clamp_text_to_token_cap(entry["text"], max(40, window_cap // 6))
    for topic in payload.get("topic_context", []):
        topic["summary"] = clamp_text_to_token_cap(topic["summary"], max(40, topic_cap // 4))
    for item in payload.get("retrieved_topic_chunks", []):
        item["text"] = clamp_text_to_token_cap(item["text"], max(25, topic_cap // 6))
    for item in payload.get("unresolved_ledger_context", []):
        item["summary"] = clamp_text_to_token_cap(item["summary"], max(30, ledger_cap // 6))
    for item in payload.get("recent_card_history", []):
        item["preview"] = clamp_text_to_token_cap(item["preview"], max(16, history_cap // 6))
    return payload


def build_live_prompt_payload(
    *,
    session: SessionState,
    window_start_ms: int,
    window_end_ms: int,
    window_chunks: list[TranscriptChunk],
    route_decision: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    selected_topic_ids = [
        str(item.get("topic_id"))
        for item in route_decision.get("selected_topics", [])
        if item.get("topic_id")
    ]
    entries = _window_entries(window_chunks)
    window_text = "\n".join(entry["text"] for entry in entries)
    payload = {
        "window_start_ms": window_start_ms,
        "window_end_ms": window_end_ms,
        "route_decision": route_decision,
        "current_window_chunks": entries,
        "topic_context": _topic_context(session, selected_topic_ids),
        "retrieved_topic_chunks": _retrieved_topic_chunks(
            session,
            selected_topic_ids=selected_topic_ids,
        ),
        "unresolved_ledger_context": _ledger_context(
            session,
            window_text=window_text,
            selected_topic_ids=selected_topic_ids,
        ),
        "recent_card_history": _recent_card_history(session),
        "requirements": {
            "exact_cards": 3,
            "citation_required": True,
            "dedupe_against_recent": True,
        },
    }
    return _trim_payload_for_cap(payload, settings.LIVE_CONTEXT_TOKEN_CAP)


def build_card_chat_payload(
    *,
    session: SessionState,
    card: SuggestionCard,
    latest_user_message: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    chunks_by_id = {chunk.chunk_id: chunk for chunk in session.transcript_chunks}
    evidence_chunks = [
        {
            "chunk_id": chunk_id,
            "text": chunks_by_id[chunk_id].text,
            "start_ms": chunks_by_id[chunk_id].start_ms,
            "end_ms": chunks_by_id[chunk_id].end_ms,
        }
        for chunk_id in card.evidence_chunk_ids
        if chunk_id in chunks_by_id
    ]
    related_topics = _topic_context(session, card.topic_ids)
    payload = {
        "card": {
            "card_id": card.card_id,
            "type": card.type,
            "title": card.title,
            "preview": card.preview,
            "why_now": card.why_now,
            "priority": card.priority,
            "topic_ids": card.topic_ids,
            "evidence_chunk_ids": card.evidence_chunk_ids,
        },
        "evidence_chunks": evidence_chunks,
        "related_topics": related_topics,
        "latest_user_message": latest_user_message,
    }
    return _trim_payload_for_cap(payload, settings.CHAT_CONTEXT_TOKEN_CAP)
