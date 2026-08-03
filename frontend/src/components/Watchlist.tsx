"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  getStockQuote,
  getWatchlist,
  removeFromWatchlist,
  type StockQuote,
  type WatchlistItem,
} from "@/services/api";

type WatchlistRow = {
  item: WatchlistItem;
  quote: StockQuote | null;
};

function formatPrice(value: string): string {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return value;
  }

  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numericValue);
}

function formatSavedDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeZone: "Asia/Kolkata",
  }).format(date);
}

export default function Watchlist() {
  const [rows, setRows] = useState<WatchlistRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [removingSymbol, setRemovingSymbol] = useState<string | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  const loadWatchlist = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const watchlist = await getWatchlist();

      const populatedRows = await Promise.all(
        watchlist.items.map(async (item) => {
          try {
            const quote = await getStockQuote(item.displaySymbol);

            return {
              item,
              quote,
            };
          } catch {
            return {
              item,
              quote: null,
            };
          }
        }),
      );

      setRows(populatedRows);
    } catch {
      setError(
        "Watchlist could not be loaded. Make sure the backend and MySQL are running.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWatchlist();
  }, [loadWatchlist]);

  async function handleRemove(displaySymbol: string): Promise<void> {
    setRemovingSymbol(displaySymbol);
    setError(null);

    try {
      await removeFromWatchlist(displaySymbol);

      setRows((currentRows) =>
        currentRows.filter(
          (row) => row.item.displaySymbol !== displaySymbol,
        ),
      );
    } catch {
      setError(`${displaySymbol} could not be removed.`);
    } finally {
      setRemovingSymbol(null);
    }
  }

  return (
    <section className="mt-8 rounded-2xl border border-white/10 bg-zinc-950 p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">My Watchlist</h2>

          <p className="mt-1 text-sm text-zinc-500">
            Stocks saved in your persistent MySQL watchlist
          </p>
        </div>

        {!isLoading && rows.length > 0 && (
          <span className="rounded-full border border-white/10 bg-black/40 px-3 py-1 text-xs text-zinc-400">
            {rows.length} {rows.length === 1 ? "stock" : "stocks"}
          </span>
        )}
      </div>

      {error && (
        <div
          aria-live="polite"
          className="mt-5 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300"
        >
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="mt-5 rounded-xl border border-white/5 bg-black/40 px-4 py-6 text-sm text-zinc-500">
          Loading watchlist...
        </div>
      ) : rows.length === 0 ? (
        <div className="mt-5 rounded-xl border border-dashed border-white/10 bg-black/30 px-5 py-8 text-center">
          <p className="text-sm font-medium text-zinc-300">
            Your watchlist is empty
          </p>

          <p className="mt-2 text-sm text-zinc-500">
            Search for a stock and add it from the stock details page.
          </p>
        </div>
      ) : (
        <div className="mt-5 grid gap-3">
          {rows.map(({ item, quote }) => {
            const numericChange = quote
              ? Number(quote.changePercent)
              : null;

            const changeClassName =
              numericChange === null || !Number.isFinite(numericChange)
                ? "text-zinc-500"
                : numericChange >= 0
                  ? "text-emerald-400"
                  : "text-red-400";

            return (
              <article
                key={item.id}
                className="flex flex-col gap-4 rounded-xl border border-white/5 bg-black/50 p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <Link
                    href={`/stocks/${encodeURIComponent(
                      item.displaySymbol,
                    )}`}
                    className="font-semibold text-zinc-100 transition hover:text-emerald-300"
                  >
                    {quote?.companyName ?? item.displaySymbol}
                  </Link>

                  <p className="mt-1 text-xs text-zinc-500">
                    {item.displaySymbol} · Saved{" "}
                    {formatSavedDate(item.createdAt)}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-5 sm:justify-end">
                  <div className="sm:text-right">
                    <p className="font-semibold text-zinc-100">
                      {quote ? `₹${formatPrice(quote.price)}` : "Unavailable"}
                    </p>

                    <p className={`mt-1 text-xs ${changeClassName}`}>
                      {quote
                        ? `${numericChange !== null && numericChange > 0 ? "+" : ""}${formatPrice(
                            quote.changePercent,
                          )}%`
                        : "Quote unavailable"}
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={() =>
                      void handleRemove(item.displaySymbol)
                    }
                    disabled={removingSymbol === item.displaySymbol}
                    className="rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs font-medium text-red-300 transition hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {removingSymbol === item.displaySymbol
                      ? "Removing..."
                      : "Remove"}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
