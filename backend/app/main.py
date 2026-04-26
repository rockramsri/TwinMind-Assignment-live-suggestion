from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from openai import OpenAI

from app.audio import append_transcript_chunk, build_rolling_window
from app.chat_engine import open_card_explanation, stream_card_chat_answer
from app.config import get_settings
from app.context_packer import build_live_prompt_payload
from app.embeddings import EmbeddingService
from app.export import build_session_export
from app.models import SessionState, SuggestionCard, TranscriptChunk
from app.schemas import (
    CardChatRequest,
    CardOpenResponse,
    SessionStartRequest,
    SessionStartResponse,
    SessionStateResponse,
    SuggestionCardOut,
    TickResponse,
    TranscriptChunkOut,
    ValidateKeyRequest,
    ValidateKeyResponse,
)
from app.session_store import create_session, get_session, set_session_key
from app.suggestion_engine import generate_suggestion_batch
from app.topic_router import route_topics
from app.transcribe import resolve_groq_api_key, transcribe_audio_slice

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(title="Twinmind Live Copilot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embedding_service = EmbeddingService()


def _require_session(session_id: str) -> SessionState:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _chunk_out(chunk: TranscriptChunk) -> TranscriptChunkOut:
    return TranscriptChunkOut(
        chunk_id=chunk.chunk_id,
        text=chunk.text,
        start_ms=chunk.start_ms,
        end_ms=chunk.end_ms,
        created_at_ms=chunk.created_at_ms,
        is_low_signal=chunk.is_low_signal,
    )


def _card_out(card: SuggestionCard) -> SuggestionCardOut:
    return SuggestionCardOut(
        card_id=card.card_id,
        type=card.type,
        title=card.title,
        preview=card.preview,
        why_now=card.why_now,
        priority=card.priority,
        topic_ids=card.topic_ids,
        evidence_chunk_ids=card.evidence_chunk_ids,
        created_at_ms=card.created_at_ms,
    )


def _state_out(session: SessionState) -> SessionStateResponse:
    return SessionStateResponse(
        session_id=session.session_id,
        created_at_ms=session.created_at_ms,
        transcript_chunks=[_chunk_out(chunk) for chunk in session.transcript_chunks],
        topic_clusters=[
            {
                "topic_id": topic.topic_id,
                "title": topic.title,
                "rolling_summary": topic.rolling_summary,
                "chunk_ids": topic.chunk_ids,
                "last_touched_ms": topic.last_touched_ms,
            }
            for topic in session.topic_clusters.values()
        ],
        suggestion_batches=[
            {
                "batch_id": batch.batch_id,
                "created_at_ms": batch.created_at_ms,
                "window_start_ms": batch.window_start_ms,
                "window_end_ms": batch.window_end_ms,
                "route_decision": batch.route_decision,
                "cards": [_card_out(card).model_dump() for card in batch.cards],
            }
            for batch in session.suggestion_batches
        ],
        unresolved_ledger=[
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
        active_topic_id=session.active_topic_id,
    )


@app.get("/api/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/session/start", response_model=SessionStartResponse)
def start_session(payload: SessionStartRequest) -> SessionStartResponse:
    session = create_session(payload.groqApiKey)
    return SessionStartResponse(sessionId=session.session_id)


@app.post("/api/session/{session_id}/validate-key", response_model=ValidateKeyResponse)
def validate_key(session_id: str, payload: ValidateKeyRequest) -> ValidateKeyResponse:
    session = _require_session(session_id)
    key = payload.groqApiKey.strip()
    if not key:
        return ValidateKeyResponse(valid=False, message="Groq key is required")
    try:
        client = OpenAI(api_key=key, base_url=settings.GROQ_BASE_URL)
        client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": "Reply with: ok"}],
            max_tokens=4,
            temperature=0,
        )
        set_session_key(session.session_id, key)
        return ValidateKeyResponse(valid=True, message="Groq key looks valid")
    except Exception:
        return ValidateKeyResponse(valid=False, message="Groq key validation failed")


@app.post("/api/session/{session_id}/audio-slice", response_model=TranscriptChunkOut)
async def upload_audio_slice(
    session_id: str,
    file: UploadFile = File(...),
    start_ms: int = Form(...),
    end_ms: int = Form(...),
) -> TranscriptChunkOut:
    session = _require_session(session_id)
    body = await file.read()
    if not body:
        raise HTTPException(status_code=400, detail="Empty audio slice")
    try:
        transcript_text = transcribe_audio_slice(
            audio_bytes=body,
            filename=file.filename or "slice.webm",
            session_key=session.user_groq_api_key_in_memory,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:  # pragma: no cover - runtime API dependency
        # Keep timeline moving even when STT for one slice fails.
        transcript_text = ""

    chunk = append_transcript_chunk(
        session,
        text=transcript_text,
        start_ms=start_ms,
        end_ms=end_ms,
        embedding_service=embedding_service,
    )
    return _chunk_out(chunk)


@app.post("/api/session/{session_id}/tick", response_model=TickResponse)
def tick_session(session_id: str) -> TickResponse:
    session = _require_session(session_id)
    api_key = resolve_groq_api_key(session.user_groq_api_key_in_memory)
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="No Groq key configured. Add key in settings to continue.",
        )

    window_start_ms, window_end_ms, window_chunks = build_rolling_window(
        session=session,
        window_seconds=settings.LIVE_WINDOW_SECONDS,
    )
    route_decision = route_topics(
        session=session,
        window_chunks=window_chunks,
        embedding_service=embedding_service,
    )
    context_payload = build_live_prompt_payload(
        session=session,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
        window_chunks=window_chunks,
        route_decision=route_decision,
    )

    batch, ledger_updates = generate_suggestion_batch(
        session=session,
        context_payload=context_payload,
        route_decision=route_decision,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
        window_chunk_ids=[chunk.chunk_id for chunk in window_chunks],
        embedding_service=embedding_service,
    )

    transcript_append = [
        chunk
        for chunk in session.transcript_chunks
        if chunk.end_ms > session.last_tick_window_end_ms
    ]
    session.last_tick_window_end_ms = max(session.last_tick_window_end_ms, window_end_ms)

    return TickResponse(
        transcript_append=[_chunk_out(chunk) for chunk in transcript_append],
        cards=[_card_out(card) for card in batch.cards[:3]],
        route_decision=route_decision,
        ledger_updates=ledger_updates,
    )


@app.get("/api/session/{session_id}/state", response_model=SessionStateResponse)
def get_state(session_id: str) -> SessionStateResponse:
    session = _require_session(session_id)
    return _state_out(session)


@app.post("/api/session/{session_id}/card/{card_id}/open", response_model=CardOpenResponse)
def open_card(session_id: str, card_id: str) -> CardOpenResponse:
    session = _require_session(session_id)
    try:
        explanation, citations, thread = open_card_explanation(
            session=session,
            card_id=card_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CardOpenResponse(
        card_id=card_id,
        explanation=explanation,
        citations=citations,
        thread=thread,
    )


@app.post("/api/session/{session_id}/card/{card_id}/chat")
def chat_card(session_id: str, card_id: str, payload: CardChatRequest) -> StreamingResponse:
    session = _require_session(session_id)
    try:
        generator = stream_card_chat_answer(
            session=session,
            card_id=card_id,
            user_message=payload.message.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StreamingResponse(generator, media_type="text/plain")


@app.get("/api/session/{session_id}/export")
def export_session(session_id: str) -> JSONResponse:
    session = _require_session(session_id)
    payload = build_session_export(session)
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": f'attachment; filename="session-{session_id}.json"'
        },
    )


@app.get("/api/session/{session_id}/debug/context")
def debug_context(session_id: str) -> JSONResponse:
    # Lightweight helper endpoint for local debugging only.
    session = _require_session(session_id)
    export_payload: dict[str, Any] = build_session_export(session)
    return JSONResponse(content=json.loads(json.dumps(export_payload)))
