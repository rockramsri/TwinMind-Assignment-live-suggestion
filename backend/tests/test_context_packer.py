from __future__ import annotations

import json

from app.adapters.memory.faiss_index import FaissMemoryIndex
from app.domain.memory.context_packer import build_live_prompt_payload
from app.models import SessionState, TopicCluster, TranscriptChunk
from app.utils.time_utils import now_ms
from app.utils.token_budget import estimate_tokens


def test_live_context_packer_trims_payload_to_budget() -> None:
    current = now_ms()
    session = SessionState(
        session_id="session_ctx",
        created_at_ms=current,
        faiss_indexes={
            "transcript_chunk_index": FaissMemoryIndex(),
            "topic_summary_index": FaissMemoryIndex(),
            "suggestion_preview_index": FaissMemoryIndex(),
        },
    )
    session.topic_clusters["topic_x"] = TopicCluster(
        topic_id="topic_x",
        title="Topic X",
        rolling_summary=" ".join(["summary"] * 2000),
        centroid_embedding=[1.0, 0.0],
        summary_embedding=[1.0, 0.0],
        chunk_ids=[],
        last_touched_ms=current,
    )
    window_chunks = [
        TranscriptChunk(
            chunk_id=f"chunk_{idx}",
            text=" ".join(["window"] * 1200),
            start_ms=idx * 5000,
            end_ms=(idx + 1) * 5000,
            created_at_ms=current,
            is_low_signal=False,
        )
        for idx in range(3)
    ]
    older_chunk = TranscriptChunk(
        chunk_id="chunk_old",
        text="window related historical context",
        start_ms=0,
        end_ms=1000,
        created_at_ms=current,
        embedding=[1.0, 0.0],
        is_low_signal=False,
    )
    session.transcript_chunks.extend(window_chunks + [older_chunk])
    for chunk in session.transcript_chunks:
        if chunk.embedding:
            session.faiss_indexes["transcript_chunk_index"].add(chunk.chunk_id, chunk.embedding)
    session.faiss_indexes["topic_summary_index"].add("topic_x", [1.0, 0.0])
    session.topic_clusters["topic_x"].chunk_ids = ["chunk_old"]

    payload = build_live_prompt_payload(
        session=session,
        window_start_ms=0,
        window_end_ms=15000,
        window_chunks=window_chunks,
        route_decision={"selected_topics": [{"topic_id": "topic_x"}], "mode": "single_topic"},
    )

    serialized = json.dumps(payload)
    # Approximation because token estimator is heuristic.
    assert estimate_tokens(serialized) <= 2200
    assert payload["current_window_chunks"]
    assert len(payload["topic_context"][0]["summary"].split()) < 1000
    assert "retrieved_topic_chunks" in payload
