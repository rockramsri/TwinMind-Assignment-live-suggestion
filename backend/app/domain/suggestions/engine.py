from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from openai import OpenAI

from app.adapters.memory.embeddings import EmbeddingService
from app.config import get_settings
from app.domain.transcript.transcribe import resolve_groq_api_key
from app.models import LedgerItem, SessionState, SuggestionBatch, SuggestionCard, TopicCluster
from app.prompts import LIVE_SUGGESTIONS_JSON_SCHEMA, live_suggestion_messages
from app.utils.text_normalize import keyword_set, normalize_preview, preview_hash
from app.utils.time_utils import now_ms

logger = logging.getLogger(__name__)

CARD_TYPES = [
    "question_to_ask",
    "info_to_surface",
    "verify_claim",
    "decision_nudge",
    "stakeholder_followup",
]


def _has_stakeholder_signal(context_payload: dict[str, Any]) -> bool:
    window_text = " ".join(
        str(item.get("text", ""))
        for item in context_payload.get("current_window_chunks", [])
    ).lower()
    if not window_text.strip():
        return False
    stakeholder_keywords = [
        "stakeholder",
        "customer",
        "client",
        "buyer",
        "user",
        "manager",
        "team",
        "vendor",
        "partner",
        "finance",
        "legal",
        "ops",
        "operations",
    ]
    return any(keyword in window_text for keyword in stakeholder_keywords)


def has_type_diversity(cards: list[dict[str, Any]]) -> bool:
    return len({card.get("type") for card in cards}) == len(cards)


def is_duplicate_preview(
    *,
    preview_text: str,
    session: SessionState,
    embedding_service: EmbeddingService,
    threshold: float = 0.86,
) -> bool:
    normalized = normalize_preview(preview_text)
    if not normalized:
        return True
    digest = preview_hash(normalized)

    recent_hashes = {
        card.preview_hash
        for batch in session.suggestion_batches[-6:]
        for card in batch.cards
        if card.preview_hash
    }
    if digest in recent_hashes:
        return True

    vector = embedding_service.embed_text(normalized)
    nearest = session.faiss_indexes["suggestion_preview_index"].search(vector, top_k=3)
    if nearest and nearest[0][1] > threshold:
        return True
    return False


def _is_already_covered_by_window(
    *,
    card: dict[str, Any],
    context_payload: dict[str, Any],
) -> bool:
    window_text = " ".join(
        str(item.get("text", ""))
        for item in context_payload.get("current_window_chunks", [])
    ).lower()
    if not window_text.strip():
        return False

    intent_text = f"{card.get('title', '')} {card.get('preview', '')}".strip()
    intent_tokens = keyword_set(intent_text)
    window_tokens = keyword_set(window_text)
    if not intent_tokens or not window_tokens:
        return False

    overlap = len(intent_tokens.intersection(window_tokens)) / max(1, len(intent_tokens))
    recent_card_history = context_payload.get("recent_card_history", [])
    most_similar_recent = 0.0
    for recent_card in recent_card_history:
        recent_tokens = keyword_set(
            f"{recent_card.get('title', '')} {recent_card.get('preview', '')}"
        )
        if not recent_tokens:
            continue
        shared = len(intent_tokens.intersection(recent_tokens))
        most_similar_recent = max(
            most_similar_recent,
            shared / max(1, min(len(intent_tokens), len(recent_tokens))),
        )

    completion_signals = [
        "already asked",
        "already answered",
        "we asked",
        "i asked",
        "we covered",
        "that's covered",
        "that is covered",
        "resolved",
        "decided",
        "confirmed",
        "thank you",
        "thanks",
    ]
    has_completion_signal = any(signal in window_text for signal in completion_signals)
    return most_similar_recent >= 0.7 or (
        most_similar_recent >= 0.45 and overlap >= 0.35 and has_completion_signal
    )


def _request_live_suggestions(
    *,
    api_key: str,
    context_payload: dict[str, Any],
    prompt_override: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    client = OpenAI(api_key=api_key, base_url=settings.GROQ_BASE_URL)
    completion = client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=0.25,
        response_format={
            "type": "json_schema",
            "json_schema": LIVE_SUGGESTIONS_JSON_SCHEMA,
        },
        messages=live_suggestion_messages(context_payload, prompt_override=prompt_override),
    )
    raw = completion.choices[0].message.content or "{}"
    return json.loads(raw)


