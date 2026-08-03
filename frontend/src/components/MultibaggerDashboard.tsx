"use client";

import Link from "next/link";
import {
  useEffect,
  useState,
  type FormEvent,
} from "react";

import {
  getMultibaggerPotential,
  getMultibaggerRankings,
  type MultibaggerObservationType,
  type MultibaggerPotential,
  type MultibaggerPotentialCategory,
  type MultibaggerRankingsResponse,
} from "@/services/api";

function formatLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    );
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(parsed);
}

function formatRatio(value: string | null): string {
  if (value === null) {
    return "Not available";
  }

  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return value;
  }

  return `${(parsed * 100).toFixed(1)}%`;
}

function formatNumber(value: string | null): string {
  if (value === null) {
    return "Not available";
  }

  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return value;
  }

  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
  }).format(parsed);
}

function formatMarketCap(value: string | null): string {
  if (value === null) {
    return "Not available";
  }

  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return value;
  }

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(parsed);
}

function categoryClasses(
  category: MultibaggerPotentialCategory,
): string {
  if (category === "very_high") {
    return "border-emerald-400/40 bg-emerald-400/15 text-emerald-200";
  }

  if (category === "high") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  }

  if (category === "moderate") {
    return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  }

  if (category === "low") {
    return "border-orange-500/30 bg-orange-500/10 text-orange-300";
  }

  return "border-red-500/30 bg-red-500/10 text-red-300";
}

function observationClasses(
  type: MultibaggerObservationType,
): string {
  if (type === "positive") {
    return "border-emerald-500/20 bg-emerald-500/5";
  }

  if (type === "negative") {
    return "border-red-500/20 bg-red-500/5";
  }

  return "border-white/10 bg-black/30";
}

function observationMarkerClasses(
  type: MultibaggerObservationType,
): string {
  if (type === "positive") {
    return "bg-emerald-400";
  }

  if (type === "negative") {
    return "bg-red-400";
  }

  return "bg-zinc-500";
}

