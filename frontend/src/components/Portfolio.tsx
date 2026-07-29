"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  addPortfolioHolding,
  deletePortfolioHolding,
  getPortfolio,
  PortfolioApiError,
  searchStocks,
  updatePortfolioHolding,
  type PortfolioPosition,
  type PortfolioResponse,
  type StockSearchResult,
} from "@/services/api";

const EMPTY_PORTFOLIO: PortfolioResponse = {
  positions: [],
  count: 0,
  totalInvested: "0.00",
  totalCurrentValue: "0.00",
  totalProfitLoss: "0.00",
  totalReturnPercent: "0.00",
};

type FormState = {
  displaySymbol: string;
  quantity: string;
  averageBuyPrice: string;
};

const EMPTY_FORM: FormState = {
  displaySymbol: "",
  quantity: "",
  averageBuyPrice: "",
};

function formatCurrency(value: string): string {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return value;
  }

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(number);
}

function formatNumber(
  value: string,
  maximumFractionDigits = 6,
): string {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return value;
  }

  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits,
  }).format(number);
}

function formatPercent(value: string): string {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return `${value}%`;
  }

  const sign = number > 0 ? "+" : "";

  return `${sign}${number.toFixed(2)}%`;
}

function gainClassName(value: string): string {
  const number = Number(value);

  if (number > 0) {
    return "text-emerald-400";
  }

  if (number < 0) {
    return "text-red-400";
  }

  return "text-zinc-400";
}

