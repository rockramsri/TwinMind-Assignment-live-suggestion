"use client";

import { FormEvent, ReactNode, useMemo, useState } from "react";

import { CardThreadMessage, SuggestionCard } from "../lib/types";

interface CardChatPanelProps {
  selectedCard: SuggestionCard | null;
  thread: CardThreadMessage[];
  isLoadingOpen: boolean;
  isSending: boolean;
  onSend: (message: string) => Promise<void>;
}

function formatTopicLabel(topicId: string): string {
  return topicId.replace(/[_-]+/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function cleanAssistantText(text: string): string {
  return text
    .replace(/\[chunk_[^\]]+\]/gi, "")
    .replace(/\(chunk_[^)]+\)/gi, "")
    .replace(/\bchunk_[a-z0-9_]+\b/gi, "")
    .replace(/^Sources:\s.*$/gim, "")
    .trim();
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <span key={index}>{part}</span>;
  });
}

function MarkdownMessage({ text }: { text: string }) {
  const cleaned = cleanAssistantText(text);
  const blocks = cleaned.split(/\n{2,}/).filter(Boolean);
  return (
    <div className="space-y-2">
      {blocks.map((block, blockIndex) => {
        const lines = block.split("\n").filter(Boolean);
        const isList = lines.every((line) => /^[-*]\s+/.test(line.trim()));
        if (isList) {
          return (
            <ul key={blockIndex} className="list-disc space-y-1 pl-5">
              {lines.map((line, lineIndex) => (
                <li key={`${blockIndex}-${lineIndex}`}>
                  {renderInlineMarkdown(line.replace(/^[-*]\s+/, ""))}
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={blockIndex} className="leading-relaxed">
            {renderInlineMarkdown(lines.join(" "))}
          </p>
        );
      })}
    </div>
  );
}

export default function CardChatPanel({
  selectedCard,
  thread,
  isLoadingOpen,
  isSending,
  onSend
}: CardChatPanelProps) {
  const [draft, setDraft] = useState("");
  const hasCard = Boolean(selectedCard);

  const visibleThread = useMemo(
    () => thread.filter((message) => message.role !== "system"),
    [thread]
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isSending) {
      return;
    }
    setDraft("");
    await onSend(message);
  }

  if (!hasCard || !selectedCard) {
    return (
      <section className="flex h-full flex-col bg-panel">
        <div className="border-b border-panelBorder px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-100">Card details + chat</h2>
        </div>
        <div className="flex flex-1 items-center justify-center p-6">
          <p className="max-w-sm rounded-md border border-dashed border-panelBorder p-4 text-center text-sm text-slate-400">
            Select any card from the center panel to open an immediate grounded explanation and start a focused chat thread.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="flex h-full flex-col bg-panel">
      <div className="border-b border-panelBorder px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-100">{selectedCard.title}</h2>
        <p className="text-xs text-slate-400">{selectedCard.type}</p>
        {selectedCard.topic_ids.length ? (
          <div className="mt-2 flex flex-wrap gap-1">
            {selectedCard.topic_ids.slice(0, 4).map((topicId) => (
              <span
                key={topicId}
                className="rounded-full border border-cyan-700/60 bg-cyan-950/40 px-2 py-0.5 text-[10px] text-cyan-100"
              >
                {formatTopicLabel(topicId)}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-auto p-3">
        {isLoadingOpen ? (
          <p className="rounded-md border border-panelBorder bg-panelSoft p-3 text-sm text-slate-300">
            Loading grounded explanation...
          </p>
        ) : null}
        {visibleThread.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`rounded-md border p-3 text-sm ${
              message.role === "assistant"
                ? "border-cyan-700/60 bg-cyan-950/30 text-slate-100"
                : "border-panelBorder bg-panelSoft text-slate-100"
            }`}
          >
            <div className="mb-1 text-[11px] uppercase tracking-wide text-slate-400">{message.role}</div>
            {message.role === "assistant" ? (
              <>
                <MarkdownMessage text={message.text} />
                {selectedCard.topic_ids.length ? (
                  <div className="mt-3 border-t border-cyan-800/50 pt-2">
                    <div className="mb-1 text-[10px] uppercase tracking-wide text-cyan-200/70">
                      Source topics
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {selectedCard.topic_ids.slice(0, 4).map((topicId) => (
                        <span
                          key={`${message.created_at_ms}-${topicId}`}
                          className="rounded-full border border-cyan-700/60 bg-cyan-950/40 px-2 py-0.5 text-[10px] text-cyan-100"
                        >
                          {formatTopicLabel(topicId)}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </>
            ) : (
              <p className="whitespace-pre-wrap">{message.text}</p>
            )}
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-panelBorder p-3">
        <label htmlFor="chat-input" className="mb-1 block text-xs text-slate-400">
          Ask a follow-up for this card only
        </label>
        <textarea
          id="chat-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows={3}
          className="w-full rounded-md border border-panelBorder bg-panelSoft px-3 py-2 text-sm text-slate-100 outline-none focus:border-accentStrong"
          placeholder="What specifically should we verify next?"
        />
        <div className="mt-2 flex justify-end">
          <button
            type="submit"
            disabled={isSending || !draft.trim()}
            className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
          >
            {isSending ? "Sending..." : "Send"}
          </button>
        </div>
      </form>
    </section>
  );
}
