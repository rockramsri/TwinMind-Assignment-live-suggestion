"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import CardChatPanel from "../components/CardChatPanel";
import SettingsModal from "../components/SettingsModal";
import SuggestionsPanel from "../components/SuggestionsPanel";
import TopBar from "../components/TopBar";
import TranscriptPanel from "../components/TranscriptPanel";
import {
  exportSession,
  getSessionState,
  openCard,
  startSession,
  streamCardChat,
  tickSession,
  uploadAudioSlice,
  validateGroqKey
} from "../lib/api";
import {
  DEFAULT_MEDIA_SLICE_MS,
  DEFAULT_UI_REFRESH_SECONDS,
  mergeTranscriptChunks,
  splitCurrentAndOlderCards,
  transcriptStreamByThirtySeconds
} from "../lib/state";
import { CardThreadMessage, SuggestionBatch, SuggestionCard, TranscriptChunk } from "../lib/types";

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

export default function HomePage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [groqKey, setGroqKey] = useState("");
  const [isMeetingActive, setIsMeetingActive] = useState(false);
  const [countdown, setCountdown] = useState(DEFAULT_UI_REFRESH_SECONDS);
  const [transcriptChunks, setTranscriptChunks] = useState<TranscriptChunk[]>([]);
  const [suggestionBatches, setSuggestionBatches] = useState<SuggestionBatch[]>([]);
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const [threadsByCard, setThreadsByCard] = useState<Record<string, CardThreadMessage[]>>({});
  const [loadingCardId, setLoadingCardId] = useState<string | null>(null);
  const [sendingCardId, setSendingCardId] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const sliceCursorMsRef = useRef(0);
  const sliceTimeoutRef = useRef<number | null>(null);
  const tickIntervalRef = useRef<number | null>(null);
  const countdownIntervalRef = useRef<number | null>(null);
  const meetingActiveRef = useRef(false);
  const isStoppingRef = useRef(false);

  useEffect(() => {
    const key = sessionStorage.getItem("twinmind_groq_key") ?? "";
    setGroqKey(key);
  }, []);

  useEffect(() => {
    meetingActiveRef.current = isMeetingActive;
  }, [isMeetingActive]);

  useEffect(() => {
    return () => {
      stopMeetingResources();
    };
  }, []);

  async function hydrateSessionState(id: string) {
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
  }

  async function ensureSession(): Promise<string> {
    if (sessionId) {
      return sessionId;
    }
    const started = await startSession(groqKey || undefined);
    setSessionId(started.sessionId);
    await hydrateSessionState(started.sessionId);
    return started.sessionId;
  }

  function stopMeetingResources() {
    isStoppingRef.current = true;
    if (tickIntervalRef.current !== null) {
      window.clearInterval(tickIntervalRef.current);
      tickIntervalRef.current = null;
    }
    if (countdownIntervalRef.current !== null) {
      window.clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    if (sliceTimeoutRef.current !== null) {
      window.clearTimeout(sliceTimeoutRef.current);
      sliceTimeoutRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    mediaRecorderRef.current = null;

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
    }
    mediaStreamRef.current = null;
    meetingActiveRef.current = false;
    setIsMeetingActive(false);
  }

  async function runTick(targetSessionId?: string) {
    const activeSession = targetSessionId ?? sessionId;
    if (!activeSession) {
      return;
    }
    try {
      const tick = await tickSession(activeSession);
      setTranscriptChunks((current) => mergeTranscriptChunks(current, tick.transcript_append));
      const newBatch: SuggestionBatch = {
        batch_id: `batch_${Date.now()}`,
        created_at_ms: Date.now(),
        window_start_ms: Number((tick.route_decision.window_start_ms as number) ?? 0),
        window_end_ms: Number((tick.route_decision.window_end_ms as number) ?? 0),
        cards: tick.cards,
        route_decision: tick.route_decision
      };
      setSuggestionBatches((current) => [newBatch, ...current]);
      if (tick.route_decision.mode === "empty_window") {
        setErrorMessage("Current window is mostly silent; cards may rely on unresolved context.");
      } else {
        setErrorMessage(null);
      }
    } catch (error) {
      setErrorMessage(humanizeError(error));
    } finally {
      setCountdown(DEFAULT_UI_REFRESH_SECONDS);
    }
  }

  async function startMeeting() {
    if (!groqKey.trim()) {
      setErrorMessage("No key configured. Open settings and validate your Groq key first.");
      setSettingsOpen(true);
      return;
    }
    try {
      const activeSession = await ensureSession();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      isStoppingRef.current = false;
      const mimeCandidates = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
        "audio/ogg;codecs=opus"
      ];
      const supportedMimes = mimeCandidates.filter((item) => MediaRecorder.isTypeSupported(item));

      sliceCursorMsRef.current = transcriptChunks.length
        ? Math.max(...transcriptChunks.map((chunk) => chunk.end_ms))
        : 0;

      const startSingleSliceRecorder = () => {
        if (!meetingActiveRef.current || isStoppingRef.current || !mediaStreamRef.current) {
          return;
        }
        const startMs = sliceCursorMsRef.current;
        const recorder = supportedMimes.length
          ? new MediaRecorder(mediaStreamRef.current, { mimeType: supportedMimes[0] })
          : new MediaRecorder(mediaStreamRef.current);
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = async (event) => {
          if (event.data.size === 0) {
            return;
          }
          const endMs = startMs + DEFAULT_MEDIA_SLICE_MS;
          sliceCursorMsRef.current = endMs;
          try {
            const chunk = await uploadAudioSlice(activeSession, event.data, startMs, endMs);
            setTranscriptChunks((current) => mergeTranscriptChunks(current, [chunk]));
          } catch (error) {
            setErrorMessage(humanizeError(error));
          }
        };

        recorder.onstop = () => {
          if (sliceTimeoutRef.current !== null) {
            window.clearTimeout(sliceTimeoutRef.current);
            sliceTimeoutRef.current = null;
          }
          if (meetingActiveRef.current && !isStoppingRef.current) {
            startSingleSliceRecorder();
          }
        };

        recorder.start();
        sliceTimeoutRef.current = window.setTimeout(() => {
          if (recorder.state === "recording") {
            recorder.stop();
          }
        }, DEFAULT_MEDIA_SLICE_MS);
      };

      meetingActiveRef.current = true;
      setIsMeetingActive(true);
      setErrorMessage(null);
      setCountdown(DEFAULT_UI_REFRESH_SECONDS);
      startSingleSliceRecorder();

      tickIntervalRef.current = window.setInterval(() => {
        void runTick(activeSession);
      }, DEFAULT_UI_REFRESH_SECONDS * 1000);

      countdownIntervalRef.current = window.setInterval(() => {
        setCountdown((current) => (current <= 1 ? DEFAULT_UI_REFRESH_SECONDS : current - 1));
      }, 1000);
    } catch (error) {
      const message =
        error instanceof DOMException && error.name === "NotAllowedError"
          ? "Microphone permission denied."
          : humanizeError(error);
      setErrorMessage(message);
      stopMeetingResources();
    }
  }

  function toggleMeeting() {
    if (isMeetingActive) {
      stopMeetingResources();
      return;
    }
    void startMeeting();
  }

  async function handleCardSelect(card: SuggestionCard) {
    setSelectedCardId(card.card_id);
    if (!sessionId) {
      return;
    }
    if (threadsByCard[card.card_id]?.length) {
      return;
    }
    setLoadingCardId(card.card_id);
    try {
      const opened = await openCard(sessionId, card.card_id);
      setThreadsByCard((current) => ({
        ...current,
        [card.card_id]:
          opened.thread.length > 0
            ? opened.thread
            : [
                {
                  role: "assistant",
                  text: opened.explanation,
                  created_at_ms: Date.now()
                }
              ]
      }));
    } catch (error) {
      setErrorMessage(humanizeError(error));
    } finally {
      setLoadingCardId(null);
    }
  }

  async function handleSendCardMessage(message: string) {
    if (!sessionId || !selectedCardId) {
      return;
    }
    setSendingCardId(selectedCardId);
    const assistantPlaceholder: CardThreadMessage = {
      role: "assistant",
      text: "",
      created_at_ms: Date.now()
    };
    setThreadsByCard((current) => ({
      ...current,
      [selectedCardId]: [
        ...(current[selectedCardId] ?? []),
        { role: "user", text: message, created_at_ms: Date.now() },
        assistantPlaceholder
      ]
    }));

    try {
      await streamCardChat(sessionId, selectedCardId, message, (chunk) => {
        setThreadsByCard((current) => {
          const nextThread = [...(current[selectedCardId] ?? [])];
          const assistantIndex = [...nextThread]
            .reverse()
            .findIndex((entry) => entry.role === "assistant");
          if (assistantIndex < 0) {
            return current;
          }
          const actualIndex = nextThread.length - 1 - assistantIndex;
          nextThread[actualIndex] = {
            ...nextThread[actualIndex],
            text: `${nextThread[actualIndex].text}${chunk}`
          };
          return { ...current, [selectedCardId]: nextThread };
        });
      });
    } catch (error) {
      setErrorMessage(humanizeError(error));
    } finally {
      setSendingCardId(null);
    }
  }

  async function handleExport() {
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
  }

  async function handleValidateKey(key: string): Promise<{ valid: boolean; message: string }> {
    try {
      const activeSession = sessionId ?? (await startSession(key)).sessionId;
      if (!sessionId) {
        setSessionId(activeSession);
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
  }

  const transcriptEntries = useMemo(
    () => transcriptStreamByThirtySeconds(transcriptChunks),
    [transcriptChunks]
  );
  const { current: currentCards, older: olderCards } = useMemo(
    () => splitCurrentAndOlderCards(suggestionBatches),
    [suggestionBatches]
  );
  const selectedCard = useMemo(() => {
    const cards = [...currentCards, ...olderCards];
    return cards.find((card) => card.card_id === selectedCardId) ?? null;
  }, [currentCards, olderCards, selectedCardId]);
  const selectedThread = selectedCardId ? threadsByCard[selectedCardId] ?? [] : [];

  return (
    <main className="flex h-screen flex-col">
      <TopBar
        isMeetingActive={isMeetingActive}
        countdown={countdown}
        onStartStop={toggleMeeting}
        onOpenSettings={() => setSettingsOpen(true)}
        onExport={() => void handleExport()}
        onRefresh={() => void runTick()}
        disableActions={!sessionId}
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
      />
    </main>
  );
}
