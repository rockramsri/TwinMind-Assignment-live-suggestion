"use client";

import { useCallback, useEffect, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import {
  exportSession,
  getSessionState,
  startSession,
  updateSessionConfig,
  validateGroqKey
} from "../lib/api";
import { SessionConfig, SuggestionBatch, SuggestionCard, TranscriptChunk } from "../lib/types";

interface SessionLifecycleResult {
  sessionId: string | null;
  setSessionId: (value: string | null) => void;
  groqKey: string;
  setGroqKey: (value: string) => void;
  sessionConfig: SessionConfig | null;
  setSessionConfig: (value: SessionConfig | null) => void;
  hydrateSessionState: (id: string) => Promise<void>;
  ensureSession: () => Promise<string>;
  handleValidateKey: (key: string) => Promise<{ valid: boolean; message: string }>;
  handleSaveSessionConfig: (nextConfig: Partial<SessionConfig>) => Promise<void>;
  handleExport: () => Promise<void>;
}

export function useSessionLifecycle(
  humanizeError: (error: unknown) => string,
  setTranscriptChunks: Dispatch<SetStateAction<TranscriptChunk[]>>,
  setSuggestionBatches: Dispatch<SetStateAction<SuggestionBatch[]>>,
  setErrorMessage: Dispatch<SetStateAction<string | null>>
): SessionLifecycleResult {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [groqKey, setGroqKey] = useState("");
  const [sessionConfig, setSessionConfig] = useState<SessionConfig | null>(null);

  useEffect(() => {
    const key = sessionStorage.getItem("twinmind_groq_key") ?? "";
    setGroqKey(key);
  }, []);

  const hydrateSessionState = useCallback(async (id: string) => {
    const state = await getSessionState(id);
    setTranscriptChunks(state.transcript_chunks);
    setSuggestionBatches(
      state.suggestion_batches.map((batch) => ({
        batch_id: String(batch.batch_id),
        created_at_ms: Number(batch.created_at_ms),
        window_start_ms: Number(batch.window_start_ms),
        window_end_ms: Number(batch.window_end_ms),
        cards: (batch.cards as SuggestionCard[]) ?? [],
        route_decision: (batch.route_decision as Record<string, unknown>) ?? {}
      }))
    );
    setSessionConfig(state.session_config);
  }, [setSuggestionBatches, setTranscriptChunks]);

  const ensureSession = useCallback(async () => {
    if (sessionId) {
      return sessionId;
    }
    const started = await startSession(groqKey || undefined);
    setSessionId(started.sessionId);
    await hydrateSessionState(started.sessionId);
    return started.sessionId;
  }, [groqKey, hydrateSessionState, sessionId]);

  const handleValidateKey = useCallback(async (key: string) => {
    try {
      const started = sessionId ? null : await startSession(key);
      const activeSession = sessionId ?? started?.sessionId ?? "";
      if (!sessionId) {
        setSessionId(activeSession);
        await hydrateSessionState(activeSession);
      }
      const result = await validateGroqKey(activeSession, key);
      if (result.valid) {
        setGroqKey(key);
        sessionStorage.setItem("twinmind_groq_key", key);
        setErrorMessage(null);
      }
      return result;
    } catch (error) {
      return { valid: false, message: humanizeError(error) };
    }
  }, [humanizeError, hydrateSessionState, sessionId, setErrorMessage]);

  const handleSaveSessionConfig = useCallback(async (nextConfig: Partial<SessionConfig>) => {
    if (!sessionId) {
      throw new Error("Start a session before updating config.");
    }
    const updated = await updateSessionConfig(sessionId, nextConfig);
    setSessionConfig(updated);
  }, [sessionId]);

  const handleExport = useCallback(async () => {
    if (!sessionId) {
      setErrorMessage("Start a session before exporting.");
      return;
    }
    try {
      const blob = await exportSession(sessionId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `session-${sessionId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(humanizeError(error));
    }
  }, [humanizeError, sessionId, setErrorMessage]);

  return {
    sessionId,
    setSessionId,
    groqKey,
    setGroqKey,
    sessionConfig,
    setSessionConfig,
    hydrateSessionState,
    ensureSession,
    handleValidateKey,
    handleSaveSessionConfig,
    handleExport
  };
}

