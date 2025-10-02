import type { ItemSummary } from "@/app/_lib/items-types";

export function formatSavedAt(savedAt?: ItemSummary["created_at"]) {
  if (!savedAt) {
    return null;
  }

  const numeric = Number(savedAt);
  if (!Number.isNaN(numeric)) {
    const millisecondsThreshold = 10 ** 12;
    const timestamp =
      numeric < millisecondsThreshold ? numeric * 1000 : numeric;
    return new Date(timestamp).toLocaleDateString("en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  }

  const parsed = Date.parse(savedAt);
  return Number.isNaN(parsed)
    ? null
    : new Date(parsed).toLocaleDateString("en-US", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      });
}

export function estimateReadingTime(tokenCount: number | null | undefined): string {
  if (!tokenCount || tokenCount <= 0) return "-- min";

  const wordCount = Math.ceil(tokenCount * 0.75);
  const minutes = Math.ceil(wordCount / 200);
  const roundedMinutes = Math.ceil(minutes / 5) * 5;

  return `${roundedMinutes} min`;
}

export function estimateReadMinutes(tokenCount: number | null | undefined): number {
  if (!tokenCount || tokenCount <= 0) {
    return 5;
  }
  const words = Math.ceil(tokenCount * 0.75);
  const minutes = Math.ceil(words / 200);
  const roundedMinutes = Math.ceil(minutes / 5) * 5;
  return Math.max(roundedMinutes, 5);
}
