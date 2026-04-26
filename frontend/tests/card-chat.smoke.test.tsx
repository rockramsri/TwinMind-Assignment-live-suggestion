import React from "react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import CardChatPanel from "../components/CardChatPanel";
import SuggestionsPanel from "../components/SuggestionsPanel";
import { SuggestionCard } from "../lib/types";

const sampleCard: SuggestionCard = {
  card_id: "card_1",
  type: "question_to_ask",
  title: "Clarify budget owner",
  preview: "Ask who owns the final budget decision.",
  why_now: "Ownership is still unclear.",
  priority: "high",
  topic_ids: ["topic_budget"],
  evidence_chunk_ids: ["chunk_1"],
  created_at_ms: Date.now()
};

function Harness() {
  const [selectedCard, setSelectedCard] = useState<SuggestionCard | null>(null);
  return (
    <div>
      <SuggestionsPanel
        currentCards={[sampleCard]}
        olderCards={[]}
        selectedCardId={selectedCard?.card_id}
        onSelectCard={setSelectedCard}
      />
      <CardChatPanel
        selectedCard={selectedCard}
        thread={
          selectedCard
            ? [{ role: "assistant", text: "Initial grounded explanation", created_at_ms: Date.now() }]
            : []
        }
        isLoadingOpen={false}
        isSending={false}
        onSend={async () => {}}
      />
    </div>
  );
}

describe("card selection smoke", () => {
  it("opens card chat panel after selecting a card", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    expect(
      screen.getByText(/Select any card from the center panel/i)
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Clarify budget owner/i }));

    expect(
      screen.getByRole("heading", { name: "Clarify budget owner", level: 2 })
    ).toBeInTheDocument();
    expect(screen.getByText(/Initial grounded explanation/i)).toBeInTheDocument();
  });
});
