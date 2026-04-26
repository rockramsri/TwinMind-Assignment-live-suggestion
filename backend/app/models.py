from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


CardType = Literal[
    "question_to_ask",
    "info_to_surface",
    "verify_claim",
    "decision_nudge",
    "stakeholder_followup",
]
PriorityType = Literal["high", "medium", "low"]
LedgerKind = Literal[
    "open_question",
    "verify_claim",
    "pending_decision",
    "stakeholder_followup",
    "risk",
    "action_item",
]
LedgerStatus = Literal["open", "resolved"]
ChatRole = Literal["user", "assistant", "system"]


@dataclass
class TranscriptChunk:
    chunk_id: str
    text: str
    start_ms: int
    end_ms: int
    created_at_ms: int
    embedding: list[float] = field(default_factory=list)
    is_low_signal: bool = False
    topic_tags: list[str] = field(default_factory=list)


@dataclass
class TopicCluster:
    topic_id: str
    title: str
    rolling_summary: str
    centroid_embedding: list[float] = field(default_factory=list)
    summary_embedding: list[float] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    last_touched_ms: int = 0


@dataclass
class SuggestionCard:
    card_id: str
    type: CardType
    title: str
    preview: str
    why_now: str
    priority: PriorityType
    topic_ids: list[str]
    evidence_chunk_ids: list[str]
    created_at_ms: int
    preview_hash: str = ""
    preview_embedding: list[float] = field(default_factory=list)


@dataclass
class SuggestionBatch:
    batch_id: str
    created_at_ms: int
    window_start_ms: int
    window_end_ms: int
    cards: list[SuggestionCard]
    route_decision: dict[str, Any] = field(default_factory=dict)


@dataclass
class LedgerItem:
    ledger_item_id: str
    kind: LedgerKind
    title: str
    summary: str
    topic_id: str
    evidence_chunk_ids: list[str]
    status: LedgerStatus
    updated_at_ms: int


@dataclass
class ChatMessage:
    role: ChatRole
    text: str
    created_at_ms: int
    citations: list[str] = field(default_factory=list)


@dataclass
class SessionState:
    session_id: str
    created_at_ms: int
    user_groq_api_key_in_memory: str | None = None
    transcript_chunks: list[TranscriptChunk] = field(default_factory=list)
    topic_clusters: dict[str, TopicCluster] = field(default_factory=dict)
    suggestion_batches: list[SuggestionBatch] = field(default_factory=list)
    unresolved_ledger: dict[str, LedgerItem] = field(default_factory=dict)
    card_chat_threads: dict[str, list[ChatMessage]] = field(default_factory=dict)
    faiss_indexes: dict[str, Any] = field(default_factory=dict)
    active_topic_id: str | None = None
    last_tick_window_end_ms: int = 0
    last_tick_emitted_ms: int = 0
    session_config: dict[str, Any] = field(default_factory=dict)
