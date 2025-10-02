export const dynamic = "force-dynamic";

import { redirect } from "next/navigation";

import { getSession } from "@/app/_lib/auth";
import {
  searchItems,
  type SearchMode,
  type SearchScope,
} from "@/app/_lib/search";
import type { SearchResult } from "@/app/_lib/search";
import SearchClient from "./SearchClient";

type SearchPageProps = {
  searchParams: Promise<{
    q?: string;
    mode?: string;
    scope?: string;
  }>;
};

function sanitiseMode(value: string | undefined): SearchMode {
  return value === "semantic" ? "semantic" : "lexical";
}

function sanitiseScope(value: string | undefined): SearchScope {
  return value === "chunks" ? "chunks" : "items";
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }

  const resolvedParams = await searchParams;
  const query = resolvedParams?.q?.trim() ?? "";
  const mode = sanitiseMode(resolvedParams?.mode);
  const scope = sanitiseScope(resolvedParams?.scope);

  let initialResults: SearchResult[] = [];
  if (query) {
    try {
      initialResults = await searchItems({
        query,
        mode,
        scope,
        limit: 30,
      });
    } catch (error) {
      if (error instanceof Error && error.message.includes("401")) {
        redirect("/login");
      }
      throw error;
    }
  }

  return (
    <div
      className="flex h-full w-full flex-col bg-[#F0F0F0] overflow-auto"
      style={{
        paddingRight: "calc(var(--panels-width, 0px) + 25px",
      }}
    >
      <SearchClient
        initialQuery={query}
        initialMode={mode}
        initialScope={scope}
        initialResults={initialResults}
      />
    </div>
  );
}
