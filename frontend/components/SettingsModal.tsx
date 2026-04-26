"use client";

import { useEffect, useState } from "react";

interface SettingsModalProps {
  open: boolean;
  initialKey: string;
  onClose: () => void;
  onValidate: (key: string) => Promise<{ valid: boolean; message: string }>;
  onSave: (key: string) => void;
}

export default function SettingsModal({
  open,
  initialKey,
  onClose,
  onValidate,
  onSave
}: SettingsModalProps) {
  const [keyInput, setKeyInput] = useState(initialKey);
  const [statusMessage, setStatusMessage] = useState("");
  const [isValidating, setIsValidating] = useState(false);

  useEffect(() => {
    setKeyInput(initialKey);
  }, [initialKey, open]);

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
          Groq API key
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
        {statusMessage ? (
          <p className="mt-3 rounded-md border border-panelBorder bg-panelSoft px-3 py-2 text-xs text-slate-200">
            {statusMessage}
          </p>
        ) : null}
      </div>
    </div>
  );
}