export default function MultibaggerDashboard() {
  const [rankings, setRankings] =
    useState<MultibaggerRankingsResponse | null>(null);

  const [selectedStock, setSelectedStock] =
    useState<MultibaggerPotential | null>(null);

  const [symbol, setSymbol] =
    useState("RELIANCE.NSE");

  const [minimumScore, setMinimumScore] =
    useState(50);

  const [limit, setLimit] = useState(10);

  const [isRankingLoading, setIsRankingLoading] =
    useState(true);

  const [isStockLoading, setIsStockLoading] =
    useState(false);

  const [rankingError, setRankingError] =
    useState<string | null>(null);

  const [stockError, setStockError] =
    useState<string | null>(null);

  async function loadRankings(
    score = minimumScore,
    resultLimit = limit,
  ): Promise<void> {
    setIsRankingLoading(true);
    setRankingError(null);

    try {
      const result = await getMultibaggerRankings(
        score,
        resultLimit,
      );

      setRankings(result);
    } catch (error) {
      setRankings(null);
      setRankingError(
        error instanceof Error
          ? error.message
          : "Unable to load the rankings.",
      );
    } finally {
      setIsRankingLoading(false);
    }
  }

  useEffect(() => {
    let isActive = true;

    async function loadInitialRankings(): Promise<void> {
      setIsRankingLoading(true);
      setRankingError(null);

      try {
        const result = await getMultibaggerRankings(
          50,
          10,
        );

        if (isActive) {
          setRankings(result);
        }
      } catch (error) {
        if (isActive) {
          setRankings(null);
          setRankingError(
            error instanceof Error
              ? error.message
              : "Unable to load the rankings.",
          );
        }
      } finally {
        if (isActive) {
          setIsRankingLoading(false);
        }
      }
    }

    void loadInitialRankings();

    return () => {
      isActive = false;
    };
  }, []);

  async function handleRankingSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    await loadRankings();
  }

  async function analyseSymbol(
    displaySymbol: string,
  ): Promise<void> {
    const normalized =
      displaySymbol.trim().toUpperCase();

    if (
      !/^[A-Z0-9&_-]+\.(NSE|BSE)$/.test(normalized)
    ) {
      setStockError(
        "Use SYMBOL.NSE or SYMBOL.BSE format.",
      );
      return;
    }

    setIsStockLoading(true);
    setStockError(null);

    try {
      const result =
        await getMultibaggerPotential(normalized);

      setSelectedStock(result);
      setSymbol(normalized);
    } catch (error) {
      setSelectedStock(null);
      setStockError(
        error instanceof Error
          ? error.message
          : "Unable to analyse this stock.",
      );
    } finally {
      setIsStockLoading(false);
    }
  }

  async function handleStockSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    await analyseSymbol(symbol);
  }

  return (
    <div>
      <header className="max-w-4xl">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-emerald-400">
          AlphaEdge Multibagger Radar
        </p>

        <h1 className="mt-3 text-3xl font-semibold sm:text-5xl">
          Long-term potential screening
        </h1>

        <p className="mt-4 text-sm leading-6 text-zinc-400 sm:text-base">
          Compare companies using growth quality, financial
          strength, valuation, momentum and risk. The score is a
          transparent screening tool?not a promise of future
          returns.
        </p>
      </header>

      <section className="mt-8 rounded-2xl border border-white/10 bg-black/40 p-5 sm:p-6">
        <h2 className="text-xl font-semibold">
          Analyse one stock
        </h2>

        <form
          onSubmit={(event) => void handleStockSubmit(event)}
          className="mt-4 grid gap-4 sm:grid-cols-[1fr_auto]"
        >
          <input
            value={symbol}
            onChange={(event) =>
              setSymbol(event.target.value)
            }
            placeholder="RELIANCE.NSE"
            className="rounded-xl border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm outline-none transition placeholder:text-zinc-700 focus:border-emerald-500/50"
          />

          <button
            type="submit"
            disabled={isStockLoading}
            className="rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-black transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isStockLoading
              ? "Analysing..."
              : "Check potential"}
          </button>
        </form>

        {stockError && (
          <p className="mt-4 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300">
            {stockError}
          </p>
        )}
      </section>

      {selectedStock && (
        <StockPotentialDetails stock={selectedStock} />
      )}

      <section className="mt-8">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <h2 className="text-2xl font-semibold">
              Ranked candidates
            </h2>

            <p className="mt-2 text-sm text-zinc-500">
              Cached screening across the configured stock
              universe.
            </p>
          </div>

          <form
            onSubmit={(event) =>
              void handleRankingSubmit(event)
            }
            className="grid gap-3 sm:grid-cols-[150px_130px_auto]"
          >
            <label className="text-xs text-zinc-500">
              Minimum score
              <input
                type="number"
                min={0}
                max={100}
                value={minimumScore}
                onChange={(event) =>
                  setMinimumScore(
                    Number(event.target.value),
                  )
                }
                className="mt-1 w-full rounded-lg border border-zinc-800 bg-black px-3 py-2 text-sm text-white outline-none"
              />
            </label>

            <label className="text-xs text-zinc-500">
              Result limit
              <select
                value={limit}
                onChange={(event) =>
                  setLimit(Number(event.target.value))
                }
                className="mt-1 w-full rounded-lg border border-zinc-800 bg-black px-3 py-2 text-sm text-white outline-none"
              >
                {[5, 10, 20, 50].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>

            <button
              type="submit"
              disabled={isRankingLoading}
              className="self-end rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-5 py-2 text-sm font-semibold text-emerald-300 transition hover:bg-emerald-500/15 disabled:opacity-50"
            >
              Apply
            </button>
          </form>
        </div>

        {isRankingLoading && (
          <div className="mt-6 rounded-2xl border border-white/10 bg-black/30 p-8 text-center">
            <div className="mx-auto h-7 w-7 animate-spin rounded-full border-2 border-zinc-700 border-t-emerald-400" />

            <p className="mt-4 text-sm text-zinc-500">
              Screening the configured universe...
            </p>
          </div>
        )}

        {rankingError && (
          <p className="mt-6 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300">
            {rankingError}
          </p>
        )}

        {!isRankingLoading &&
          rankings &&
          rankings.rankings.length === 0 && (
            <div className="mt-6 rounded-2xl border border-white/10 bg-black/30 p-8 text-center">
              <p className="text-sm text-zinc-400">
                No stocks matched the selected minimum score.
              </p>
            </div>
          )}

        {!isRankingLoading &&
          rankings &&
          rankings.rankings.length > 0 && (
            <>
              <div className="mt-6 grid gap-4 lg:grid-cols-2">
                {rankings.rankings.map(
                  (stock, index) => (
                    <RankingCard
                      key={stock.displaySymbol}
                      stock={stock}
                      rank={index + 1}
                      onAnalyse={() =>
                        void analyseSymbol(
                          stock.displaySymbol,
                        )
                      }
                    />
                  ),
                )}
              </div>

              <div className="mt-5 flex flex-col gap-2 text-xs text-zinc-600 sm:flex-row sm:justify-between">
                <span>
                  Returned {rankings.returnedCount} of{" "}
                  {rankings.successfulCount} successfully
                  screened stocks.
                </span>

                <span>
                  Generated{" "}
                  {formatTimestamp(rankings.generatedAt)} IST
                </span>
              </div>

              {rankings.failedSymbols.length > 0 && (
                <p className="mt-3 text-xs text-amber-300/70">
                  Temporarily unavailable:{" "}
                  {rankings.failedSymbols.join(", ")}
                </p>
              )}
            </>
          )}
      </section>

      <section className="mt-8 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5">
        <p className="text-sm leading-6 text-amber-100/80">
          Multibagger Potential is a deterministic screening
          score. It is not investment advice, a recommendation,
          or a guarantee that any stock will produce multibagger
          returns.
        </p>
      </section>
    </div>
  );
}

