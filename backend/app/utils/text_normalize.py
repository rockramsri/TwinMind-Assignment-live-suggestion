from __future__ import annotations

import hashlib
import re


_SPACES_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")


def normalize_preview(text: str) -> str:
    lowered = text.lower().strip()
    lowered = _PUNCT_RE.sub(" ", lowered)
    return _SPACES_RE.sub(" ", lowered).strip()


def preview_hash(text: str) -> str:
    normalized = normalize_preview(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def keyword_set(text: str) -> set[str]:
    normalized = normalize_preview(text)
    return {token for token in normalized.split(" ") if len(token) > 2}
