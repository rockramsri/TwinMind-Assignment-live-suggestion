"use client";

import { useMemo, useState } from "react";

import CardChatPanel from "../components/CardChatPanel";
import SettingsModal from "../components/SettingsModal";
import SuggestionsPanel from "../components/SuggestionsPanel";
import TopBar from "../components/TopBar";
import TranscriptPanel from "../components/TranscriptPanel";
import { useCardChat } from "../hooks/useCardChat";
import { useMeetingRecorder } from "../hooks/useMeetingRecorder";
import { useSessionLifecycle } from "../hooks/useSessionLifecycle";
import { useSuggestionRefresh } from "../hooks/useSuggestionRefresh";
import {
  DEFAULT_UI_REFRESH_SECONDS,
  splitCurrentAndOlderCards,
  transcriptStreamByThirtySeconds
} from "../lib/state";
import { SuggestionBatch, SuggestionCard, TranscriptChunk } from "../lib/types";

function humanizeError(error: unknown): string {
  if (error instanceof Error) {
    if (error.message.includes("No Groq key")) {
      return "No key configured. Paste and validate your Groq key in settings.";
    }
    if (error.message.toLowerCase().includes("stt")) {
      return "Transcription failed on a recent slice.";
    }
    if (error.message.toLowerCase().includes("timeout")) {
      return "The model timed out. Try manual refresh.";
    }
    return error.message;
  }
  return "Unexpected error";
}

function isSessionNotFound(error: unknown): boolean {
  return error instanceof Error && error.message.toLowerCase().includes("session not found");
}

function keywordTokens(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((token) => token.length > 3)
  );
}

function isCardCoveredByTranscript(card: SuggestionCard, chunks: TranscriptChunk[]): boolean {
  // Card materialization timestamp is later than the transcript that inspired the
  // card, so we look at all transcript chunks rather than only those newer than the
  // card. To avoid false positives we still require either a clear overlap or a
  // moderate overlap with a spoken-resolution signal.
  const transcriptText = chunks.map((chunk) => chunk.text).join(" ").toLowerCase();
  if (!transcriptText.trim()) {
    return false;
  }
  const intentTokens = keywordTokens(`${card.title} ${card.preview}`);
  const transcriptTokens = keywordTokens(transcriptText);
  if (!intentTokens.size || !transcriptTokens.size) {
    return false;
  }
  const overlap =
    [...intentTokens].filter((token) => transcriptTokens.has(token)).length /
    Math.max(1, intentTokens.size);
  const spokenUsageSignals = [
    "could you",
    "can you",
    "what are",
    "explain",
    "tell me",
    "i asked",
    "we asked",
    "we covered",
    "we discussed",
    "as i said",
    "as we discussed",
    "answered",
    "addressed",
    "thank you",
    "thanks"
  ];
  return overlap >= 0.65 || (overlap >= 0.4 && spokenUsageSignals.some((signal) => transcriptText.includes(signal)));
}

