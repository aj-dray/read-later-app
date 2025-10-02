export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

import { NextResponse } from "next/server";

import {
  searchItems,
  type SearchMode,
  type SearchScope,
  type SearchResult,
} from "@/app/_lib/search";

function sanitiseMode(value: string | null): SearchMode {
  return value === "semantic" ? "semantic" : "lexical";
}

function sanitiseScope(value: string | null): SearchScope {
  return value === "chunks" ? "chunks" : "items";
}

function sanitiseLimit(value: string | null): number | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return undefined;
  }
  return parsed;
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.get("query")?.trim() ?? "";
  const modeParam = searchParams.get("mode");
  const scopeParam = searchParams.get("scope");
  const limitParam = searchParams.get("limit");

  if (!query) {
    return NextResponse.json({ results: [] satisfies SearchResult[] });
  }

  const mode = sanitiseMode(modeParam);
  const scope = sanitiseScope(scopeParam);
  const limit = sanitiseLimit(limitParam);

  try {
    const results = await searchItems({
      query,
      mode,
      scope,
      limit,
    });

    return NextResponse.json({ results });
  } catch (error) {
    console.error("Failed to perform search", { error, mode, scope });

    if (error instanceof Error && error.message.includes("401")) {
      return NextResponse.json(
        { error: "Authentication required" },
        { status: 401 },
      );
    }

    return NextResponse.json(
      { error: "Unable to complete search" },
      { status: 500 },
    );
  }
}
