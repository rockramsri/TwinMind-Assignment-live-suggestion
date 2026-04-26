import { SuggestionBatch, SuggestionCard, TranscriptChunk } from "./types";

export const DEFAULT_MEDIA_SLICE_MS = 5000;
export const DEFAULT_UI_REFRESH_SECONDS = 30;

export interface TranscriptGroup {
  bucketIndex: number;
  startMs: number;
  endMs: number;
  chunks: TranscriptChunk[];
}

export interface TranscriptStreamEntry {
  id: string;
  startMs: number;
  endMs: number;
  text: string;
}

export function mergeTranscriptChunks(
  existing: TranscriptChunk[],
  incoming: TranscriptChunk[]
): TranscriptChunk[] {
  const byId = new Map<string, TranscriptChunk>();
  for (const chunk of [...existing, ...incoming]) {
    byId.set(chunk.chunk_id, chunk);
  }
  return [...byId.values()].sort((a, b) => a.start_ms - b.start_ms);
}

export function transcriptGroupsByThirtySeconds(
  chunks: TranscriptChunk[],
  bucketSeconds = DEFAULT_UI_REFRESH_SECONDS
): TranscriptGroup[] {
  const bucketSizeMs = bucketSeconds * 1000;
  const grouped = new Map<number, TranscriptChunk[]>();
  for (const chunk of chunks) {
    const bucket = Math.floor(chunk.start_ms / bucketSizeMs);
    const list = grouped.get(bucket) ?? [];
    list.push(chunk);
    grouped.set(bucket, list);
  }
  return [...grouped.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([bucketIndex, groupedChunks]) => ({
      bucketIndex,
      startMs: bucketIndex * bucketSizeMs,
      endMs: (bucketIndex + 1) * bucketSizeMs,
      chunks: groupedChunks.sort((a, b) => a.start_ms - b.start_ms)
    }));
}

export function transcriptStreamByThirtySeconds(
  chunks: TranscriptChunk[],
  bucketSeconds = DEFAULT_UI_REFRESH_SECONDS
): TranscriptStreamEntry[] {
  const bucketSizeMs = bucketSeconds * 1000;
  const grouped = new Map<number, string[]>();
  for (const chunk of chunks) {
    const text = chunk.text.trim();
    if (!text) {
      continue;
    }
    const bucket = Math.floor(chunk.start_ms / bucketSizeMs);
    const list = grouped.get(bucket) ?? [];
    list.push(text);
    grouped.set(bucket, list);
  }
  return [...grouped.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([bucketIndex, texts]) => ({
      id: `t_${bucketIndex}`,
      startMs: bucketIndex * bucketSizeMs,
      endMs: (bucketIndex + 1) * bucketSizeMs,
      text: texts.join(" ").trim()
    }))
    .filter((item) => item.text.length > 0);
}

export function splitCurrentAndOlderCards(
  batches: SuggestionBatch[]
): { current: SuggestionCard[]; older: SuggestionCard[] } {
  if (!batches.length) {
    return { current: [], older: [] };
  }
  const sorted = [...batches].sort((a, b) => b.created_at_ms - a.created_at_ms);
  const current = sorted[0].cards;
  const older = sorted.slice(1).flatMap((batch) => batch.cards);
  return { current, older };
}
