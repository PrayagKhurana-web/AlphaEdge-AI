"use client";

import { useCallback, useEffect, useState } from "react";

import {
  addToWatchlist,
  getWatchlist,
  removeFromWatchlist,
  WatchlistApiError,
} from "@/services/api";

type WatchlistButtonProps = {
  displaySymbol: string;
};

export default function WatchlistButton({
  displaySymbol,
}: WatchlistButtonProps) {
  const [isSaved, setIsSaved] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [hasError, setHasError] = useState(false);

  const loadState = useCallback(async () => {
    try {
      const watchlist = await getWatchlist();

      setIsSaved(
        watchlist.items.some(
          (item) => item.displaySymbol === displaySymbol,
        ),
      );
      setHasError(false);
    } catch {
      setMessage("Could not check watchlist status.");
      setHasError(true);
    } finally {
      setIsChecking(false);
    }
  }, [displaySymbol]);

  useEffect(() => {
    void loadState();
  }, [loadState]);

  async function handleClick(): Promise<void> {
    setIsUpdating(true);
    setMessage(null);
    setHasError(false);

    try {
      if (isSaved) {
        await removeFromWatchlist(displaySymbol);
        setIsSaved(false);
        setMessage("Removed from watchlist.");
      } else {
        await addToWatchlist(displaySymbol);
        setIsSaved(true);
        setMessage("Added to watchlist.");
      }
    } catch (error) {
      if (
        error instanceof WatchlistApiError &&
        error.code === "WATCHLIST_ITEM_ALREADY_EXISTS"
      ) {
        setIsSaved(true);
        setMessage("This stock is already in your watchlist.");
        return;
      }

      if (
        error instanceof WatchlistApiError &&
        error.code === "WATCHLIST_ITEM_NOT_FOUND"
      ) {
        setIsSaved(false);
        setMessage("This stock was already removed.");
        return;
      }

      setHasError(true);
      setMessage(
        error instanceof Error
          ? error.message
          : "Watchlist could not be updated.",
      );
    } finally {
      setIsUpdating(false);
    }
  }

  const isBusy = isChecking || isUpdating;

  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <button
        type="button"
        onClick={() => void handleClick()}
        disabled={isBusy}
        className={`rounded-xl border px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
          isSaved
            ? "border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20"
            : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20"
        }`}
      >
        {isChecking
          ? "Checking watchlist..."
          : isUpdating
            ? "Updating..."
            : isSaved
              ? "Remove from watchlist"
              : "Add to watchlist"}
      </button>

      {message && (
        <p
          aria-live="polite"
          className={`text-xs ${
            hasError ? "text-red-400" : "text-zinc-400"
          }`}
        >
          {message}
        </p>
      )}
    </div>
  );
}