def _fallback_cards(
    *,
    context_payload: dict[str, Any],
    now: int,
) -> dict[str, Any]:
    chunks = context_payload.get("current_window_chunks", [])
    ledger_context = context_payload.get("unresolved_ledger_context", [])
    ledger_evidence_ids = [
        evidence_id
        for item in ledger_context
        for evidence_id in item.get("evidence_chunk_ids", [])
    ]
    evidence_ids = [chunk["chunk_id"] for chunk in chunks[:2]] or ledger_evidence_ids[:2]
    lead_text = chunks[0]["text"] if chunks else "The last window was thin or mostly silent."
    topic_context = context_payload.get("topic_context", [])
    topic_id = topic_context[0]["topic_id"] if topic_context else "topic_current"
    cards = []
    for idx, card_type in enumerate(CARD_TYPES[:3], start=1):
        cards.append(
            {
                "card_id": f"card_{uuid.uuid4().hex[:8]}",
                "type": card_type,
                "title": f"Live follow-up {idx}",
                "preview": lead_text[:160] or "Ask for clarification on the latest point.",
                "why_now": "Recent transcript indicates this should be addressed immediately.",
                "priority": "medium",
                "topic_ids": [topic_id],
                "evidence_chunk_ids": evidence_ids,
            }
        )
    return {"cards": cards, "topic_updates": [], "ledger_updates": []}


def _materialize_cards(
    *,
    session: SessionState,
    payload_cards: list[dict[str, Any]],
    window_chunk_ids: list[str],
) -> list[SuggestionCard]:
    cards: list[SuggestionCard] = []
    ts = now_ms()
    valid_chunk_ids = {chunk.chunk_id for chunk in session.transcript_chunks}
    for raw in payload_cards:
        evidence = raw.get("evidence_chunk_ids") or window_chunk_ids[:2]
        evidence = [str(item) for item in evidence if str(item).strip() and str(item) in valid_chunk_ids]
        if not evidence:
            evidence = window_chunk_ids[:2]
        topic_ids = raw.get("topic_ids") or ["topic_current"]
        card = SuggestionCard(
            card_id=f"card_{uuid.uuid4().hex[:8]}",
            type=raw.get("type", "question_to_ask"),
            title=(raw.get("title", "") or "Untitled card")[:80],
            preview=(raw.get("preview", "") or "No preview")[:180],
            why_now=(raw.get("why_now", "") or "Relevant to current discussion.")[:180],
            priority=raw.get("priority", "medium"),
            topic_ids=[str(item) for item in topic_ids],
            evidence_chunk_ids=evidence,
            created_at_ms=ts,
        )
        cards.append(card)
    return cards


def _apply_topic_updates(
    *,
    session: SessionState,
    cards: list[SuggestionCard],
    topic_updates: list[dict[str, Any]],
    embedding_service: EmbeddingService,
) -> None:
    now = now_ms()
    updates_by_id = {item.get("topic_id"): item for item in topic_updates if item.get("topic_id")}
    for card in cards:
        for topic_id in card.topic_ids:
            update = updates_by_id.get(topic_id)
            title = update.get("title") if update else topic_id.replace("_", " ").title()
            summary = (
                update.get("summary")
                if update
                else f"Latest discussion related to: {card.title}. {card.preview}"
            )
            existing = session.topic_clusters.get(topic_id)
            summary_embedding = embedding_service.embed_text(summary)
            if existing is None:
                existing = TopicCluster(
                    topic_id=topic_id,
                    title=title,
                    rolling_summary=summary,
                    summary_embedding=summary_embedding,
                    centroid_embedding=summary_embedding,
                    chunk_ids=[],
                    last_touched_ms=now,
                )
                session.topic_clusters[topic_id] = existing
            else:
                existing.title = title
                existing.rolling_summary = summary
                existing.summary_embedding = summary_embedding
                if existing.centroid_embedding and summary_embedding:
                    existing.centroid_embedding = [
                        (old + new) / 2.0
                        for old, new in zip(existing.centroid_embedding, summary_embedding)
                    ]
                elif summary_embedding:
                    existing.centroid_embedding = summary_embedding
                existing.last_touched_ms = now

            for chunk_id in card.evidence_chunk_ids:
                if chunk_id not in existing.chunk_ids:
                    existing.chunk_ids.append(chunk_id)
            session.faiss_indexes["topic_summary_index"].add(topic_id, existing.summary_embedding)


