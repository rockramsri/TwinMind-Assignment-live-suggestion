import {
  CardOpenResponse,
  SessionConfig,
  SessionState,
  TickResponse,
  TranscriptChunk
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function parseJsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export async function startSession(groqApiKey?: string): Promise<{ sessionId: string }> {
  const response = await fetch(`${API_BASE}/api/session/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ groqApiKey })
  });
  return parseJsonOrThrow(response);
}

export async function validateGroqKey(
  sessionId: string,
  groqApiKey: string
): Promise<{ valid: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}/validate-key`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ groqApiKey })
  });
  return parseJsonOrThrow(response);
}

export async function uploadAudioSlice(
  sessionId: string,
  blob: Blob,
  startMs: number,
  endMs: number
): Promise<TranscriptChunk> {
  const form = new FormData();
  const mime = (blob.type || "").toLowerCase();
  const extension = mime.includes("mp4")
    ? "m4a"
    : mime.includes("ogg")
      ? "ogg"
      : mime.includes("wav")
        ? "wav"
        : "webm";
  form.append("file", blob, `slice.${extension}`);
  form.append("start_ms", String(startMs));
  form.append("end_ms", String(endMs));

  const response = await fetch(`${API_BASE}/api/session/${sessionId}/audio-slice`, {
    method: "POST",
    body: form
  });
  return parseJsonOrThrow(response);
}

export async function tickSession(sessionId: string, force = false): Promise<TickResponse> {
  const suffix = force ? "?force=true" : "";
  const response = await fetch(`${API_BASE}/api/session/${sessionId}/tick${suffix}`, {
    method: "POST"
  });
  return parseJsonOrThrow(response);
}

export async function updateSessionConfig(
  sessionId: string,
  payload: Partial<SessionConfig>
): Promise<SessionConfig> {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}/config`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseJsonOrThrow(response);
}

export async function getSessionState(sessionId: string): Promise<SessionState> {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}/state`, {
    method: "GET"
  });
  return parseJsonOrThrow(response);
}

export async function openCard(
  sessionId: string,
  cardId: string
): Promise<CardOpenResponse> {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}/card/${cardId}/open`, {
    method: "POST"
  });
  return parseJsonOrThrow(response);
}

export async function streamCardChat(
  sessionId: string,
  cardId: string,
  message: string,
  onChunk: (chunk: string) => void
): Promise<string> {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}/card/${cardId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message })
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Chat request failed");
  }
  if (!response.body) {
    throw new Error("Chat stream missing response body");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let finalText = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    const textChunk = decoder.decode(value, { stream: true });
    if (!textChunk) {
      continue;
    }
    finalText += textChunk;
    onChunk(textChunk);
  }
  return finalText;
}

export async function exportSession(sessionId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/session/${sessionId}/export`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Export failed");
  }
  return response.blob();
}
