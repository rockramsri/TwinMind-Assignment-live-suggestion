"use client";

import { useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import { tickSession } from "../lib/api";
import { DEFAULT_UI_REFRESH_SECONDS, mergeTranscriptChunks } from "../lib/state";
import { SuggestionBatch, TranscriptChunk } from "../lib/types";

interface UseSuggestionRefreshArgs {
  sessionId: string | null;
  groqKey: string;
  humanizeError: (error: unknown) => string;
  isSessionNotFound: (error: unknown) => boolean;
  onSessionRestart: () => Promise<string>;
  setTranscriptChunks: Dispatch<SetStateAction<TranscriptChunk[]>>;
  setSuggestionBatches: Dispatch<SetStateAction<SuggestionBatch[]>>;
  setErrorMessage: Dispatch<SetStateAction<string | null>>;
}

interface PendingTickRequest {
  targetSessionId?: string;
  force: boolean;
}

export function useSuggestionRefresh({
  sessionId,
  groqKey,
  humanizeError,
  isSessionNotFound,
  onSessionRestart,
  setTranscriptChunks,
  setSuggestionBatches,
  setErrorMessage
}: UseSuggestionRefreshArgs) {
  const [countdown, setCountdown] = useState(DEFAULT_UI_REFRESH_SECONDS);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshMs, setLastRefreshMs] = useState<number | null>(null);
  const [lastTickMode, setLastTickMode] = useState<string | null>(null);
  const [cadenceHoldSecondsRemaining, setCadenceHoldSecondsRemaining] =
    useState<number | null>(null);
  const tickInFlightRef = useRef(false);
  const pendingTickRef = useRef<PendingTickRequest | null>(null);

  function applyTickResponse(tick: Awaited<ReturnType<typeof tickSession>>) {
    setTranscriptChunks((current) => mergeTranscriptChunks(current, tick.transcript_append));
    const mode = (tick.route_decision.mode as string) ?? null;
    setLastTickMode(mode);
    if (mode === "cadence_hold") {
      const secondsUntilNext = Number(
        (tick.route_decision.seconds_until_next as number) ?? DEFAULT_UI_REFRESH_SECONDS
      );
      const clamped = Math.max(1, Math.ceil(secondsUntilNext));
      setCadenceHoldSecondsRemaining(clamped);
      // Align UI countdown with server cadence so the timer reflects
      // when a real generation will happen next.
      setCountdown(Math.min(DEFAULT_UI_REFRESH_SECONDS, clamped));
      setErrorMessage(null);
      return;
    }
    setCadenceHoldSecondsRemaining(null);
    const tickWindowStart = Number(
      tick.window_start_ms ?? (tick.route_decision.window_start_ms as number) ?? 0
    );
    const tickWindowEnd = Number(
      tick.window_end_ms ?? (tick.route_decision.window_end_ms as number) ?? 0
    );
    const newBatch: SuggestionBatch = {
      batch_id: `batch_${Date.now()}`,
      created_at_ms: Date.now(),
      window_start_ms: tickWindowStart,
      window_end_ms: tickWindowEnd,
      cards: tick.cards,
      route_decision: tick.route_decision
    };
    setSuggestionBatches((current) => [newBatch, ...current]);
    if (mode === "empty_window") {
      setErrorMessage("Current window is mostly silent; cards may rely on unresolved context.");
    } else {
      setErrorMessage(null);
    }
  }

  async function runTick(targetSessionId?: string, force = false) {
    const activeSession = targetSessionId ?? sessionId;
    if (!activeSession) {
      return;
    }
    if (tickInFlightRef.current) {
      // Queue at most one follow-up tick. Force takes priority over a non-force pending.
      const existing = pendingTickRef.current;
      if (!existing || (force && !existing.force)) {
        pendingTickRef.current = { targetSessionId, force };
      }
      return;
    }
    const startedAt = performance.now();
    tickInFlightRef.current = true;
    if (force) {
      setIsRefreshing(true);
    }
    try {
      const tick = await tickSession(activeSession, force);
      applyTickResponse(tick);
      if (tick.route_decision.mode !== "cadence_hold") {
        setCountdown(DEFAULT_UI_REFRESH_SECONDS);
      }
    } catch (error) {
      if (isSessionNotFound(error) && groqKey.trim()) {
        try {
          const restartedSessionId = await onSessionRestart();
          const tick = await tickSession(restartedSessionId, true);
          applyTickResponse(tick);
          setCountdown(DEFAULT_UI_REFRESH_SECONDS);
          return;
        } catch (retryError) {
          setErrorMessage(humanizeError(retryError));
          return;
        }
      }
      setErrorMessage(humanizeError(error));
    } finally {
      setLastRefreshMs(Math.round(performance.now() - startedAt));
      tickInFlightRef.current = false;
      if (force) {
        setIsRefreshing(false);
      }
      const pending = pendingTickRef.current;
      pendingTickRef.current = null;
      if (pending) {
        // Run the queued tick after the current one resolves so we never silently
        // drop a scheduled 30s refresh because a previous tick was still running.
        void runTick(pending.targetSessionId, pending.force);
      }
    }
  }

  return {
    countdown,
    setCountdown,
    isRefreshing,
    lastRefreshMs,
    runTick,
    lastTickMode,
    cadenceHoldSecondsRemaining
  };
}
