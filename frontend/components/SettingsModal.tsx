"use client";

import { useEffect, useState } from "react";
import { SessionConfig } from "../lib/types";

interface SettingsModalProps {
  open: boolean;
  initialKey: string;
  onClose: () => void;
  onValidate: (key: string) => Promise<{ valid: boolean; message: string }>;
  onSave: (key: string) => void;
  sessionConfig: SessionConfig | null;
  onSaveConfig: (nextConfig: Partial<SessionConfig>) => Promise<void>;
}

interface LabelWithInfoProps {
  label: string;
  hint: string;
}

function LabelWithInfo({ label, hint }: LabelWithInfoProps) {
  return (
    <div className="mb-1 flex items-center gap-1">
      <span className="text-xs text-slate-200">{label}</span>
      <span
        title={hint}
        className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-panelBorder bg-panel text-[10px] font-semibold text-slate-300"
        aria-label={`${label} info`}
      >
        i
      </span>
    </div>
  );
}

export default function SettingsModal({
  open,
  initialKey,
  onClose,
  onValidate,
  onSave,
  sessionConfig,
  onSaveConfig
}: SettingsModalProps) {
  const [keyInput, setKeyInput] = useState(initialKey);
  const [statusMessage, setStatusMessage] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [configDraft, setConfigDraft] = useState<SessionConfig | null>(sessionConfig);
  const [isSavingConfig, setIsSavingConfig] = useState(false);

  useEffect(() => {
    setKeyInput(initialKey);
    setConfigDraft(sessionConfig);
  }, [initialKey, open, sessionConfig]);

  if (!open) {
    return null;
  }

  async function handleValidate() {
    const key = keyInput.trim();
    if (!key) {
      setStatusMessage("Enter a Groq API key first.");
      return;
    }
    setIsValidating(true);
    try {
      const result = await onValidate(key);
      setStatusMessage(result.message);
      if (result.valid) {
        onSave(key);
      }
    } finally {
      setIsValidating(false);
    }
  }

  async function handleSaveConfig() {
    if (!configDraft) {
      return;
    }
    setIsSavingConfig(true);
    try {
      await onSaveConfig(configDraft);
      setStatusMessage("Session config updated.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Config update failed";
      setStatusMessage(message);
    } finally {
      setIsSavingConfig(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-xl rounded-lg border border-panelBorder bg-panel p-4 shadow-xl">
        <div className="mb-3 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">Settings</h2>
            <p className="text-xs text-slate-400">
              Key is kept in React state/sessionStorage only and never persisted server-side.
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-sm text-slate-300 hover:text-white">
            Close
          </button>
        </div>

        <label htmlFor="groq-key" className="mb-1 block text-sm text-slate-200">
          <span className="inline-flex items-center gap-1">
            Groq API key
            <span
              title="Used for Groq STT and LLM calls in this session. Stored only in browser session state and backend in-memory session."
              className="inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-panelBorder bg-panel text-[10px] font-semibold text-slate-300"
              aria-label="Groq API key info"
            >
              i
            </span>
          </span>
        </label>
        <input
          id="groq-key"
          type="password"
          autoComplete="off"
          value={keyInput}
          onChange={(event) => setKeyInput(event.target.value)}
          className="w-full rounded-md border border-panelBorder bg-panelSoft px-3 py-2 text-sm text-slate-100 outline-none focus:border-accentStrong"
          placeholder="gsk_..."
        />
        <div className="mt-3 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={handleValidate}
            disabled={isValidating}
            className="rounded-md border border-panelBorder bg-panelSoft px-3 py-2 text-sm text-slate-100 disabled:opacity-50"
          >
            {isValidating ? "Validating..." : "Validate + save"}
          </button>
        </div>
        {configDraft ? (
          <div className="mt-4 space-y-3 rounded-md border border-panelBorder bg-panelSoft p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">
              Prompt and context controls
            </p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <LabelWithInfo
                  label="Live window (s)"
                  hint="How many recent transcript seconds are treated as the active live context for suggestion generation."
                />
                <input
                  type="number"
                  className="w-full rounded border border-panelBorder bg-panel px-2 py-1 text-xs text-slate-100"
                  value={configDraft.live_window_seconds}
                  onChange={(event) =>
                    setConfigDraft({
                      ...configDraft,
                      live_window_seconds: Number(event.target.value || 25)
                    })
                  }
                  placeholder="Live window (s)"
                />
              </div>
              <div>
                <LabelWithInfo
                  label="Tick cadence (s)"
                  hint="Minimum server interval between full suggestion generations. Manual refresh can still force a generation."
                />
                <input
                  type="number"
                  className="w-full rounded border border-panelBorder bg-panel px-2 py-1 text-xs text-slate-100"
                  value={configDraft.tick_cadence_seconds}
                  onChange={(event) =>
                    setConfigDraft({
                      ...configDraft,
                      tick_cadence_seconds: Number(event.target.value || 30)
                    })
                  }
                  placeholder="Tick cadence (s)"
                />
              </div>
              <div>
                <LabelWithInfo
                  label="Live context token cap"
                  hint="Approx token budget for context passed to the model when generating the 3 live suggestion cards."
                />
                <input
                  type="number"
                  className="w-full rounded border border-panelBorder bg-panel px-2 py-1 text-xs text-slate-100"
                  value={configDraft.live_context_token_cap}
                  onChange={(event) =>
                    setConfigDraft({
                      ...configDraft,
                      live_context_token_cap: Number(event.target.value || 1500)
                    })
                  }
                  placeholder="Live context token cap"
                />
              </div>
              <div>
                <LabelWithInfo
                  label="Chat context token cap"
                  hint="Approx token budget for context passed to the model for selected-card detailed chat answers."
                />
                <input
                  type="number"
                  className="w-full rounded border border-panelBorder bg-panel px-2 py-1 text-xs text-slate-100"
                  value={configDraft.chat_context_token_cap}
                  onChange={(event) =>
                    setConfigDraft({
                      ...configDraft,
                      chat_context_token_cap: Number(event.target.value || 6000)
                    })
                  }
                  placeholder="Chat context token cap"
                />
              </div>
            </div>
            <div>
              <LabelWithInfo
                label="Live suggestions prompt override"
                hint="Optional system-prompt override used for center-panel card generation. Leave empty to use app defaults."
              />
            <textarea
              rows={3}
              className="w-full rounded border border-panelBorder bg-panel px-2 py-1 text-xs text-slate-100"
              value={configDraft.live_suggestions_prompt ?? ""}
              onChange={(event) =>
                setConfigDraft({
                  ...configDraft,
                  live_suggestions_prompt: event.target.value
                })
              }
              placeholder="Live suggestions prompt override"
            />
            </div>
            <div>
              <LabelWithInfo
                label="Card detail prompt override"
                hint="Optional prompt override used when opening a selected card for its first grounded detailed answer."
              />
            <textarea
              rows={3}
              className="w-full rounded border border-panelBorder bg-panel px-2 py-1 text-xs text-slate-100"
              value={configDraft.card_detail_prompt ?? ""}
              onChange={(event) =>
                setConfigDraft({
                  ...configDraft,
                  card_detail_prompt: event.target.value
                })
              }
              placeholder="Card detail prompt override"
            />
            </div>
            <div>
              <LabelWithInfo
                label="Card chat prompt override"
                hint="Optional prompt override used for right-panel follow-up chat turns after a card is opened."
              />
            <textarea
              rows={3}
              className="w-full rounded border border-panelBorder bg-panel px-2 py-1 text-xs text-slate-100"
              value={configDraft.card_chat_prompt ?? ""}
              onChange={(event) =>
                setConfigDraft({
                  ...configDraft,
                  card_chat_prompt: event.target.value
                })
              }
              placeholder="Card chat prompt override"
            />
            </div>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={handleSaveConfig}
                disabled={isSavingConfig}
                className="rounded-md border border-panelBorder bg-panel px-3 py-1 text-xs text-slate-100 disabled:opacity-50"
              >
                {isSavingConfig ? "Saving..." : "Save prompt/context config"}
              </button>
            </div>
          </div>
        ) : null}
        {statusMessage ? (
          <p className="mt-3 rounded-md border border-panelBorder bg-panelSoft px-3 py-2 text-xs text-slate-200">
            {statusMessage}
          </p>
        ) : null}
      </div>
    </div>
  );
}