function RankingCard({
  stock,
  rank,
  onAnalyse,
}: {
  stock: MultibaggerPotential;
  rank: number;
  onAnalyse: () => void;
}) {
  return (
    <article className="rounded-2xl border border-white/10 bg-black/35 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold text-zinc-600">
            Rank #{rank}
          </p>

          <h3 className="mt-2 text-xl font-semibold">
            {stock.companyName}
          </h3>

          <p className="mt-1 text-sm text-zinc-500">
            {stock.displaySymbol}
          </p>
        </div>

        <div className="text-right">
          <p className="text-3xl font-semibold text-white">
            {stock.potentialScore}
          </p>

          <span
            className={`mt-2 inline-block rounded-full border px-3 py-1 text-xs font-medium ${categoryClasses(
              stock.potentialCategory,
            )}`}
          >
            {formatLabel(stock.potentialCategory)}
          </span>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <MiniScore
          label="Growth"
          value={stock.growthQualityScore}
        />

        <MiniScore
          label="Financial"
          value={stock.financialStrengthScore}
        />

        <MiniScore
          label="Valuation"
          value={stock.valuationAttractivenessScore}
        />

        <MiniScore
          label="Momentum"
          value={stock.momentumScore}
        />

        <MiniScore
          label="Risk"
          value={stock.riskQualityScore}
        />

        <MiniScore
          label="Data"
          value={stock.dataCompletenessScore}
        />
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onAnalyse}
          className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-black transition hover:bg-emerald-400"
        >
          View potential
        </button>

        <Link
          href={`/stocks/${encodeURIComponent(
            stock.displaySymbol,
          )}`}
          className="rounded-lg border border-white/10 px-4 py-2 text-xs font-medium text-zinc-300 transition hover:border-zinc-700 hover:text-white"
        >
          Full stock page
        </Link>
      </div>
    </article>
  );
}

