from __future__ import annotations

import json
from typing import Any


TOPIC_RANKER_SYSTEM_PROMPT = """
You are a topic ranker for a live meeting copilot.
Return STRICT JSON only.
Task:
- Given current transcript window and candidate topic summaries, rank top 5 relevant topics.
Rules:
- Prefer the minimum set of topics needed.
- Penalize stale topics unless clearly reintroduced.
- Boost unresolved topics when semantically relevant.
- Score each selected topic from 0.0 to 1.0.
""".strip()


LIVE_SUGGESTIONS_SYSTEM_PROMPT = """
You generate live suggestion cards for an ongoing conversation.
Return STRICT JSON only.
Hard requirements:
- Produce exactly 3 cards.
- Ground every card in transcript evidence chunk ids.
- No generic coaching fluff and no duplicate intents.
- If current window is thin/silent, use unresolved ledger context or a clarification card.
- Prefer type diversity across:
  question_to_ask, info_to_surface, verify_claim, decision_nudge, stakeholder_followup.
- Keep text concise and useful.
- Avoid `stakeholder_followup` unless the transcript explicitly mentions stakeholders,
  clients, users, or teams beyond the speaker.
- Do not generate vague "project starter" advice; each card must reference a concrete
  spoken detail from the current window.
""".strip()


CLICKED_CARD_SYSTEM_PROMPT = """
You answer follow-up questions for one selected suggestion card.
Rules:
- Stay grounded to provided transcript/context only.
- Never claim external facts unless they are explicitly present in the transcript context.
- If verification needs outside sources, say so plainly.
- Answer the user directly. Do not explain card mechanics (avoid phrases like
  "this card asks you to ...").
- Keep answers concise and practical with clear next actions.
- If context is sparse, provide the best possible answer plus one short clarification question.
- Do not include chunk ids inline in the narrative. Citations are appended separately.
""".strip()


TOPIC_RANKER_JSON_SCHEMA: dict[str, Any] = {
    "name": "topic_ranker_response",
    "schema": {
        "type": "object",
        "properties": {
            "ranked_topics": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "topic_id": {"type": "string"},
                        "score": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["topic_id", "score", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["ranked_topics"],
        "additionalProperties": False,
    },
    "strict": True,
}


LIVE_SUGGESTIONS_JSON_SCHEMA: dict[str, Any] = {
    "name": "live_suggestions_response",
    "schema": {
        "type": "object",
        "properties": {
            "cards": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "card_id": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": [
                                "question_to_ask",
                                "info_to_surface",
                                "verify_claim",
                                "decision_nudge",
                                "stakeholder_followup",
                            ],
                        },
                        "title": {"type": "string", "maxLength": 80},
                        "preview": {"type": "string", "maxLength": 180},
                        "why_now": {"type": "string", "maxLength": 180},
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "topic_ids": {"type": "array", "items": {"type": "string"}},
                        "evidence_chunk_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "card_id",
                        "type",
                        "title",
                        "preview",
                        "why_now",
                        "priority",
                        "topic_ids",
                        "evidence_chunk_ids",
                    ],
                    "additionalProperties": False,
                },
            },
            "topic_updates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic_id": {"type": "string"},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                    },
                    "required": ["topic_id", "title", "summary"],
                    "additionalProperties": False,
                },
            },
            "ledger_updates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "op": {"type": "string", "enum": ["upsert", "resolve"]},
                        "ledger_item_id": {"type": "string"},
                        "kind": {
                            "type": "string",
                            "enum": [
                                "open_question",
                                "verify_claim",
                                "pending_decision",
                                "stakeholder_followup",
                                "risk",
                                "action_item",
                            ],
                        },
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "topic_id": {"type": "string"},
                        "evidence_chunk_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "status": {"type": "string", "enum": ["open", "resolved"]},
                    },
                    "required": [
                        "op",
                        "ledger_item_id",
                        "kind",
                        "title",
                        "summary",
                        "topic_id",
                        "evidence_chunk_ids",
                        "status",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["cards", "topic_updates", "ledger_updates"],
        "additionalProperties": False,
    },
    "strict": True,
}


def topic_ranker_messages(
    window_text: str,
    candidates: list[dict[str, Any]],
    unresolved_items: list[dict[str, Any]],
) -> list[dict[str, str]]:
    payload = {
        "current_window_transcript": window_text,
        "candidate_topics": candidates,
        "unresolved_ledger": unresolved_items,
    }
    return [
        {
            "role": "system",
            "content": (
                f"{TOPIC_RANKER_SYSTEM_PROMPT}\n"
                f"JSON schema: {json.dumps(TOPIC_RANKER_JSON_SCHEMA['schema'])}"
            ),
        },
        {"role": "user", "content": json.dumps(payload)},
    ]


def live_suggestion_messages(
    context_payload: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                f"{LIVE_SUGGESTIONS_SYSTEM_PROMPT}\n"
                f"JSON schema: {json.dumps(LIVE_SUGGESTIONS_JSON_SCHEMA['schema'])}"
            ),
        },
        {"role": "user", "content": json.dumps(context_payload)},
    ]


def card_chat_messages(
    card_payload: dict[str, Any],
    thread: list[dict[str, Any]],
    user_message: str | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": CLICKED_CARD_SYSTEM_PROMPT},
        {"role": "system", "content": json.dumps(card_payload)},
    ]
    messages.extend(thread)
    if user_message is not None:
        messages.append({"role": "user", "content": user_message})
    return messages
