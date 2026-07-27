"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import {
  searchStocks,
  type StockSearchResult,
} from "@/services/api";

export function StockSearch() {
  const router = useRouter();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);

  const requestIdRef = useRef(0);

  useEffect(() => {
    const normalizedQuery = query.trim();

    if (!normalizedQuery) {
      requestIdRef.current += 1;
      setResults([]);
      setErrorMessage("");
      setIsLoading(false);
      setHasSearched(false);
      setActiveIndex(-1);
      return;
    }

    setHasSearched(false);

    const timeoutId = window.setTimeout(async () => {
      const requestId = ++requestIdRef.current;

      setIsLoading(true);
      setErrorMessage("");

      try {
        const response = await searchStocks(normalizedQuery, 8);

        if (requestId !== requestIdRef.current) {
          return;
        }

        setResults(response.results);
        setActiveIndex(response.results.length > 0 ? 0 : -1);
        setHasSearched(true);
      } catch {
        if (requestId !== requestIdRef.current) {
          return;
        }

        setResults([]);
        setActiveIndex(-1);
        setHasSearched(true);
        setErrorMessage("Unable to search stocks right now.");
      } finally {
        if (requestId === requestIdRef.current) {
          setIsLoading(false);
        }
      }
    }, 300);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [query]);

  function openStock(result: StockSearchResult): void {
    setResults([]);
    setActiveIndex(-1);

    router.push(
      `/stocks/${encodeURIComponent(result.displaySymbol)}`,
    );
  }

  function handleKeyDown(
    event: React.KeyboardEvent<HTMLInputElement>,
  ): void {
    if (event.key === "Escape") {
      setResults([]);
      setActiveIndex(-1);
      return;
    }

    if (results.length === 0) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();

      setActiveIndex((currentIndex) =>
        currentIndex >= results.length - 1
          ? 0
          : currentIndex + 1,
      );
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();

      setActiveIndex((currentIndex) =>
        currentIndex <= 0
          ? results.length - 1
          : currentIndex - 1,
      );
    }

    if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      openStock(results[activeIndex]);
    }
  }

  const normalizedQuery = query.trim();

  const showNoResults =
    normalizedQuery.length > 0 &&
    hasSearched &&
    !isLoading &&
    !errorMessage &&
    results.length === 0;

  const showDropdown =
    normalizedQuery.length > 0 &&
    (isLoading ||
      Boolean(errorMessage) ||
      results.length > 0 ||
      showNoResults);

  return (
    <div className="relative w-full max-w-xl">
      <div className="relative">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search stocks, e.g. Reliance or HDFC Bank"
          aria-label="Search Indian stocks"
          aria-expanded={showDropdown}
          aria-autocomplete="list"
          className="w-full rounded-xl border border-white/10 bg-zinc-950 px-4 py-3 pr-12 text-sm text-white outline-none transition placeholder:text-zinc-600 focus:border-emerald-400/50"
        />

        <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-zinc-500">
          {isLoading ? (
            <span className="text-xs">...</span>
          ) : (
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              className="h-5 w-5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-4-4" />
            </svg>
          )}
        </div>
      </div>

      {showDropdown && (
        <div
          role="listbox"
          className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-50 overflow-hidden rounded-xl border border-white/10 bg-zinc-950 shadow-2xl"
        >
          {isLoading && (
            <div className="px-4 py-4 text-sm text-zinc-500">
              Searching...
            </div>
          )}

          {!isLoading && errorMessage && (
            <div className="px-4 py-4 text-sm text-red-300">
              {errorMessage}
            </div>
          )}

          {showNoResults && (
            <div className="px-4 py-4 text-sm text-zinc-500">
              No stocks found for “{normalizedQuery}”.
            </div>
          )}

          {!isLoading &&
            !errorMessage &&
            results.map((result, index) => (
              <button
                key={`${result.exchange}-${result.symbol}`}
                type="button"
                role="option"
                aria-selected={activeIndex === index}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => openStock(result)}
                className={`flex w-full items-center justify-between gap-4 border-b border-white/5 px-4 py-3 text-left transition last:border-b-0 ${
                  activeIndex === index
                    ? "bg-emerald-500/10"
                    : "hover:bg-white/5"
                }`}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-zinc-100">
                    {result.symbol}
                  </p>

                  <p className="truncate text-xs text-zinc-500">
                    {result.companyName}
                  </p>
                </div>

                <div className="shrink-0 text-right">
                  <p className="text-xs font-medium text-emerald-400">
                    {result.exchange}
                  </p>

                  <p className="text-[11px] text-zinc-600">
                    {result.displaySymbol}
                  </p>
                </div>
              </button>
            ))}
        </div>
      )}
    </div>
  );
}