function StockPotentialDetails({
  stock,
}: {
  stock: MultibaggerPotential;
}) {
  return (
    <section className="mt-8 rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.03] p-5 sm:p-7">
      <div className="flex flex-col justify-between gap-5 sm:flex-row">
        <div>
          <p className="text-sm text-zinc-500">
            {stock.displaySymbol}
          </p>

          <h2 className="mt-2 text-2xl font-semibold">
            {stock.companyName}
          </h2>

          <span
            className={`mt-3 inline-block rounded-full border px-3 py-1 text-xs font-medium ${categoryClasses(
              stock.potentialCategory,
            )}`}
          >
            {formatLabel(stock.potentialCategory)} potential
          </span>
        </div>

        <div className="sm:text-right">
          <p className="text-5xl font-semibold text-emerald-300">
            {stock.potentialScore}
          </p>

          <p className="mt-1 text-xs uppercase tracking-wide text-zinc-600">
            Potential score
          </p>
        </div>
      </div>

      <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <ScoreBar
          label="Growth quality"
          score={stock.growthQualityScore}
        />

        <ScoreBar
          label="Financial strength"
          score={stock.financialStrengthScore}
        />

        <ScoreBar
          label="Valuation"
          score={stock.valuationAttractivenessScore}
        />

        <ScoreBar
          label="Momentum"
          score={stock.momentumScore}
        />

        <ScoreBar
          label="Risk quality"
          score={stock.riskQualityScore}
        />
      </div>

      <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Market cap"
          value={formatMarketCap(stock.marketCap)}
        />

        <Metric
          label="Revenue growth"
          value={formatRatio(stock.revenueGrowth)}
        />

        <Metric
          label="Earnings growth"
          value={formatRatio(stock.earningsGrowth)}
        />

        <Metric
          label="Return on equity"
          value={formatRatio(stock.returnOnEquity)}
        />

        <Metric
          label="Debt to equity"
          value={formatNumber(stock.debtToEquity)}
        />

        <Metric
          label="Trailing P/E"
          value={formatNumber(stock.trailingPe)}
        />

        <Metric
          label="Price to book"
          value={formatNumber(stock.priceToBook)}
        />

        <Metric
          label="Data completeness"
          value={`${stock.dataCompletenessScore}/100`}
        />
      </div>

      <div className="mt-7">
        <h3 className="text-lg font-semibold">
          Key observations
        </h3>

        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {stock.observations.map(
            (observation, index) => (
              <div
                key={`${observation.category}-${index}`}
                className={`rounded-xl border p-4 ${observationClasses(
                  observation.observationType,
                )}`}
              >
                <div className="flex gap-3">
                  <span
                    className={`mt-2 h-2 w-2 shrink-0 rounded-full ${observationMarkerClasses(
                      observation.observationType,
                    )}`}
                  />

                  <div>
                    <p className="text-sm font-semibold text-zinc-200">
                      {observation.category}
                    </p>

                    <p className="mt-1 text-sm leading-6 text-zinc-400">
                      {observation.message}
                    </p>
                  </div>
                </div>
              </div>
            ),
          )}
        </div>
      </div>

      <p className="mt-6 border-t border-white/10 pt-4 text-xs text-zinc-600">
        Calculated {formatTimestamp(stock.calculatedAt)} IST
        {" | "}
        Methodology: {stock.methodologyVersion}
      </p>
    </section>
  );
}

function MiniScore({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-lg border border-white/5 bg-zinc-950 px-3 py-2">
      <p className="text-xs text-zinc-600">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold text-zinc-300">
        {value}
      </p>
    </div>
  );
}

function ScoreBar({
  label,
  score,
}: {
  label: string;
  score: number;
}) {
  const safeScore = Math.max(
    0,
    Math.min(100, score),
  );

  return (
    <div className="rounded-xl border border-white/10 bg-black/30 p-4">
      <div className="flex justify-between gap-3">
        <p className="text-xs text-zinc-500">
          {label}
        </p>

        <p className="text-sm font-semibold">
          {score}
        </p>
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-zinc-800">
        <div
          className="h-full rounded-full bg-emerald-400"
          style={{ width: `${safeScore}%` }}
        />
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/30 p-4">
      <p className="text-xs uppercase tracking-wide text-zinc-600">
        {label}
      </p>

      <p className="mt-2 break-words text-sm font-semibold text-zinc-200">
        {value}
      </p>
    </div>
  );
}
