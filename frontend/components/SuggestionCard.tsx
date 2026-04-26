"use client";

import { SuggestionCard as SuggestionCardType } from "../lib/types";

interface SuggestionCardProps {
  card: SuggestionCardType;
  selected: boolean;
  covered?: boolean;
  onClick: () => void;
}

function badgeColor(type: SuggestionCardType["type"]): string {
  switch (type) {
    case "question_to_ask":
      return "bg-blue-500/20 text-blue-200";
    case "info_to_surface":
      return "bg-emerald-500/20 text-emerald-200";
    case "verify_claim":
      return "bg-amber-500/20 text-amber-100";
    case "decision_nudge":
      return "bg-fuchsia-500/20 text-fuchsia-200";
    case "stakeholder_followup":
      return "bg-cyan-500/20 text-cyan-200";
    default:
      return "bg-slate-500/20 text-slate-100";
  }
}

export default function SuggestionCard({
  card,
  selected,
  covered = false,
  onClick
}: SuggestionCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-md border p-3 text-left transition ${
        selected
          ? "border-accentStrong bg-cyan-900/20"
          : "border-panelBorder bg-panelSoft hover:border-cyan-500/60"
      } ${covered ? "opacity-70" : ""}`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className={`rounded px-2 py-1 text-xs font-semibold ${badgeColor(card.type)}`}>
          {card.type}
        </span>
        <div className="flex items-center gap-2">
          {covered ? (
            <span className="rounded-full border border-emerald-600/60 bg-emerald-950/50 px-2 py-0.5 text-[10px] font-semibold text-emerald-200">
              covered
            </span>
          ) : null}
          <span className="text-xs text-slate-300">priority: {card.priority}</span>
        </div>
      </div>
      <h3 className={`text-sm font-semibold text-white ${covered ? "line-through decoration-emerald-300/70" : ""}`}>
        {card.title}
      </h3>
      <p className="mt-1 text-sm text-slate-200">{card.preview}</p>
      <p className="mt-2 text-xs text-slate-400">{card.why_now}</p>
    </button>
  );
}
