"use client";

import { useEffect, useRef } from "react";

import { TranscriptStreamEntry } from "../lib/state";

function formatClock(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function formatTopicLabel(topicId: string): string {
  return topicId.replace(/[_-]+/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

interface TranscriptPanelProps {
  entries?: TranscriptStreamEntry[];
}

export default function TranscriptPanel({ entries = [] }: TranscriptPanelProps) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!scrollerRef.current) {
      return;
    }
    scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
  }, [entries]);

  return (
    <section className="flex h-full flex-col border-r border-panelBorder bg-panel">
      <div className="border-b border-panelBorder px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-100">Transcript</h2>
        <p className="text-xs text-slate-400">Streaming transcript, appended every ~30 seconds</p>
      </div>
      <div ref={scrollerRef} className="min-h-0 flex-1 overflow-auto p-3">
        {!entries.length ? (
          <p className="rounded-md border border-dashed border-panelBorder p-3 text-sm text-slate-400">
            Waiting for transcript...
          </p>
        ) : (
          <div className="space-y-2">
            {entries.map((entry) => (
              <div key={entry.id} className="rounded-md border border-panelBorder bg-panelSoft p-3">
                <div className="mb-1 text-xs font-semibold text-cyan-200">
                  {formatClock(entry.startMs)} - {formatClock(entry.endMs)}
                </div>
                <p className="text-sm text-slate-100">{entry.text}</p>
                {entry.topicTags.length ? (
                  <div className="mt-2">
                    <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500">
                      Topics
                    </div>
                    <div className="flex flex-wrap gap-1">
                    {entry.topicTags.map((tag) => (
                      <span
                        key={`${entry.id}-${tag}`}
                        className="rounded-full border border-cyan-700/60 bg-cyan-950/50 px-2 py-0.5 text-[10px] text-cyan-100"
                      >
                        {formatTopicLabel(tag)}
                      </span>
                    ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
