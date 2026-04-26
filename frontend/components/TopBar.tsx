"use client";

import TimerBadge from "./TimerBadge";

interface TopBarProps {
  isMeetingActive: boolean;
  countdown: number;
  onStartStop: () => void;
  onOpenSettings: () => void;
  onExport: () => void;
  onRefresh: () => void;
  disableActions?: boolean;
}

export default function TopBar({
  isMeetingActive,
  countdown,
  onStartStop,
  onOpenSettings,
  onExport,
  onRefresh,
  disableActions = false
}: TopBarProps) {
  return (
    <header className="flex items-center justify-between gap-4 border-b border-panelBorder bg-panel px-4 py-3">
      <div>
        <h1 className="text-lg font-semibold text-white">Twinmind Live Copilot</h1>
        <p className="text-xs text-slate-400">
          Transcript -&gt; suggestions -&gt; grounded card chat
        </p>
      </div>
      <div className="flex items-center gap-2">
        <TimerBadge secondsRemaining={countdown} />
        <button
          type="button"
          onClick={onRefresh}
          disabled={disableActions}
          className="rounded-md border border-panelBorder bg-panelSoft px-3 py-2 text-sm text-slate-100 disabled:opacity-50"
        >
          Refresh now
        </button>
        <button
          type="button"
          onClick={onExport}
          disabled={disableActions}
          className="rounded-md border border-panelBorder bg-panelSoft px-3 py-2 text-sm text-slate-100 disabled:opacity-50"
        >
          Export JSON
        </button>
        <button
          type="button"
          onClick={onOpenSettings}
          className="rounded-md border border-panelBorder bg-panelSoft px-3 py-2 text-sm text-slate-100"
        >
          Settings
        </button>
        <button
          type="button"
          onClick={onStartStop}
          className={`rounded-md px-3 py-2 text-sm font-semibold ${
            isMeetingActive
              ? "bg-rose-600 text-white hover:bg-rose-500"
              : "bg-accent text-slate-950 hover:bg-cyan-300"
          }`}
        >
          {isMeetingActive ? "Stop meeting" : "Start meeting"}
        </button>
      </div>
    </header>
  );
}