def _apply_ledger_updates(
    *,
    session: SessionState,
    ledger_updates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    applied = []
    now = now_ms()
    for item in ledger_updates:
        ledger_id = str(item.get("ledger_item_id") or f"ledger_{uuid.uuid4().hex[:8]}")
        op = item.get("op", "upsert")
        existing = session.unresolved_ledger.get(ledger_id)
        if op == "resolve" and existing:
            existing.status = "resolved"
            existing.updated_at_ms = now
            applied.append(item)
            continue

        record = LedgerItem(
            ledger_item_id=ledger_id,
            kind=item.get("kind", "open_question"),
            title=item.get("title", "Untitled ledger item"),
            summary=item.get("summary", ""),
            topic_id=item.get("topic_id", "topic_current"),
            evidence_chunk_ids=[str(cid) for cid in item.get("evidence_chunk_ids", [])],
            status=item.get("status", "open"),
            updated_at_ms=now,
        )
        session.unresolved_ledger[ledger_id] = record
        applied.append(
            {
                "op": "upsert",
                "ledger_item_id": ledger_id,
                "kind": record.kind,
                "title": record.title,
                "summary": record.summary,
                "topic_id": record.topic_id,
                "evidence_chunk_ids": record.evidence_chunk_ids,
                "status": record.status,
            }
        )
    return applied


def generate_suggestion_batch(
    *,
    session: SessionState,
    context_payload: dict[str, Any],
    route_decision: dict[str, Any],
    window_start_ms: int,
    window_end_ms: int,
    window_chunk_ids: list[str],
    embedding_service: EmbeddingService,
) -> tuple[SuggestionBatch, list[dict[str, Any]]]:
    api_key = resolve_groq_api_key(session.user_groq_api_key_in_memory)
    cards_payload: dict[str, Any] | None = None

    accepted_payload: dict[str, Any] | None = None
    for attempt in range(3):
        valid_chunk_ids = {chunk.chunk_id for chunk in session.transcript_chunks}
        try:
            if not api_key:
                raise ValueError("Missing Groq API key for suggestion generation")
            cards_payload = _request_live_suggestions(
                api_key=api_key,
                context_payload=context_payload,
                prompt_override=session.session_config.get("live_suggestions_prompt"),
            )
        except Exception as exc:  # pragma: no cover - network/host dependent
            logger.warning("Live suggestions request failed, using fallback: %s", exc)
            cards_payload = _fallback_cards(context_payload=context_payload, now=now_ms())

        candidate_cards = cards_payload.get("cards", [])
        if len(candidate_cards) != 3:
            continue
        if not has_type_diversity(candidate_cards):
            continue
        if (
            not _has_stakeholder_signal(context_payload)
            and any(card.get("type") == "stakeholder_followup" for card in candidate_cards)
        ):
            continue
        duplicate_found = False
        for card in candidate_cards:
            evidence_ids = [str(item) for item in card.get("evidence_chunk_ids", [])]
            if not any(item in valid_chunk_ids for item in evidence_ids):
                duplicate_found = True
                break
            if is_duplicate_preview(
                preview_text=f"{card.get('title', '')}. {card.get('preview', '')}",
                session=session,
                embedding_service=embedding_service,
            ):
                duplicate_found = True
                break
            if _is_already_covered_by_window(card=card, context_payload=context_payload):
                duplicate_found = True
                break
        if duplicate_found:
            continue
        accepted_payload = cards_payload
        break

    if accepted_payload is None:
        cards_payload = _fallback_cards(context_payload=context_payload, now=now_ms())
    else:
        cards_payload = accepted_payload

    cards = _materialize_cards(
        session=session,
        payload_cards=cards_payload.get("cards", [])[:3],
        window_chunk_ids=window_chunk_ids,
    )
    if len(cards) < 3:
        fallback = _materialize_cards(
            session=session,
            payload_cards=_fallback_cards(context_payload=context_payload, now=now_ms())["cards"],
            window_chunk_ids=window_chunk_ids,
        )
        cards = fallback[:3]

    for card in cards:
        card.preview_hash = preview_hash(card.preview)
        card.preview_embedding = embedding_service.embed_text(card.preview)
        if card.preview_embedding:
            session.faiss_indexes["suggestion_preview_index"].add(
                card.card_id,
                card.preview_embedding,
            )

    topic_updates = cards_payload.get("topic_updates", [])
    _apply_topic_updates(
        session=session,
        cards=cards,
        topic_updates=topic_updates,
        embedding_service=embedding_service,
    )
    applied_ledger_updates = _apply_ledger_updates(
        session=session,
        ledger_updates=cards_payload.get("ledger_updates", []),
    )

    batch = SuggestionBatch(
        batch_id=f"batch_{uuid.uuid4().hex[:8]}",
        created_at_ms=now_ms(),
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
        cards=cards[:3],
        route_decision=route_decision,
    )
    session.suggestion_batches.append(batch)
    return batch, applied_ledger_updates
