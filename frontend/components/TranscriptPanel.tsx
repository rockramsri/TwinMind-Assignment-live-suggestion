"use client";

import { TranscriptStreamEntry } from "../lib/state";

function formatClock(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

interface TranscriptPanelProps {
  entries?: TranscriptStreamEntry[];
}

export default function TranscriptPanel({ entries = [] }: TranscriptPanelProps) {
  return (
    <section className="flex h-full flex-col border-r border-panelBorder bg-panel">
      <div className="border-b border-panelBorder px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-100">Transcript</h2>
        <p className="text-xs text-slate-400">Streaming transcript, appended every ~30 seconds</p>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-3">
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
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
