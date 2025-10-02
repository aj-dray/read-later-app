"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import ItemCard from "@/app/_components/ItemCard";
import type { SearchMode, SearchScope, SearchResult } from "@/app/_lib/search";

type SearchClientProps = {
  initialQuery: string;
  initialMode: SearchMode;
  initialScope: SearchScope;
  initialResults: SearchResult[];
};

type SearchApiResponse = {
  results: SearchResult[];
};

export default function SearchClient({
  initialQuery,
  initialMode,
  initialScope,
  initialResults,
}: SearchClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsString = useMemo(
    () => searchParams.toString(),
    [searchParams],
  );

  const [query, setQuery] = useState(initialQuery);
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [mode, setMode] = useState<SearchMode>(initialMode);
  const [scope, setScope] = useState<SearchScope>(initialScope);
  const [results, setResults] = useState<SearchResult[]>(initialResults);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTrigger, setSearchTrigger] = useState(0);
  const [isButtonPressed, setIsButtonPressed] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const lastSyncedSearchRef = useRef(searchParamsString);

  // Sync local state with the URL when the user navigates with history controls
  useEffect(() => {
    const params = new URLSearchParams(searchParamsString);
    const nextQuery = params.get("q") ?? "";
    const nextModeParam = params.get("mode");
    const nextScopeParam = params.get("scope");
    const desiredMode: SearchMode =
      nextModeParam === "semantic" ? "semantic" : "lexical";
    const desiredScope: SearchScope =
      nextScopeParam === "chunks" ? "chunks" : "items";

    setQuery((current) => (current === nextQuery ? current : nextQuery));
    setSearchQuery((current) => (current === nextQuery ? current : nextQuery));
    setMode((current) => {
      return current === desiredMode ? current : desiredMode;
    });
    setScope((current) => {
      return current === desiredScope ? current : desiredScope;
    });
    lastSyncedSearchRef.current = searchParamsString;
  }, [searchParamsString]);

  // Keep the URL in sync with the current search configuration
  useEffect(() => {
    const params = new URLSearchParams();
    const trimmedQuery = searchQuery.trim();
    if (trimmedQuery) {
      params.set("q", trimmedQuery);
    }
    if (mode !== "lexical") {
      params.set("mode", mode);
    }
    if (scope !== "items") {
      params.set("scope", scope);
    }

    const nextSearch = params.toString();
    if (nextSearch === lastSyncedSearchRef.current) {
      return;
    }

    lastSyncedSearchRef.current = nextSearch;
    router.replace(nextSearch ? `${pathname}?${nextSearch}` : pathname, {
      scroll: false,
    });
  }, [searchQuery, mode, scope, router, pathname]);

  // Perform the search whenever search query or other parameters change
  useEffect(() => {
    const trimmedQuery = searchQuery.trim();

    if (!trimmedQuery) {
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      setResults([]);
      setIsLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    abortControllerRef.current?.abort();
    abortControllerRef.current = controller;

    // Clear previous results immediately when starting new search
    setResults([]);
    setIsLoading(true);
    setError(null);

    const performSearch = async () => {
      try {
        const params = new URLSearchParams();
        params.set("query", trimmedQuery);
        params.set("mode", mode);
        params.set("scope", scope);
        const response = await fetch(`/api/search?${params.toString()}`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(
            `Search request failed with status ${response.status}`,
          );
        }
        const payload = (await response.json()) as SearchApiResponse;
        setResults(Array.isArray(payload.results) ? payload.results : []);
        setIsLoading(false);
        setError(null);
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          return;
        }
        console.error("Search request failed", err);
        setIsLoading(false);
        setError("Something went wrong while searching. Please try again.");
      }
    };

    performSearch();

    return () => {
      controller.abort();
    };
  }, [searchQuery, mode, scope, searchTrigger]);

  const handleSubmit: React.FormEventHandler<HTMLFormElement> = (event) => {
    event.preventDefault();
    const trimmedQuery = query.trim();
    // Always clear results and trigger search on form submit
    setResults([]);
    setSearchQuery(trimmedQuery);
    // Force a new search even if the query is the same by incrementing trigger
    setSearchTrigger((prev) => prev + 1);

    // Trigger button press effect
    setIsButtonPressed(true);
    setTimeout(() => setIsButtonPressed(false), 150);
  };

  // Clear search when input becomes empty
  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newQuery = event.target.value;
    setQuery(newQuery);

    // If input is cleared, immediately clear the search
    if (newQuery.trim() === "" && searchQuery.trim() !== "") {
      setSearchQuery("");
      setResults([]);
    }
  };

  // Auto-select all text when input is focused
  const handleInputFocus = (event: React.FocusEvent<HTMLInputElement>) => {
    event.target.select();
  };

  // Remove a deleted item from the rendered results immediately
  const handleDelete = (itemId: string) => {
    setResults((prev) => prev.filter((r) => r.item.id !== itemId));
  };

  return (
    <div className="flex flex-col gap-[15px] p-[25px]">
      <form className="flex flex-col gap-4 " onSubmit={handleSubmit}>
        <div className="flex h-[50px] w-[750px] items-center rounded-[25px] transition-all hover:drop-shadow-md hover:scale-101 focus-within:shadow-md focus-within:scale-101 bg-white px-[5px]">
          <input
            type="text"
            value={query}
            onChange={handleInputChange}
            onFocus={handleInputFocus}
            placeholder="Search for items"
            className="w-full bg-transparent ml-[10px] h-full text-slate-600 font-medium text-[15px]  focus:outline-none"
          />
          <button
            type="submit"
            className={`flex h-[40px] w-[60px] items-center justify-center rounded-full text-[15px] font-bold text-slate-900 transition hover:scale-105 hover:bg-blue-400 hover:drop-shadow-md ${
              isButtonPressed
                ? "scale-105 bg-blue-400 drop-shadow-md"
                : "bg-blue-400/50"
            }`}
          >
            ⏎
          </button>
        </div>
      </form>

      <div className="flex flex-col gap-[15px]">
        {/* Loading placeholders */}
        {searchQuery.trim() && isLoading && (
          <>
            {[...Array(3)].map((_, index) => (
              <div
                key={`loading-${index}`}
                className="flex rounded-2xl overflow-hidden border border-slate-200 bg-white animate-loading-pulse"
                style={{
                  animationDelay: `${index * 200}ms`,
                  animationDuration: "1000ms",
                  animationIterationCount: "infinite",
                  animationFillMode: "both",
                }}
              >
                {/* Favicon Section */}
                <div className="flex justify-center bg-white p-[15px]">
                  <div className="flex justify-center items-center w-[45px] rounded-xl h-[45px] bg-[#D8D8D8]">
                    <div className="bg-gray-200 h-[35px] w-[35px] rounded-[8px] flex items-center justify-center border border-gray-200"></div>
                  </div>
                </div>

                {/* Main Content Section */}
                <div className="flex flex-col px-[15px] py-[12px] flex-1 gap-[6px]">
                  <div className="h-[20px] bg-slate-200 rounded w-3/4"></div>
                  <div className="flex flex-col gap-[4px] min-h-[48px]">
                    <div className="h-[12px] bg-slate-200 rounded w-full max-w-[220px]"></div>
                    <div className="h-[12px] bg-slate-200 rounded w-3/4 max-w-[180px]"></div>
                    <div className="h-[12px] bg-slate-200 rounded w-4/5 max-w-[200px]"></div>
                  </div>
                </div>

                {/* Info Panels Section */}
                <div className="flex flex-col items-end justify-start gap-[6px] p-[15px] ml-auto">
                  <div className="h-[20px] bg-slate-200 rounded w-[40px]"></div>
                  <div className="flex items-center gap-[5px] px-[10px] rounded-xl bg-transparent h-[20px]">
                    <div className="h-[12px] bg-slate-200 rounded w-[35px]"></div>
                    <div className="h-[15px] bg-slate-200 rounded w-[15px]"></div>
                  </div>
                  <div className="flex items-center gap-[5px] px-[10px] rounded-xl bg-transparent h-[20px]">
                    <div className="h-[12px] bg-slate-200 rounded w-[30px]"></div>
                    <div className="h-[15px] bg-slate-200 rounded w-[15px]"></div>
                  </div>
                </div>
              </div>
            ))}
          </>
        )}

        {/* Error state */}
        {searchQuery.trim() && !isLoading && error && (
          <p className="text-xl font-bold text-slate-400 text-center py-8">
            {error}
          </p>
        )}

        {/* No results state */}
        {searchQuery.trim() && !isLoading && !error && results.length === 0 && (
          <p className="text-xl font-bold text-slate-400 text-center py-8">
            No matching items found.
          </p>
        )}

        {/* Search results with smooth animation */}
        {results.map((result, index) => (
          <Link
            key={result.item.id}
            href={result.item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-lg outline-none transition-all duration-300 ease-out transform focus-visible:-translate-y-1 focus-visible:drop-shadow-lg focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-blue-500 animate-search-result-enter"
            style={{
              animationDelay: `${index * 50}ms`,
            }}
          >
            <ItemCard item={result.item} onDelete={handleDelete} />
          </Link>
        ))}
      </div>
    </div>
  );
}
