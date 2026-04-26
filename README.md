# twinmind-live-copilot

Live meeting copilot monorepo with:

- **Frontend**: Next.js + React + Tailwind
- **Backend**: FastAPI + Python
- **Models**:
  - STT: `whisper-large-v3` via Groq SDK
  - Suggestions/chat: `openai/gpt-oss-120b` via OpenAI SDK against Groq base URL
- **Memory**:
  - In-memory session state
  - Local embedding service (`BAAI/bge-small-en-v1.5`) + FAISS `IndexFlatIP`
- **No login**, **no persistence across reloads**, **no TTS**, **no LiveKit**, **no LangChain**.

## Product behavior

- Browser records mic audio in 5s slices (`MediaRecorder`).
- Backend transcribes each slice immediately.
- Backend builds rolling 25s logical window.
- Every 30s tick:
  - topic routing (recent-topic score + fallback ranker mode)
  - context packing
  - exactly 3 new live suggestion cards
- Older cards remain visible and clickable.
- Clicking a card opens immediate grounded explanation + card-specific chat.
- Every explanation/chat answer includes transcript citations (`chunk_id` + `[HH:MM:SS–HH:MM:SS]`).
- Session can be exported as JSON from in-memory state.

## Monorepo layout

```text
backend/
  requirements.txt
  .env.example
  app/
  tests/
frontend/
  package.json
  .env.local.example
  app/
  components/
  lib/
```

## Backend setup

1. Create and activate a virtualenv:
   - macOS/Linux:
     - `cd backend`
     - `python3 -m venv .venv`
     - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements.txt`
   - For strict local `BAAI/bge-small-en-v1.5` embeddings, prefer Python 3.12.
     On Python 3.13, the app automatically falls back to deterministic hash embeddings for runtime stability.
3. Set env vars:
   - `cp .env.example .env`
   - update values (especially `GROQ_API_KEY` if desired fallback)
4. Run API:
   - `uvicorn app.main:app --reload --port 8000`

## Frontend setup

1. Install dependencies:
   - `cd frontend`
   - `npm install`
2. Set env vars:
   - `cp .env.local.example .env.local`
   - ensure `NEXT_PUBLIC_API_BASE=http://localhost:8000`
3. Run app:
   - `npm run dev`

## End-to-end run

1. Open the frontend in your browser.
2. Open **Settings**, paste Groq API key, click **Validate + save**.
3. Allow microphone permission.
4. Click **Start meeting**.
5. Verify:
   - transcript chunks append continuously
   - cards refresh every 30 seconds with exactly 3 new cards
   - older cards remain visible
   - selecting a card opens explanation + chat with citations
6. Click **Export JSON** to download current session state.

## Core API endpoints

- `POST /api/session/start`
- `POST /api/session/{session_id}/validate-key`
- `POST /api/session/{session_id}/audio-slice`
- `POST /api/session/{session_id}/tick`
- `GET /api/session/{session_id}/state`
- `POST /api/session/{session_id}/card/{card_id}/open`
- `POST /api/session/{session_id}/card/{card_id}/chat` (streamed)
- `GET /api/session/{session_id}/export`

## Testing

### Backend

From `backend/`:

- `pytest -q`

Includes:

- topic routing threshold tests
- context packer token budget test
- card dedup logic test
- export structure test
- integration test for tick emitting exactly 3 cards with evidence refs

### Frontend

From `frontend/`:

- `npm test`

Includes:

- smoke test for selecting a card and opening the chat panel

## Security and key handling

- User Groq key is accepted from UI settings and kept only in session memory on backend.
- Frontend stores key in React state + `sessionStorage` only (not `localStorage`).
- Backend never writes API keys to disk.
