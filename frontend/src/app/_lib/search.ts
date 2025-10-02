"use server";

import { fetchItems, authedFetch } from "@/app/_lib/items";
import type { ItemSummary } from "@/app/_lib/items";

export type SearchMode = "lexical" | "semantic";
export type SearchScope = "items" | "chunks";

export type SearchResult = {
  item: ItemSummary;
  preview: string | null;
  score: number | null;
  distance: number | null;
};

type PerformSearchOptions = {
  query: string;
  mode?: SearchMode;
  scope?: SearchScope;
  limit?: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function toStringOrNull(value: unknown): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  return null;
}

function toNumberOrNull(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

type ParsedRawResult = {
  id: string;
  preview: string | null;
  score: number | null;
  distance: number | null;
};

function parseRawResult(value: unknown): ParsedRawResult | null {
  if (!isRecord(value)) {
    return null;
  }

  const id = toStringOrNull(value.id);
  if (!id) {
    return null;
  }

  const preview =
    toStringOrNull(value.preview) ??
    toStringOrNull(value.content_text) ??
    null;
  const score = toNumberOrNull(value.score);
  const distance = toNumberOrNull(value.distance);

  return { id, preview, score, distance };
}

function sanitiseLimit(limit: number | undefined): number {
  if (!Number.isFinite(limit ?? NaN)) {
    return 20;
  }
  const value = Math.trunc(limit as number);
  if (!Number.isFinite(value)) {
    return 20;
  }
  return Math.min(Math.max(value, 1), 100);
}

export async function searchItems({
  query,
  mode = "lexical",
  scope = "items",
  limit = 20,
}: PerformSearchOptions): Promise<SearchResult[]> {
  const trimmedQuery = query.trim();
  if (!trimmedQuery) {
    return [];
  }

  const safeLimit = sanitiseLimit(limit);
  const params = new URLSearchParams();
  params.set("query", trimmedQuery);
  params.set("mode", mode === "semantic" ? "semantic" : "lexical");
  params.set("scope", scope === "chunks" ? "chunks" : "items");
  params.set("limit", String(safeLimit));

  const response = await authedFetch(`/items/search?${params.toString()}`, {
    cache: "no-store",
    next: { revalidate: 0 },
  });

  if (response.status === 401) {
    throw new Error("Search request failed: Unauthorized. Please log in again.");
  }

  if (!response.ok) {
    let errorDetail = `Search request failed with status ${response.status}`;
    try {
      const errorBody = await response.json();
      if (errorBody && typeof errorBody.detail === "string") {
        errorDetail = errorBody.detail;
      }
    } catch {
      // Ignore JSON parse errors, use default message
    }
    throw new Error(errorDetail);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch (error) {
    throw new Error(`Search failed: Invalid response format from server. ${error instanceof Error ? error.message : ""}`);
  }
  if (!isRecord(payload)) {
    throw new Error("Unexpected payload when performing search");
  }

  const rawResults = Array.isArray(payload.results)
    ? payload.results
    : [];

  const parsed = rawResults
    .map((entry) => parseRawResult(entry))
    .filter((entry): entry is ParsedRawResult => Boolean(entry));

  if (parsed.length === 0) {
    return [];
  }

  const uniqueIds: string[] = [];
  const seenIds = new Set<string>();
  parsed.forEach((entry) => {
    if (!seenIds.has(entry.id)) {
      seenIds.add(entry.id);
      uniqueIds.push(entry.id);
    }
  });

  if (uniqueIds.length === 0) {
    return [];
  }

  const items = await fetchItems({
    filters: [
      {
        column: "id",
        operator: "IN",
        value: uniqueIds,
      },
    ],
    limit: Math.max(uniqueIds.length, 1),
  });

  const itemById = new Map<string, ItemSummary>(
    items.map((item) => [item.id, item]),
  );

  const results: SearchResult[] = [];
  const usedIds = new Set<string>();
  parsed.forEach((entry) => {
    const item = itemById.get(entry.id);
    if (!item || usedIds.has(entry.id)) {
      return;
    }
    usedIds.add(entry.id);
    results.push({
      item,
      preview: entry.preview,
      score: entry.score,
      distance: entry.distance,
    });
  });

  return results;
}
