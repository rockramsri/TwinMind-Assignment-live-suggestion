"use client";

import SuggestionCard from "./SuggestionCard";
import { SuggestionCard as SuggestionCardType } from "../lib/types";

interface SuggestionsPanelProps {
  currentCards: SuggestionCardType[];
  olderCards: SuggestionCardType[];
  selectedCardId?: string | null;
  onSelectCard: (card: SuggestionCardType) => void;
}

export default function SuggestionsPanel({
  currentCards,
  olderCards,
  selectedCardId,
  onSelectCard
}: SuggestionsPanelProps) {
  return (
    <section className="flex h-full flex-col border-r border-panelBorder bg-panel">
      <div className="border-b border-panelBorder px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-100">Suggestions</h2>
        <p className="text-xs text-slate-400">
          Exactly 3 new cards every 30 seconds; older cards remain clickable.
        </p>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-3">
        {!currentCards.length && !olderCards.length ? (
          <p className="rounded-md border border-dashed border-panelBorder p-3 text-sm text-slate-400">
            No suggestion cards yet. Start the meeting and wait for the first 30-second tick.
          </p>
        ) : (
          <div className="space-y-4">
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-cyan-200">
                Current batch
              </div>
              <div className="space-y-2">
                {currentCards.map((card) => (
                  <SuggestionCard
                    key={card.card_id}
                    card={card}
                    selected={selectedCardId === card.card_id}
                    onClick={() => onSelectCard(card)}
                  />
                ))}
              </div>
            </div>
            {olderCards.length > 0 ? (
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-300">
                  Older cards
                </div>
                <div className="space-y-2">
                  {olderCards.map((card) => (
                    <SuggestionCard
                      key={card.card_id}
                      card={card}
                      selected={selectedCardId === card.card_id}
                      onClick={() => onSelectCard(card)}
                    />
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}
