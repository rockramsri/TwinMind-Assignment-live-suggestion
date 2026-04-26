"use client";

import { useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import { uploadAudioSlice } from "../lib/api";
import { DEFAULT_MEDIA_SLICE_MS, DEFAULT_UI_REFRESH_SECONDS, mergeTranscriptChunks } from "../lib/state";
import { TranscriptChunk } from "../lib/types";

interface UseMeetingRecorderArgs {
  ensureSession: () => Promise<string>;
  runTick: (targetSessionId?: string, force?: boolean) => Promise<void>;
  transcriptChunks: TranscriptChunk[];
  setTranscriptChunks: Dispatch<SetStateAction<TranscriptChunk[]>>;
  setErrorMessage: Dispatch<SetStateAction<string | null>>;
  humanizeError: (error: unknown) => string;
  tickCadenceSeconds?: number | null;
}

export function useMeetingRecorder({
  ensureSession,
  runTick,
  transcriptChunks,
  setTranscriptChunks,
  setErrorMessage,
  humanizeError,
  tickCadenceSeconds
}: UseMeetingRecorderArgs) {
  const [isMeetingActive, setIsMeetingActive] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const sliceCursorMsRef = useRef(0);
  const sliceTimeoutRef = useRef<number | null>(null);
  const tickIntervalRef = useRef<number | null>(null);
  const countdownIntervalRef = useRef<number | null>(null);
  const meetingActiveRef = useRef(false);
  const isStoppingRef = useRef(false);

  useEffect(() => {
    meetingActiveRef.current = isMeetingActive;
  }, [isMeetingActive]);

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

  async function startMeeting(onCountdownReset: () => void, onCountdownTick: () => void) {
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
      onCountdownReset();
      startSingleSliceRecorder();

      const cadenceSeconds = Math.max(
        10,
        Math.min(
          120,
          Math.floor(tickCadenceSeconds && tickCadenceSeconds > 0 ? tickCadenceSeconds : DEFAULT_UI_REFRESH_SECONDS)
        )
      );
      tickIntervalRef.current = window.setInterval(() => {
        void runTick(activeSession);
      }, cadenceSeconds * 1000);

      countdownIntervalRef.current = window.setInterval(() => {
        onCountdownTick();
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

  function toggleMeeting(onCountdownReset: () => void, onCountdownTick: () => void) {
    if (isMeetingActive) {
      stopMeetingResources();
      return;
    }
    void startMeeting(onCountdownReset, onCountdownTick);
  }

  useEffect(() => {
    return () => {
      stopMeetingResources();
    };
  }, []);

  return {
    isMeetingActive,
    toggleMeeting,
    stopMeetingResources
  };
}

