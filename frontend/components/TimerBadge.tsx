"use client";

interface TimerBadgeProps {
  secondsRemaining: number;
}

export default function TimerBadge({ secondsRemaining }: TimerBadgeProps) {
  return (
    <div className="rounded-md border border-panelBorder bg-panelSoft px-3 py-1 text-xs text-slate-200">
      Next refresh in <span className="font-semibold text-accentStrong">{secondsRemaining}s</span>
    </div>
  );
}