export default function HomePage() {
  const [transcriptChunks, setTranscriptChunks] = useState<TranscriptChunk[]>([]);
  const [suggestionBatches, setSuggestionBatches] = useState<SuggestionBatch[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [usedCardIds, setUsedCardIds] = useState<Set<string>>(() => new Set());
  const [settingsOpen, setSettingsOpen] = useState(false);

  const {
    sessionId,
    setSessionId,
    groqKey,
    setGroqKey,
    sessionConfig,
    hydrateSessionState,
    ensureSession,
    handleValidateKey,
    handleSaveSessionConfig,
    handleExport
  } = useSessionLifecycle(
    humanizeError,
    setTranscriptChunks,
    setSuggestionBatches,
    setErrorMessage
  );

  const {
    countdown: refreshCountdown,
    setCountdown: setRefreshCountdown,
    isRefreshing,
    lastRefreshMs: measuredLastRefreshMs,
    runTick
  } = useSuggestionRefresh({
    sessionId,
    groqKey,
    humanizeError,
    isSessionNotFound,
    onSessionRestart: async () => {
      const restarted = await ensureSession();
      setSessionId(restarted);
      await hydrateSessionState(restarted);
      return restarted;
    },
    setTranscriptChunks,
    setSuggestionBatches,
    setErrorMessage
  });

  const {
    isMeetingActive,
    toggleMeeting
  } = useMeetingRecorder({
    ensureSession,
    runTick,
    transcriptChunks,
    setTranscriptChunks,
    setErrorMessage,
    humanizeError,
    tickCadenceSeconds: sessionConfig?.tick_cadence_seconds ?? null
  });

  const {
    selectedCardId,
    loadingCardId,
    sendingCardId,
    selectedCard,
    selectedThread,
    handleCardSelect,
    handleSendCardMessage
  } = useCardChat({
    sessionId,
    suggestionBatches,
    humanizeError,
    setErrorMessage,
    setUsedCardIds
  });

  const countdownValue = refreshCountdown;
  const refreshDurationMs = measuredLastRefreshMs;

  const transcriptEntries = useMemo(
    () => transcriptStreamByThirtySeconds(transcriptChunks),
    [transcriptChunks]
  );
  const { current: currentCards, older: olderCards } = useMemo(
    () => splitCurrentAndOlderCards(suggestionBatches),
    [suggestionBatches]
  );
  const coveredCardIds = useMemo(() => {
    const ids = new Set<string>();
    for (const card of [...currentCards, ...olderCards]) {
      if (usedCardIds.has(card.card_id) || isCardCoveredByTranscript(card, transcriptChunks)) {
        ids.add(card.card_id);
      }
    }
    return ids;
  }, [currentCards, olderCards, transcriptChunks, usedCardIds]);

  return (
    <main className="flex h-screen flex-col">
      <TopBar
        isMeetingActive={isMeetingActive}
        countdown={countdownValue}
        onStartStop={() =>
          toggleMeeting(
            () => setRefreshCountdown(DEFAULT_UI_REFRESH_SECONDS),
            () =>
              setRefreshCountdown((current) =>
                current <= 1 ? DEFAULT_UI_REFRESH_SECONDS : current - 1
              )
          )
        }
        onOpenSettings={() => setSettingsOpen(true)}
        onExport={() => void handleExport()}
        onRefresh={() => void runTick(undefined, true)}
        disableActions={!sessionId}
        isRefreshing={isRefreshing}
        lastRefreshMs={refreshDurationMs}
      />

      {errorMessage ? (
        <div className="border-b border-rose-700/60 bg-rose-950/60 px-4 py-2 text-sm text-rose-100">
          {errorMessage}
        </div>
      ) : null}

      <div className="grid min-h-0 flex-1 grid-cols-12">
        <div className="col-span-3 min-h-0">
          <TranscriptPanel entries={transcriptEntries} />
        </div>
        <div className="col-span-4 min-h-0">
          <SuggestionsPanel
            currentCards={currentCards}
            olderCards={olderCards}
            selectedCardId={selectedCardId}
            coveredCardIds={coveredCardIds}
            onSelectCard={(card) => void handleCardSelect(card)}
          />
        </div>
        <div className="col-span-5 min-h-0">
          <CardChatPanel
            selectedCard={selectedCard}
            thread={selectedThread}
            isLoadingOpen={selectedCardId === loadingCardId}
            isSending={selectedCardId === sendingCardId}
            onSend={handleSendCardMessage}
          />
        </div>
      </div>

      <SettingsModal
        open={settingsOpen}
        initialKey={groqKey}
        onClose={() => setSettingsOpen(false)}
        onValidate={handleValidateKey}
        onSave={(key) => {
          setGroqKey(key);
          sessionStorage.setItem("twinmind_groq_key", key);
        }}
        sessionConfig={sessionConfig}
        onSaveConfig={handleSaveSessionConfig}
      />
    </main>
  );
}
