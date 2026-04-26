from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

from openai import OpenAI

from app.config import get_settings
from app.context_packer import build_card_chat_payload
from app.models import ChatMessage, SessionState, SuggestionCard
from app.prompts import card_chat_messages
from app.transcribe import resolve_groq_api_key
from app.utils.time_utils import format_citation_range, now_ms
from app.utils.token_budget import estimate_tokens

logger = logging.getLogger(__name__)


def _find_card(session: SessionState, card_id: str) -> SuggestionCard | None:
    for batch in reversed(session.suggestion_batches):
        for card in batch.cards:
            if card.card_id == card_id:
                return card
    return None


def _build_citations(session: SessionState, chunk_ids: list[str]) -> list[dict[str, Any]]:
    by_id = {chunk.chunk_id: chunk for chunk in session.transcript_chunks}
    citations = []
    for chunk_id in chunk_ids:
        chunk = by_id.get(chunk_id)
        if chunk is None:
            continue
        citations.append(
            {
                "chunk_id": chunk.chunk_id,
                "start_ms": chunk.start_ms,
                "end_ms": chunk.end_ms,
                "label": format_citation_range(chunk.start_ms, chunk.end_ms),
            }
        )
    return citations


def _citation_footer(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return "\n\nSources: none available in current transcript window."
    parts = [f"{item['chunk_id']} {item['label']}" for item in citations]
    return "\n\nSources: " + ", ".join(parts)


def _summarize_thread_if_needed(
    thread: list[ChatMessage],
    token_cap: int,
) -> list[ChatMessage]:
    total = sum(estimate_tokens(msg.text) for msg in thread)
    if total <= int(token_cap * 0.8) and len(thread) <= 12:
        return thread
    if len(thread) <= 4:
        return thread

    keep_tail = thread[-8:]
    older = thread[:-8]
    summary_lines = []
    for message in older:
        role = "User" if message.role == "user" else "Assistant"
        summary_lines.append(f"{role}: {message.text[:120]}")
    summary = "Previous card-thread summary:\n" + "\n".join(summary_lines[:8])
    summarized_head = ChatMessage(
        role="system",
        text=summary,
        created_at_ms=now_ms(),
    )
    return [summarized_head, *keep_tail]


def open_card_explanation(
    *,
    session: SessionState,
    card_id: str,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    card = _find_card(session, card_id)
    if card is None:
        raise ValueError("Card not found")

    citations = _build_citations(session, card.evidence_chunk_ids)
    thread = session.card_chat_threads.setdefault(card_id, [])
    if thread:
        return thread[0].text, citations, _thread_to_dict(thread)

    payload = build_card_chat_payload(session=session, card=card, latest_user_message=None)
    prompt_message = (
        "Provide an immediate grounded answer to the user intent behind this card. "
        "Do not describe card mechanics. Keep it concise and practical."
    )
    api_key = resolve_groq_api_key(session.user_groq_api_key_in_memory)
    answer = ""
    if api_key:
        try:
            settings = get_settings()
            client = OpenAI(api_key=api_key, base_url=settings.GROQ_BASE_URL)
            completion = client.chat.completions.create(
                model=settings.LLM_MODEL,
                temperature=0.4,
                messages=card_chat_messages(payload, [], prompt_message),
            )
            answer = (completion.choices[0].message.content or "").strip()
        except Exception as exc:  # pragma: no cover - network/host dependent
            logger.warning("Card open explanation generation failed: %s", exc)

    if not answer:
        evidence_summary = "; ".join(
            [
                f"{item['chunk_id']} {item['label']}"
                for item in citations[:3]
            ]
        )
        answer = (
            f"{card.title}: {card.preview}. "
            f"Why now: {card.why_now}. "
            f"Grounding: {evidence_summary or 'insufficient transcript evidence'}."
        )
    answer = answer + _citation_footer(citations)

    assistant_msg = ChatMessage(
        role="assistant",
        text=answer,
        created_at_ms=now_ms(),
        citations=[item["chunk_id"] for item in citations],
    )
    thread.append(assistant_msg)
    return answer, citations, _thread_to_dict(thread)


def stream_card_chat_answer(
    *,
    session: SessionState,
    card_id: str,
    user_message: str,
) -> Generator[str, None, None]:
    card = _find_card(session, card_id)
    if card is None:
        raise ValueError("Card not found")

    settings = get_settings()
    thread = session.card_chat_threads.setdefault(card_id, [])
    thread.append(ChatMessage(role="user", text=user_message, created_at_ms=now_ms()))
    compact_thread = _summarize_thread_if_needed(thread, settings.CHAT_CONTEXT_TOKEN_CAP)
    session.card_chat_threads[card_id] = compact_thread

    payload = build_card_chat_payload(
        session=session,
        card=card,
        latest_user_message=user_message,
    )
    citations = _build_citations(session, card.evidence_chunk_ids)
    prior_thread = compact_thread
    if (
        prior_thread
        and prior_thread[-1].role == "user"
        and prior_thread[-1].text == user_message
    ):
        prior_thread = prior_thread[:-1]
    history = [{"role": msg.role, "content": msg.text} for msg in prior_thread][-10:]

    api_key = resolve_groq_api_key(session.user_groq_api_key_in_memory)
    streamed_parts: list[str] = []
    if api_key:
        try:
            client = OpenAI(api_key=api_key, base_url=settings.GROQ_BASE_URL)
            stream = client.chat.completions.create(
                model=settings.LLM_MODEL,
                temperature=0.35,
                stream=True,
                messages=card_chat_messages(payload, history, user_message),
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if not delta:
                    continue
                streamed_parts.append(delta)
                yield delta
        except Exception as exc:  # pragma: no cover - network/host dependent
            logger.warning("Card chat stream failed, returning fallback text: %s", exc)

    if not streamed_parts:
        fallback = (
            "Based on the selected card evidence, this point is supported by the cited transcript "
            "segments. If you need factual verification outside the transcript, external validation is required."
        )
        streamed_parts.append(fallback)
        yield fallback

    footer = _citation_footer(citations)
    streamed_parts.append(footer)
    yield footer

    full_answer = "".join(streamed_parts).strip()
    session.card_chat_threads[card_id].append(
        ChatMessage(
            role="assistant",
            text=full_answer,
            created_at_ms=now_ms(),
            citations=[item["chunk_id"] for item in citations],
        )
    )


def _thread_to_dict(thread: list[ChatMessage]) -> list[dict[str, Any]]:
    return [
        {
            "role": msg.role,
            "text": msg.text,
            "created_at_ms": msg.created_at_ms,
            "citations": msg.citations,
        }
        for msg in thread
    ]
