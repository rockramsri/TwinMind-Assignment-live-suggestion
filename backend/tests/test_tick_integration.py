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
    monkeypatch.setattr("app.domain.suggestions.engine._request_live_suggestions", fake_request_live_suggestions)

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


def test_tick_enforces_server_cadence(monkeypatch) -> None:
    client = TestClient(app)

    def fake_transcribe_audio_slice(**kwargs):
        return "Need to decide launch date now."

    def fake_request_live_suggestions(*, api_key, context_payload, prompt_override=None):
        evidence = [item["chunk_id"] for item in context_payload.get("current_window_chunks", [])][:1]
        return {
            "cards": [
                {
                    "card_id": "card_1",
                    "type": "question_to_ask",
                    "title": "Who confirms launch date?",
                    "preview": "Clarify decision owner immediately.",
                    "why_now": "Decision language appears in this window.",
                    "priority": "high",
                    "topic_ids": ["topic_launch"],
                    "evidence_chunk_ids": evidence,
                },
                {
                    "card_id": "card_2",
                    "type": "verify_claim",
                    "title": "Verify dependency dates",
                    "preview": "Check if external blockers were confirmed.",
                    "why_now": "Timeline statement lacked source.",
                    "priority": "medium",
                    "topic_ids": ["topic_launch"],
                    "evidence_chunk_ids": evidence,
                },
                {
                    "card_id": "card_3",
                    "type": "decision_nudge",
                    "title": "Record launch decision",
                    "preview": "Lock a decision with owner and date.",
                    "why_now": "Conversation converged on timing.",
                    "priority": "medium",
                    "topic_ids": ["topic_launch"],
                    "evidence_chunk_ids": evidence,
                },
            ],
            "topic_updates": [],
            "ledger_updates": [],
        }

    monkeypatch.setattr("app.main.transcribe_audio_slice", fake_transcribe_audio_slice)
    monkeypatch.setattr("app.domain.suggestions.engine._request_live_suggestions", fake_request_live_suggestions)
    start = client.post("/api/session/start", json={"groqApiKey": "test_key"})
    session_id = start.json()["sessionId"]
    client.post(
        f"/api/session/{session_id}/audio-slice",
        files={"file": ("slice.webm", b"fake-bytes", "audio/webm")},
        data={"start_ms": 0, "end_ms": 5000},
    )

    first_tick = client.post(f"/api/session/{session_id}/tick")
    assert first_tick.status_code == 200
    second_tick = client.post(f"/api/session/{session_id}/tick")
    assert second_tick.status_code == 200
    assert second_tick.json()["route_decision"]["mode"] == "cadence_hold"


def test_session_config_update_roundtrip() -> None:
    client = TestClient(app)
    start = client.post("/api/session/start", json={"groqApiKey": "test_key"})
    session_id = start.json()["sessionId"]
    updated = client.patch(
        f"/api/session/{session_id}/config",
        json={"live_window_seconds": 35, "tick_cadence_seconds": 45},
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["live_window_seconds"] == 35
    assert payload["tick_cadence_seconds"] == 45


def test_tick_repairs_invalid_evidence_ids(monkeypatch) -> None:
    client = TestClient(app)

    def fake_transcribe_audio_slice(**kwargs):
        return "Discussed budget and launch constraints."

    def fake_request_live_suggestions(*, api_key, context_payload, prompt_override=None):
        return {
            "cards": [
                {
                    "card_id": "bad_1",
                    "type": "question_to_ask",
                    "title": "Clarify assumptions",
                    "preview": "Ask what assumptions were used.",
                    "why_now": "Assumptions were mentioned without detail.",
                    "priority": "high",
                    "topic_ids": ["topic_budget"],
                    "evidence_chunk_ids": ["missing_chunk"],
                },
                {
                    "card_id": "bad_2",
                    "type": "verify_claim",
                    "title": "Verify launch claim",
                    "preview": "Check launch confidence statement.",
                    "why_now": "Confidence statement lacked source.",
                    "priority": "medium",
                    "topic_ids": ["topic_launch"],
                    "evidence_chunk_ids": ["missing_chunk_2"],
                },
                {
                    "card_id": "bad_3",
                    "type": "decision_nudge",
                    "title": "Capture next decision",
                    "preview": "Convert discussion to a concrete decision.",
                    "why_now": "Discussion appears decision-ready.",
                    "priority": "medium",
                    "topic_ids": ["topic_launch"],
                    "evidence_chunk_ids": ["missing_chunk_3"],
                },
            ],
            "topic_updates": [],
            "ledger_updates": [],
        }

    monkeypatch.setattr("app.main.transcribe_audio_slice", fake_transcribe_audio_slice)
    monkeypatch.setattr("app.domain.suggestions.engine._request_live_suggestions", fake_request_live_suggestions)
    session_id = client.post("/api/session/start", json={"groqApiKey": "test_key"}).json()["sessionId"]
    client.post(
        f"/api/session/{session_id}/audio-slice",
        files={"file": ("slice.webm", b"fake-bytes", "audio/webm")},
        data={"start_ms": 0, "end_ms": 5000},
    )
    tick = client.post(f"/api/session/{session_id}/tick")
    assert tick.status_code == 200
    for card in tick.json()["cards"]:
        assert card["evidence_chunk_ids"]
        assert "missing_chunk" not in card["evidence_chunk_ids"][0]
