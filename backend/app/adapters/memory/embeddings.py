from __future__ import annotations

import hashlib
import logging
import math
import os
import sys
import threading

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._model = None
        self._fallback = False
        self._lock = threading.Lock()
        self._fallback_dim = 384

    def _ensure_model(self) -> None:
        if self._model is not None or self._fallback:
            return
        with self._lock:
            if self._model is not None or self._fallback:
                return
            if os.getenv("TM_FORCE_HASH_EMBEDDINGS", "").lower() in {"1", "true", "yes"}:
                self._fallback = True
                return
            # torch wheels used by sentence-transformers are not consistently stable on
            # Python 3.13 yet, so we safely fall back to deterministic hash embeddings.
            if sys.version_info >= (3, 13):
                logger.warning(
                    "Python %s detected; using hash embeddings fallback.",
                    ".".join(map(str, sys.version_info[:3])),
                )
                self._fallback = True
                return
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._settings.EMBED_MODEL)
                logger.info("Loaded embedding model: %s", self._settings.EMBED_MODEL)
            except Exception as exc:  # pragma: no cover - depends on host runtime
                logger.warning(
                    "Falling back to hash embeddings; model load failed: %s", exc
                )
                self._fallback = True

    @staticmethod
    def _normalize(vec: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in vec))
        if norm == 0:
            return vec
        return [value / norm for value in vec]

    def _hash_embed(self, text: str) -> list[float]:
        vec = [0.0] * self._fallback_dim
        tokens = text.lower().split()
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:2], "big") % self._fallback_dim
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vec[idx] += sign
        return self._normalize(vec)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self._ensure_model()
        if not texts:
            return []
        if self._fallback or self._model is None:
            return [self._hash_embed(text) for text in texts]

        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]

    def embed_text(self, text: str) -> list[float]:
        vectors = self.embed_texts([text])
        return vectors[0] if vectors else []


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    return float(sum(a * b for a, b in zip(vec_a, vec_b)))
