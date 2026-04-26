export type CardType =
  | "question_to_ask"
  | "info_to_surface"
  | "verify_claim"
  | "decision_nudge"
  | "stakeholder_followup";

export interface TranscriptChunk {
  chunk_id: string;
  text: string;
  start_ms: number;
  end_ms: number;
  created_at_ms: number;
  is_low_signal: boolean;
  topic_tags: string[];
}

export interface SuggestionCard {
  card_id: string;
  type: CardType;
  title: string;
  preview: string;
  why_now: string;
  priority: "high" | "medium" | "low";
  topic_ids: string[];
  evidence_chunk_ids: string[];
  created_at_ms: number;
}

export interface SuggestionBatch {
  batch_id: string;
  created_at_ms: number;
  window_start_ms: number;
  window_end_ms: number;
  cards: SuggestionCard[];
  route_decision: Record<string, unknown>;
}

export interface TickResponse {
  transcript_append: TranscriptChunk[];
  cards: SuggestionCard[];
  route_decision: Record<string, unknown>;
  ledger_updates: Array<Record<string, unknown>>;
  window_start_ms?: number;
  window_end_ms?: number;
}

export interface CardThreadMessage {
  role: "user" | "assistant" | "system";
  text: string;
  created_at_ms: number;
  citations?: string[];
}

export interface CardOpenResponse {
  card_id: string;
  explanation: string;
  citations: Array<{
    chunk_id: string;
    start_ms: number;
    end_ms: number;
    label: string;
  }>;
  thread: CardThreadMessage[];
}

export interface SessionState {
  session_id: string;
  created_at_ms: number;
  transcript_chunks: TranscriptChunk[];
  topic_clusters: Array<Record<string, unknown>>;
  suggestion_batches: SuggestionBatch[];
  unresolved_ledger: Array<Record<string, unknown>>;
  active_topic_id?: string | null;
  session_config: SessionConfig;
}

export interface SessionConfig {
  live_window_seconds: number;
  live_context_token_cap: number;
  chat_context_token_cap: number;
  tick_cadence_seconds: number;
  live_suggestions_prompt?: string | null;
  card_detail_prompt?: string | null;
  card_chat_prompt?: string | null;
}