export default function Portfolio() {
  const [portfolio, setPortfolio] =
    useState<PortfolioResponse>(EMPTY_PORTFOLIO);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingSymbol, setEditingSymbol] = useState<string | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingSymbol, setDeletingSymbol] = useState<string | null>(
    null,
  );
  const [message, setMessage] = useState<string | null>(null);
  const [hasError, setHasError] = useState(false);

  const [searchResults, setSearchResults] = useState<
    StockSearchResult[]
  >([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [activeSearchIndex, setActiveSearchIndex] = useState(-1);
  const [searchError, setSearchError] = useState<string | null>(null);

  const searchRequestIdRef = useRef(0);

  const loadPortfolio = useCallback(async () => {
    setIsLoading(true);

    try {
      const response = await getPortfolio();
      setPortfolio(response);
      setHasError(false);
    } catch {
      setPortfolio(EMPTY_PORTFOLIO);
      setHasError(true);
      setMessage(
        "Portfolio could not be loaded. Check that the backend and MySQL are running.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPortfolio();
  }, [loadPortfolio]);

  useEffect(() => {
    if (editingSymbol) {
      searchRequestIdRef.current += 1;
      setSearchResults([]);
      setIsSearching(false);
      setHasSearched(false);
      setActiveSearchIndex(-1);
      setSearchError(null);
      return;
    }

    const query = form.displaySymbol.trim();

    if (!query) {
      searchRequestIdRef.current += 1;
      setSearchResults([]);
      setIsSearching(false);
      setHasSearched(false);
      setActiveSearchIndex(-1);
      setSearchError(null);
      return;
    }

    setHasSearched(false);

    const timeoutId = window.setTimeout(async () => {
      const requestId = ++searchRequestIdRef.current;

      setIsSearching(true);
      setSearchError(null);

      try {
        const response = await searchStocks(query, 8);

        if (requestId !== searchRequestIdRef.current) {
          return;
        }

        setSearchResults(response.results);
        setActiveSearchIndex(
          response.results.length > 0 ? 0 : -1,
        );
        setHasSearched(true);
      } catch {
        if (requestId !== searchRequestIdRef.current) {
          return;
        }

        setSearchResults([]);
        setActiveSearchIndex(-1);
        setHasSearched(true);
        setSearchError("Unable to search stocks right now.");
      } finally {
        if (requestId === searchRequestIdRef.current) {
          setIsSearching(false);
        }
      }
    }, 300);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [editingSymbol, form.displaySymbol]);

  function updateForm(field: keyof FormState, value: string): void {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function selectStock(result: StockSearchResult): void {
    setForm((current) => ({
      ...current,
      displaySymbol: result.displaySymbol,
    }));
    setSearchResults([]);
    setActiveSearchIndex(-1);
    setHasSearched(false);
    setSearchError(null);
  }

  function handleSymbolKeyDown(
    event: React.KeyboardEvent<HTMLInputElement>,
  ): void {
    if (event.key === "Escape") {
      setSearchResults([]);
      setActiveSearchIndex(-1);
      return;
    }

    if (searchResults.length === 0) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();

      setActiveSearchIndex((currentIndex) =>
        currentIndex >= searchResults.length - 1
          ? 0
          : currentIndex + 1,
      );
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();

      setActiveSearchIndex((currentIndex) =>
        currentIndex <= 0
          ? searchResults.length - 1
          : currentIndex - 1,
      );
    }

    if (event.key === "Enter" && activeSearchIndex >= 0) {
      event.preventDefault();
      selectStock(searchResults[activeSearchIndex]);
    }
  }

  function beginEdit(position: PortfolioPosition): void {
    setEditingSymbol(position.displaySymbol);
    setForm({
      displaySymbol: position.displaySymbol,
      quantity: position.quantity,
      averageBuyPrice: position.averageBuyPrice,
    });
    setSearchResults([]);
    setActiveSearchIndex(-1);
    setHasSearched(false);
    setSearchError(null);
    setMessage(null);
    setHasError(false);
  }

  function cancelEdit(): void {
    setEditingSymbol(null);
    setForm(EMPTY_FORM);
    setSearchResults([]);
    setActiveSearchIndex(-1);
    setHasSearched(false);
    setSearchError(null);
    setMessage(null);
    setHasError(false);
  }

  function validateForm(): string | null {
    const normalizedSymbol = form.displaySymbol.trim().toUpperCase();
    const quantity = Number(form.quantity);
    const averagePrice = Number(form.averageBuyPrice);

    if (!/^[A-Z0-9][A-Z0-9&-]{0,29}\.(NSE|BSE)$/.test(
      normalizedSymbol,
    )) {
      return "Use a symbol such as RELIANCE.NSE or 500325.BSE.";
    }

    if (!Number.isFinite(quantity) || quantity <= 0) {
      return "Quantity must be greater than zero.";
    }

    if (!Number.isFinite(averagePrice) || averagePrice <= 0) {
      return "Average buy price must be greater than zero.";
    }

    return null;
  }

  async function handleSubmit(): Promise<void> {
    const validationError = validateForm();

    if (validationError) {
      setHasError(true);
      setMessage(validationError);
      return;
    }

    setIsSaving(true);
    setMessage(null);
    setHasError(false);

    try {
      if (editingSymbol) {
        await updatePortfolioHolding(
          editingSymbol,
          form.quantity,
          form.averageBuyPrice,
        );
        setMessage(`${editingSymbol} was updated.`);
      } else {
        const normalizedSymbol = form.displaySymbol
          .trim()
          .toUpperCase();

        await addPortfolioHolding(
          normalizedSymbol,
          form.quantity,
          form.averageBuyPrice,
        );
        setMessage(`${normalizedSymbol} was added.`);
      }

      setEditingSymbol(null);
      setForm(EMPTY_FORM);
      await loadPortfolio();
    } catch (error) {
      setHasError(true);

      if (
        error instanceof PortfolioApiError &&
        error.code === "PORTFOLIO_HOLDING_ALREADY_EXISTS"
      ) {
        setMessage(
          "This stock already exists. Use Edit to change its quantity or average price.",
        );
      } else {
        setMessage(
          error instanceof Error
            ? error.message
            : "The portfolio could not be updated.",
        );
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(displaySymbol: string): Promise<void> {
    const confirmed = window.confirm(
      `Delete ${displaySymbol} from your portfolio?`,
    );

    if (!confirmed) {
      return;
    }

    setDeletingSymbol(displaySymbol);
    setMessage(null);
    setHasError(false);

    try {
      await deletePortfolioHolding(displaySymbol);

      if (editingSymbol === displaySymbol) {
        cancelEdit();
      }

      setMessage(`${displaySymbol} was deleted.`);
      await loadPortfolio();
    } catch (error) {
      setHasError(true);
      setMessage(
        error instanceof Error
          ? error.message
          : `${displaySymbol} could not be deleted.`,
      );
    } finally {
      setDeletingSymbol(null);
    }
  }

  const normalizedSearchQuery = form.displaySymbol.trim();

  const showNoSearchResults =
    !editingSymbol &&
    normalizedSearchQuery.length > 0 &&
    hasSearched &&
    !isSearching &&
    !searchError &&
    searchResults.length === 0;

  const showSearchDropdown =
    !editingSymbol &&
    normalizedSearchQuery.length > 0 &&
    (
      isSearching ||
      Boolean(searchError) ||
      searchResults.length > 0 ||
      showNoSearchResults
    );

  return (
    <section className="mt-8 rounded-2xl border border-white/10 bg-zinc-950 p-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
        <div>
          <h2 className="text-xl font-semibold">My Portfolio</h2>
          <p className="mt-1 text-sm text-zinc-500">
            Persistent holdings with live market valuation
          </p>
        </div>

        {!isLoading && portfolio.count > 0 && (
          <span className="w-fit rounded-full border border-white/10 bg-black/40 px-3 py-1 text-xs text-zinc-400">
            {portfolio.count}{" "}
            {portfolio.count === 1 ? "holding" : "holdings"}
          </span>
        )}
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          label="Total invested"
          value={formatCurrency(portfolio.totalInvested)}
        />
        <SummaryCard
          label="Current value"
          value={formatCurrency(portfolio.totalCurrentValue)}
        />
        <SummaryCard
          label="Total profit / loss"
          value={formatCurrency(portfolio.totalProfitLoss)}
          valueClassName={gainClassName(portfolio.totalProfitLoss)}
        />
        <SummaryCard
          label="Total return"
          value={formatPercent(portfolio.totalReturnPercent)}
          valueClassName={gainClassName(portfolio.totalReturnPercent)}
        />
      </div>

      <div className="mt-6 rounded-xl border border-white/10 bg-black/40 p-4">
        <div>
          <h3 className="font-medium text-zinc-100">
            {editingSymbol ? `Edit ${editingSymbol}` : "Add a holding"}
          </h3>
          <p className="mt-1 text-xs text-zinc-500">
            Enter the quantity currently held and your average purchase
            price.
          </p>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="relative text-sm text-zinc-300">
            <label htmlFor="portfolio-stock-symbol">
              Stock symbol
            </label>

            <input
              id="portfolio-stock-symbol"
              type="search"
              value={form.displaySymbol}
              onChange={(event) =>
                updateForm("displaySymbol", event.target.value)
              }
              onKeyDown={handleSymbolKeyDown}
              disabled={Boolean(editingSymbol) || isSaving}
              placeholder="Search Reliance, TCS or HDFC Bank"
              autoComplete="off"
              aria-label="Search stock for portfolio"
              aria-expanded={showSearchDropdown}
              aria-autocomplete="list"
              className="mt-2 w-full rounded-xl border border-white/10 bg-zinc-950 px-3 py-2.5 pr-10 text-sm text-white outline-none placeholder:text-zinc-600 focus:border-emerald-400/50 disabled:cursor-not-allowed disabled:opacity-60"
            />

            {!editingSymbol && (
              <div className="pointer-events-none absolute right-3 top-[2.55rem] text-zinc-500">
                {isSearching ? (
                  <span className="text-xs">...</span>
                ) : (
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 24 24"
                    className="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <circle cx="11" cy="11" r="7" />
                    <path d="m20 20-4-4" />
                  </svg>
                )}
              </div>
            )}

            {showSearchDropdown && (
              <div
                role="listbox"
                className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-50 overflow-hidden rounded-xl border border-white/10 bg-zinc-950 shadow-2xl"
              >
                {isSearching && (
                  <div className="px-4 py-4 text-sm text-zinc-500">
                    Searching...
                  </div>
                )}

                {!isSearching && searchError && (
                  <div className="px-4 py-4 text-sm text-red-300">
                    {searchError}
                  </div>
                )}

                {showNoSearchResults && (
                  <div className="px-4 py-4 text-sm text-zinc-500">
                    No stocks found for "{normalizedSearchQuery}"
                  </div>
                )}

                {!isSearching &&
                  !searchError &&
                  searchResults.map((result, index) => (
                    <button
                      key={`${result.exchange}:${result.symbol}`}
                      type="button"
                      role="option"
                      aria-selected={index === activeSearchIndex}
                      onMouseDown={(event) => {
                        event.preventDefault();
                        selectStock(result);
                      }}
                      className={`flex w-full items-center justify-between gap-4 border-t border-white/5 px-4 py-3 text-left transition first:border-t-0 ${
                        index === activeSearchIndex
                          ? "bg-emerald-500/10"
                          : "hover:bg-white/5"
                      }`}
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-zinc-100">
                          {result.companyName}
                        </p>
                        <p className="mt-1 text-xs text-zinc-500">
                          {result.displaySymbol}
                        </p>
                      </div>

                      <span className="shrink-0 rounded-full border border-white/10 bg-black/40 px-2 py-1 text-xs text-zinc-400">
                        {result.exchange}
                      </span>
                    </button>
                  ))}
              </div>
            )}
          </div>

          <label className="text-sm text-zinc-300">
            Quantity
            <input
              type="number"
              min="0"
              step="0.000001"
              value={form.quantity}
              onChange={(event) =>
                updateForm("quantity", event.target.value)
              }
              disabled={isSaving}
              placeholder="5"
              className="mt-2 w-full rounded-xl border border-white/10 bg-zinc-950 px-3 py-2.5 text-sm text-white outline-none placeholder:text-zinc-600 focus:border-emerald-400/50 disabled:cursor-not-allowed disabled:opacity-60"
            />
          </label>

          <label className="text-sm text-zinc-300">
            Average buy price
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.averageBuyPrice}
              onChange={(event) =>
                updateForm("averageBuyPrice", event.target.value)
              }
              disabled={isSaving}
              placeholder="1200.50"
              className="mt-2 w-full rounded-xl border border-white/10 bg-zinc-950 px-3 py-2.5 text-sm text-white outline-none placeholder:text-zinc-600 focus:border-emerald-400/50 disabled:cursor-not-allowed disabled:opacity-60"
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={isSaving}
            className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving
              ? "Saving..."
              : editingSymbol
                ? "Save changes"
                : "Add holding"}
          </button>

          {editingSymbol && (
            <button
              type="button"
              onClick={cancelEdit}
              disabled={isSaving}
              className="rounded-xl border border-white/10 bg-zinc-900 px-4 py-2.5 text-sm text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-50"
            >
              Cancel
            </button>
          )}

          {message && (
            <p
              aria-live="polite"
              className={`text-sm ${
                hasError ? "text-red-400" : "text-zinc-400"
              }`}
            >
              {message}
            </p>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="mt-5 rounded-xl border border-white/5 bg-black/40 px-4 py-7 text-sm text-zinc-500">
          Loading portfolio...
        </div>
      ) : portfolio.positions.length === 0 ? (
        <div className="mt-5 rounded-xl border border-dashed border-white/10 bg-black/30 px-5 py-8 text-center">
          <p className="text-sm font-medium text-zinc-300">
            Your portfolio is empty
          </p>
          <p className="mt-2 text-sm text-zinc-500">
            Add your first holding using the form above.
          </p>
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          {portfolio.positions.map((position) => (
            <article
              key={position.id}
              className="rounded-xl border border-white/5 bg-black/50 p-5"
            >
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div>
                  <Link
                    href={`/stocks/${encodeURIComponent(
                      position.displaySymbol,
                    )}`}
                    className="font-semibold text-zinc-100 transition hover:text-emerald-300"
                  >
                    {position.companyName}
                  </Link>
                  <p className="mt-1 text-xs text-zinc-500">
                    {position.displaySymbol}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => beginEdit(position)}
                    className="rounded-lg border border-white/10 bg-zinc-900 px-3 py-2 text-xs text-zinc-300 transition hover:bg-zinc-800"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      void handleDelete(position.displaySymbol)
                    }
                    disabled={
                      deletingSymbol === position.displaySymbol
                    }
                    className="rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs text-red-300 transition hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {deletingSymbol === position.displaySymbol
                      ? "Deleting..."
                      : "Delete"}
                  </button>
                </div>
              </div>

              <div className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-8">
                <PositionMetric
                  label="Quantity"
                  value={formatNumber(position.quantity)}
                />
                <PositionMetric
                  label="Average price"
                  value={formatCurrency(position.averageBuyPrice)}
                />
                <PositionMetric
                  label="Current price"
                  value={formatCurrency(position.currentPrice)}
                />
                <PositionMetric
                  label="Invested"
                  value={formatCurrency(position.investedAmount)}
                />
                <PositionMetric
                  label="Current value"
                  value={formatCurrency(position.currentValue)}
                />
                <PositionMetric
                  label="Profit / loss"
                  value={formatCurrency(position.profitLoss)}
                  valueClassName={gainClassName(position.profitLoss)}
                />
                <PositionMetric
                  label="Return"
                  value={formatPercent(position.returnPercent)}
                  valueClassName={gainClassName(position.returnPercent)}
                />
                <PositionMetric
                  label="Allocation"
                  value={`${formatNumber(
                    position.allocationPercent,
                    2,
                  )}%`}
                />
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

type SummaryCardProps = {
  label: string;
  value: string;
  valueClassName?: string;
};

function SummaryCard({
  label,
  value,
  valueClassName = "text-zinc-100",
}: SummaryCardProps) {
  return (
    <div className="rounded-xl border border-white/5 bg-black/50 p-4">
      <p className="text-xs uppercase tracking-wide text-zinc-500">
        {label}
      </p>
      <p className={`mt-2 text-lg font-semibold ${valueClassName}`}>
        {value}
      </p>
    </div>
  );
}

type PositionMetricProps = {
  label: string;
  value: string;
  valueClassName?: string;
};

function PositionMetric({
  label,
  value,
  valueClassName = "text-zinc-200",
}: PositionMetricProps) {
  return (
    <div>
      <p className="text-xs text-zinc-600">{label}</p>
      <p className={`mt-1 break-words text-sm font-medium ${valueClassName}`}>
        {value}
      </p>
    </div>
  );
}
