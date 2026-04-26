from __future__ import annotations

import math
from typing import Any

import faiss
import numpy as np


class FaissMemoryIndex:
    def __init__(self) -> None:
        self.dimension: int | None = None
        self.index: faiss.IndexFlatIP | None = None
        self.ids: list[str] = []
        self.latest_pos: dict[str, int] = {}

    @staticmethod
    def _normalize(vector: list[float]) -> np.ndarray:
        arr = np.array(vector, dtype=np.float32)
        norm = float(np.linalg.norm(arr))
        if norm <= 0:
            return arr
        return arr / norm

    def _ensure_index(self, vector: list[float]) -> None:
        if self.index is not None:
            return
        self.dimension = len(vector)
        self.index = faiss.IndexFlatIP(self.dimension)

    def add(self, item_id: str, vector: list[float]) -> None:
        if not vector:
            return
        self._ensure_index(vector)
        if self.index is None or self.dimension is None:
            return
        if len(vector) != self.dimension:
            raise ValueError("Vector dimension mismatch for FAISS index")
        normalized = self._normalize(vector).reshape(1, -1)
        self.index.add(normalized)
        position = len(self.ids)
        self.ids.append(item_id)
        self.latest_pos[item_id] = position

    def search(self, query: list[float], top_k: int = 5) -> list[tuple[str, float]]:
        if self.index is None or self.dimension is None or not query:
            return []
        if len(query) != self.dimension:
            return []
        query_np = self._normalize(query).reshape(1, -1)
        k = max(1, min(top_k * 3, len(self.ids)))
        scores, positions = self.index.search(query_np, k)
        deduped: dict[str, float] = {}
        for score, pos in zip(scores[0], positions[0]):
            if pos < 0 or pos >= len(self.ids):
                continue
            item_id = self.ids[pos]
            if self.latest_pos.get(item_id) != pos:
                continue
            current = deduped.get(item_id, -math.inf)
            if score > current:
                deduped[item_id] = float(score)

        ranked = sorted(deduped.items(), key=lambda item: item[1], reverse=True)
        return ranked[:top_k]

    def has_item(self, item_id: str) -> bool:
        return item_id in self.latest_pos

    def metadata(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "items": len(self.latest_pos),
        }
