from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SessionStartRequest(BaseModel):
    groqApiKey: str | None = Field(default=None, max_length=500)


class SessionStartResponse(BaseModel):
    sessionId: str


class ValidateKeyRequest(BaseModel):
    groqApiKey: str


class ValidateKeyResponse(BaseModel):
    valid: bool
    message: str


class TranscriptChunkOut(BaseModel):
    chunk_id: str
    text: str
    start_ms: int
    end_ms: int
    created_at_ms: int
    is_low_signal: bool


class SuggestionCardOut(BaseModel):
    card_id: str
    type: Literal[
        "question_to_ask",
        "info_to_surface",
        "verify_claim",
        "decision_nudge",
        "stakeholder_followup",
    ]
    title: str
    preview: str
    why_now: str
    priority: Literal["high", "medium", "low"]
    topic_ids: list[str]
    evidence_chunk_ids: list[str]
    created_at_ms: int


class TickResponse(BaseModel):
    transcript_append: list[TranscriptChunkOut]
    cards: list[SuggestionCardOut]
    route_decision: dict[str, Any]
    ledger_updates: list[dict[str, Any]]


class SessionStateResponse(BaseModel):
    session_id: str
    created_at_ms: int
    transcript_chunks: list[TranscriptChunkOut]
    topic_clusters: list[dict[str, Any]]
    suggestion_batches: list[dict[str, Any]]
    unresolved_ledger: list[dict[str, Any]]
    active_topic_id: str | None


class CardOpenResponse(BaseModel):
    card_id: str
    explanation: str
    citations: list[dict[str, Any]]
    thread: list[dict[str, Any]]


class CardChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
