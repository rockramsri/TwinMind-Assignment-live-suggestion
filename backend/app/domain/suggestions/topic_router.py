from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from app.adapters.memory.embeddings import EmbeddingService, cosine_similarity
from app.config import get_settings
from app.domain.transcript.transcribe import resolve_groq_api_key
from app.models import SessionState, TopicCluster
from app.prompts import TOPIC_RANKER_JSON_SCHEMA, topic_ranker_messages
from app.utils.text_normalize import keyword_set
from app.utils.time_utils import now_ms

logger = logging.getLogger(__name__)


def keyword_overlap_score(window_text: str, topic_summary: str) -> float:
    window_tokens = keyword_set(window_text)
    summary_tokens = keyword_set(topic_summary)
    if not window_tokens or not summary_tokens:
        return 0.0
    intersection = len(window_tokens.intersection(summary_tokens))
    return intersection / max(1, len(window_tokens))


def recency_bonus(last_touched_ms: int, current_ms: int) -> float:
    age_ms = max(0, current_ms - last_touched_ms)
    # Full bonus at touch-time, linear decay over 15 minutes.
    return max(0.0, 1.0 - (age_ms / (15 * 60 * 1000)))


def compute_recent_topic_score(
    *,
    window_embedding: list[float],
    cluster: TopicCluster,
    window_text: str,
    current_ms: int,
) -> float:
    centroid_sim = cosine_similarity(window_embedding, cluster.centroid_embedding)
    summary_sim = cosine_similarity(window_embedding, cluster.summary_embedding)
    overlap = keyword_overlap_score(window_text, cluster.rolling_summary)
    recency = recency_bonus(cluster.last_touched_ms, current_ms)
    return (
        (0.55 * centroid_sim)
        + (0.25 * summary_sim)
        + (0.10 * overlap)
        + (0.10 * recency)
    )


def _rank_topics_with_llm(
    *,
    api_key: str | None,
    window_text: str,
    candidates: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not api_key or not candidates:
        return []
    settings = get_settings()
    client = OpenAI(api_key=api_key, base_url=settings.GROQ_BASE_URL)
    completion = client.chat.completions.create(
        model=settings.LLM_MODEL,
        temperature=0.2,
        response_format={
            "type": "json_schema",
            "json_schema": TOPIC_RANKER_JSON_SCHEMA,
        },
        messages=topic_ranker_messages(window_text, candidates, unresolved_items),
    )
    raw = completion.choices[0].message.content or "{}"
    parsed = json.loads(raw)
    ranked = parsed.get("ranked_topics", [])
    if not isinstance(ranked, list):
        return []
    return ranked


def route_topics(
    *,
    session: SessionState,
    window_chunks: list[Any],
    embedding_service: EmbeddingService,
) -> dict[str, Any]:
    settings = get_settings()
    significant_chunks = [chunk for chunk in window_chunks if not chunk.is_low_signal]
    window_text = "\n".join(chunk.text for chunk in significant_chunks).strip()
    if not window_text:
        return {
            "mode": "empty_window",
            "recent_topic_score": 0.0,
            "gap_to_next": 0.0,
            "selected_topics": [],
            "candidates_considered": 0,
        }

    window_embedding = embedding_service.embed_text(window_text)
    if not session.topic_clusters:
        return {
            "mode": "cold_start",
            "recent_topic_score": 0.0,
            "gap_to_next": 0.0,
            "selected_topics": [],
            "candidates_considered": 0,
        }

    current_ms = now_ms()
    prefilter_ids = [
        topic_id
        for topic_id, _ in session.faiss_indexes["topic_summary_index"].search(
            window_embedding,
            top_k=max(10, settings.TOPIC_CANDIDATE_PREFILTER),
        )
    ]
    if session.active_topic_id and session.active_topic_id not in prefilter_ids:
        prefilter_ids.append(session.active_topic_id)
    candidate_topics = (
        [session.topic_clusters[topic_id] for topic_id in prefilter_ids if topic_id in session.topic_clusters]
        if prefilter_ids
        else list(session.topic_clusters.values())
    )
    scored_topics: list[dict[str, Any]] = []
    for cluster in candidate_topics:
        score = compute_recent_topic_score(
            window_embedding=window_embedding,
            cluster=cluster,
            window_text=window_text,
            current_ms=current_ms,
        )
        scored_topics.append(
            {
                "topic_id": cluster.topic_id,
                "title": cluster.title,
                "score": float(score),
            }
        )
    scored_topics.sort(key=lambda item: item["score"], reverse=True)

    top_score = scored_topics[0]["score"]
    next_score = scored_topics[1]["score"] if len(scored_topics) > 1 else 0.0
    gap_to_next = top_score - next_score

    active_topic_id = session.active_topic_id or scored_topics[0]["topic_id"]
    active_score = next(
        (item["score"] for item in scored_topics if item["topic_id"] == active_topic_id),
        top_score,
    )

    if (
        active_score >= settings.RECENT_TOPIC_THRESHOLD
        and gap_to_next >= 0.08
        and scored_topics[0]["topic_id"] == active_topic_id
    ):
        selected = [
            {
                "topic_id": active_topic_id,
                "score": round(active_score, 4),
                "reason": "recent_topic_high_confidence",
            }
        ]
        session.active_topic_id = active_topic_id
        return {
            "mode": "single_topic",
            "recent_topic_score": round(active_score, 4),
            "gap_to_next": round(gap_to_next, 4),
            "selected_topics": selected,
            "candidates_considered": 1,
        }

    candidates = scored_topics[: settings.TOPIC_CANDIDATE_PREFILTER]
    candidate_payload = []
    for item in candidates:
        cluster = session.topic_clusters[item["topic_id"]]
        candidate_payload.append(
            {
                "topic_id": item["topic_id"],
                "title": cluster.title,
                "summary": cluster.rolling_summary,
                "embedding_score": round(item["score"], 4),
                "last_touched_ms": cluster.last_touched_ms,
            }
        )

    unresolved_items = [
        {
            "ledger_item_id": ledger.ledger_item_id,
            "topic_id": ledger.topic_id,
            "kind": ledger.kind,
            "summary": ledger.summary,
        }
        for ledger in session.unresolved_ledger.values()
        if ledger.status == "open"
    ]
    api_key = resolve_groq_api_key(session.user_groq_api_key_in_memory)
    ranked_topics: list[dict[str, Any]] = []
    try:
        ranked_topics = _rank_topics_with_llm(
            api_key=api_key,
            window_text=window_text,
            candidates=candidate_payload,
            unresolved_items=unresolved_items,
        )
    except Exception as exc:  # pragma: no cover - network/host dependent
        logger.warning("Topic ranker failed; using embedding fallback: %s", exc)

    if not ranked_topics:
        ranked_topics = [
            {
                "topic_id": item["topic_id"],
                "score": round(float(item["score"]), 4),
                "reason": "embedding_prefilter_fallback",
            }
            for item in candidates[: settings.TOPIC_RANKER_TOP_K]
        ]

    filtered = [
        item
        for item in ranked_topics[: settings.TOPIC_RANKER_TOP_K]
        if float(item.get("score", 0.0)) >= settings.FALLBACK_TOPIC_THRESHOLD
    ]
    if not filtered and ranked_topics:
        filtered = ranked_topics[:1]

    if filtered:
        session.active_topic_id = str(filtered[0]["topic_id"])

    return {
        "mode": "fallback_ranker",
        "recent_topic_score": round(active_score, 4),
        "gap_to_next": round(gap_to_next, 4),
        "selected_topics": filtered,
        "candidates_considered": len(candidate_topics),
    }
