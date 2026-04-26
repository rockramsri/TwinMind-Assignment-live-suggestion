"use client";

import { useMemo, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import { openCard, streamCardChat } from "../lib/api";
import { CardThreadMessage, SuggestionBatch, SuggestionCard } from "../lib/types";

interface UseCardChatArgs {
  sessionId: string | null;
  suggestionBatches: SuggestionBatch[];
  humanizeError: (error: unknown) => string;
  setErrorMessage: Dispatch<SetStateAction<string | null>>;
  setUsedCardIds: Dispatch<SetStateAction<Set<string>>>;
}

export function useCardChat({
  sessionId,
  suggestionBatches,
  humanizeError,
  setErrorMessage,
  setUsedCardIds
}: UseCardChatArgs) {
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  const [threadsByCard, setThreadsByCard] = useState<Record<string, CardThreadMessage[]>>({});
  const [loadingCardId, setLoadingCardId] = useState<string | null>(null);
  const [sendingCardId, setSendingCardId] = useState<string | null>(null);

  const allCards = useMemo(
    () => suggestionBatches.flatMap((batch) => batch.cards),
    [suggestionBatches]
  );
  const selectedCard = useMemo(
    () => allCards.find((card) => card.card_id === selectedCardId) ?? null,
    [allCards, selectedCardId]
  );
  const selectedThread = selectedCardId ? threadsByCard[selectedCardId] ?? [] : [];

  async function handleCardSelect(card: SuggestionCard) {
    setSelectedCardId(card.card_id);
    if (!sessionId) {
      return;
    }
    if (threadsByCard[card.card_id]?.length) {
      return;
    }
    setLoadingCardId(card.card_id);
    try {
      const opened = await openCard(sessionId, card.card_id);
      setThreadsByCard((current) => ({
        ...current,
        [card.card_id]:
          opened.thread.length > 0
            ? opened.thread
            : [
                {
                  role: "assistant",
                  text: opened.explanation,
                  created_at_ms: Date.now()
                }
              ]
      }));
    } catch (error) {
      setErrorMessage(humanizeError(error));
    } finally {
      setLoadingCardId(null);
    }
  }

  async function handleSendCardMessage(message: string) {
    if (!sessionId || !selectedCardId) {
      return;
    }
    const activeSelectedCard = allCards.find((card) => card.card_id === selectedCardId);
    if (activeSelectedCard) {
      setUsedCardIds((current) => new Set(current).add(activeSelectedCard.card_id));
    }
    setSendingCardId(selectedCardId);
    const assistantPlaceholder: CardThreadMessage = {
      role: "assistant",
      text: "",
      created_at_ms: Date.now()
    };
    setThreadsByCard((current) => ({
      ...current,
      [selectedCardId]: [
        ...(current[selectedCardId] ?? []),
        { role: "user", text: message, created_at_ms: Date.now() },
        assistantPlaceholder
      ]
    }));

    try {
      await streamCardChat(sessionId, selectedCardId, message, (chunk) => {
        setThreadsByCard((current) => {
          const nextThread = [...(current[selectedCardId] ?? [])];
          const assistantIndex = [...nextThread]
            .reverse()
            .findIndex((entry) => entry.role === "assistant");
          if (assistantIndex < 0) {
            return current;
          }
          const actualIndex = nextThread.length - 1 - assistantIndex;
          nextThread[actualIndex] = {
            ...nextThread[actualIndex],
            text: `${nextThread[actualIndex].text}${chunk}`
          };
          return { ...current, [selectedCardId]: nextThread };
        });
      });
    } catch (error) {
      setErrorMessage(humanizeError(error));
    } finally {
      setSendingCardId(null);
    }
  }

  return {
    selectedCardId,
    setSelectedCardId,
    loadingCardId,
    sendingCardId,
    selectedCard,
    selectedThread,
    handleCardSelect,
    handleSendCardMessage
  };
}

