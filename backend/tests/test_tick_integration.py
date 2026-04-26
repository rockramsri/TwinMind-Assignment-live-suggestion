from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_tick_emits_exactly_three_cards_with_evidence_refs(monkeypatch) -> None:
    client = TestClient(app)

    def fake_transcribe_audio_slice(**kwargs):
        return "We should lock the launch date and verify budget assumptions."

    def fake_request_live_suggestions(*, api_key, context_payload):
        chunk_ids = [item["chunk_id"] for item in context_payload.get("current_window_chunks", [])]
        evidence = chunk_ids[:2] or ["chunk_stub"]
        return {
            "cards": [
                {
                    "card_id": "card_a",
                    "type": "question_to_ask",
                    "title": "Confirm launch owner",
                    "preview": "Ask who owns final launch date approval.",
                    "why_now": "Ownership was implied but not explicit.",
                    "priority": "high",
                    "topic_ids": ["topic_launch"],
                    "evidence_chunk_ids": evidence,
                },
                {
                    "card_id": "card_b",
                    "type": "verify_claim",
                    "title": "Validate budget assumption",
                    "preview": "Budget baseline may be outdated.",
                    "why_now": "A claim was made without a source.",
                    "priority": "medium",
                    "topic_ids": ["topic_budget"],
                    "evidence_chunk_ids": evidence,
                },
                {
                    "card_id": "card_c",
                    "type": "decision_nudge",
                    "title": "Capture launch decision",
                    "preview": "Convert discussion into a clear decision check.",
                    "why_now": "Conversation is converging on a date.",
                    "priority": "medium",
                    "topic_ids": ["topic_launch"],
                    "evidence_chunk_ids": evidence,
                },
            ],
            "topic_updates": [],
            "ledger_updates": [],
        }

    monkeypatch.setattr("app.main.transcribe_audio_slice", fake_transcribe_audio_slice)
    monkeypatch.setattr("app.suggestion_engine._request_live_suggestions", fake_request_live_suggestions)

    start = client.post("/api/session/start", json={"groqApiKey": "test_key"})
    assert start.status_code == 200
    session_id = start.json()["sessionId"]

    for idx in range(2):
        response = client.post(
            f"/api/session/{session_id}/audio-slice",
            files={"file": ("slice.webm", b"fake-bytes", "audio/webm")},
            data={"start_ms": idx * 5000, "end_ms": (idx + 1) * 5000},
        )
        assert response.status_code == 200

    tick = client.post(f"/api/session/{session_id}/tick")
    assert tick.status_code == 200
    payload = tick.json()
    assert len(payload["cards"]) == 3
    for card in payload["cards"]:
        assert card["evidence_chunk_ids"]
