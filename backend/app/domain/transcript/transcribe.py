from __future__ import annotations

import io
import logging

from groq import Groq

from app.config import get_settings

logger = logging.getLogger(__name__)


def resolve_groq_api_key(session_key: str | None) -> str | None:
    settings = get_settings()
    if session_key and session_key.strip():
        return session_key.strip()
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip():
        return settings.GROQ_API_KEY.strip()
    return None


def transcribe_audio_slice(
    *,
    audio_bytes: bytes,
    filename: str,
    session_key: str | None,
) -> str:
    api_key = resolve_groq_api_key(session_key)
    if not api_key:
        raise ValueError("Missing Groq API key")

    settings = get_settings()
    client = Groq(api_key=api_key)
    file_tuple = (filename, io.BytesIO(audio_bytes))
    response = client.audio.transcriptions.create(
        model=settings.STT_MODEL,
        file=file_tuple,
        response_format="verbose_json",
    )
    text = ""
    if hasattr(response, "text"):
        text = (response.text or "").strip()
    elif isinstance(response, dict):
        text = str(response.get("text", "")).strip()
    if not text:
        logger.info("STT returned empty transcript for slice: %s", filename)
    return text
