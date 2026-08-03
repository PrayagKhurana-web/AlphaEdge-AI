import Link from "next/link";

import CompanySummary from "@/components/CompanySummary";
import FinancialHealth from "@/components/FinancialHealth";
import FinancialStatements from "@/components/FinancialStatements";
import StockPriceChart from "@/components/StockPriceChart";
import StockAnalysis from "@/components/StockAnalysis";
import TechnicalIndicators from "@/components/TechnicalIndicators";
import WatchlistButton from "@/components/WatchlistButton";
import {
  getCompanyFundamentals,
  getStockQuote,
} from "@/services/api";

type StockPageProps = {
  params: Promise<{
    displaySymbol: string;
  }>;
};

function formatNumber(value: string): string {
  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsedValue);
}

function formatCompactCurrency(value: string | null): string {
  if (value === null) {
    return "Not available";
  }

  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(parsedValue);
}

function formatOptionalNumber(
  value: string | null,
  suffix = "",
): string {
  if (value === null) {
    return "Not available";
  }

  return `${formatNumber(value)}${suffix}`;
}

function formatRatioAsPercentage(value: string | null): string {
  if (value === null) {
    return "Not available";
  }

  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return `${new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsedValue * 100)}%`;
}

function formatDirectPercentage(value: string | null): string {
  if (value === null) {
    return "Not available";
  }

  return `${formatNumber(value)}%`;
}

function formatTimestamp(value: string): string {
  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(parsedDate);
}

export default async function StockPage({
  params,
}: StockPageProps) {
  const { displaySymbol } = await params;

  const [quote, fundamentals] = await Promise.all([
    getStockQuote(displaySymbol),
    getCompanyFundamentals(displaySymbol),
  ]);

  const change = Number(quote.change);
  const isPositive = change > 0;
  const isNegative = change < 0;

  const changeClassName = isPositive
    ? "text-emerald-500"
    : isNegative
      ? "text-red-500"
      : "text-zinc-400";

  const changePrefix = isPositive ? "+" : "";

  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-8 text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <Link
          href="/dashboard"
          className="text-sm text-zinc-400 transition hover:text-white"
        >
          &larr; Back to dashboard
        </Link>

        <section className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6 shadow-xl sm:p-8">
          <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-start">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-semibold sm:text-3xl">
                  {quote.companyName}
                </h1>

                <span className="rounded-full border border-zinc-700 bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-300">
                  {quote.exchange}
                </span>
              </div>

              <p className="mt-2 text-sm text-zinc-400">
                {quote.displaySymbol}
              </p>

              <div className="mt-4 flex flex-wrap gap-2">
                {fundamentals.sector && (
                  <span className="rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-300">
                    {fundamentals.sector}
                  </span>
                )}

                {fundamentals.industry && (
                  <span className="rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-300">
                    {fundamentals.industry}
                  </span>
                )}
              </div>
            </div>

            <div className="flex flex-col gap-4 sm:items-end">
              <WatchlistButton displaySymbol={quote.displaySymbol} />

              <div className="sm:text-right">
              <p className="text-sm text-zinc-400">Current price</p>

              <p className="mt-1 text-4xl font-bold tracking-tight sm:text-5xl">
                ₹{formatNumber(quote.price)}
              </p>

              <p className={`mt-2 text-lg font-medium ${changeClassName}`}>
                {changePrefix}
                {formatNumber(quote.change)} ({changePrefix}
                {formatNumber(quote.changePercent)}%)
              </p>
              </div>
            </div>
          </div>

          <div className="mt-8 grid grid-cols-2 gap-4 border-t border-zinc-800 pt-6 sm:grid-cols-4">
            <QuoteMetric label="Open" value={quote.open} />
            <QuoteMetric label="High" value={quote.high} />
            <QuoteMetric label="Low" value={quote.low} />
            <QuoteMetric
              label="Previous close"
              value={quote.previousClose}
            />
          </div>
        </section>

        <p className="mt-4 text-right text-xs text-zinc-500">
          Quote updated: {formatTimestamp(quote.asOf)} IST
        </p>

        <StockPriceChart displaySymbol={quote.displaySymbol} />

        <StockAnalysis displaySymbol={quote.displaySymbol} />

        <TechnicalIndicators displaySymbol={quote.displaySymbol} />

        <FinancialHealth displaySymbol={quote.displaySymbol} />

        <FinancialStatements displaySymbol={quote.displaySymbol} />

        <section className="mt-8">
          <div>
            <h2 className="text-xl font-semibold">
              Company fundamentals
            </h2>

            <p className="mt-1 text-sm text-zinc-400">
              Key valuation, financial and trading metrics
            </p>
          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <FundamentalMetric
              label="Market capitalisation"
              value={formatCompactCurrency(fundamentals.marketCap)}
            />

            <FundamentalMetric
              label="Enterprise value"
              value={formatCompactCurrency(
                fundamentals.enterpriseValue,
              )}
            />

            <FundamentalMetric
              label="Trailing P/E"
              value={formatOptionalNumber(
                fundamentals.trailingPE,
              )}
            />

            <FundamentalMetric
              label="Forward P/E"
              value={formatOptionalNumber(
                fundamentals.forwardPE,
              )}
            />

            <FundamentalMetric
              label="Price to book"
              value={formatOptionalNumber(
                fundamentals.priceToBook,
              )}
            />

            <FundamentalMetric
              label="Debt to equity"
              value={formatOptionalNumber(
                fundamentals.debtToEquity,
              )}
            />

            <FundamentalMetric
              label="Profit margin"
              value={formatRatioAsPercentage(
                fundamentals.profitMargin,
              )}
            />

            <FundamentalMetric
              label="Operating margin"
              value={formatRatioAsPercentage(
                fundamentals.operatingMargin,
              )}
            />

            <FundamentalMetric
              label="Revenue growth"
              value={formatRatioAsPercentage(
                fundamentals.revenueGrowth,
              )}
            />

            <FundamentalMetric
              label="Earnings growth"
              value={formatRatioAsPercentage(
                fundamentals.earningsGrowth,
              )}
            />

            <FundamentalMetric
              label="Dividend yield"
              value={formatDirectPercentage(
                fundamentals.dividendYield,
              )}
            />

            <FundamentalMetric
              label="Book value per share"
              value={
                fundamentals.bookValuePerShare === null
                  ? "Not available"
                  : `₹${formatNumber(
                      fundamentals.bookValuePerShare,
                    )}`
              }
            />
          </div>
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
            <h2 className="text-lg font-semibold">
              Trading reference
            </h2>

            <div className="mt-5 grid grid-cols-2 gap-4">
              <FundamentalMetric
                label="52-week high"
                value={
                  fundamentals.fiftyTwoWeekHigh === null
                    ? "Not available"
                    : `₹${formatNumber(
                        fundamentals.fiftyTwoWeekHigh,
                      )}`
                }
              />

              <FundamentalMetric
                label="52-week low"
                value={
                  fundamentals.fiftyTwoWeekLow === null
                    ? "Not available"
                    : `₹${formatNumber(
                        fundamentals.fiftyTwoWeekLow,
                      )}`
                }
              />

              <FundamentalMetric
                label="50-day average"
                value={
                  fundamentals.fiftyDayAverage === null
                    ? "Not available"
                    : `₹${formatNumber(
                        fundamentals.fiftyDayAverage,
                      )}`
                }
              />

              <FundamentalMetric
                label="200-day average"
                value={
                  fundamentals.twoHundredDayAverage === null
                    ? "Not available"
                    : `₹${formatNumber(
                        fundamentals.twoHundredDayAverage,
                      )}`
                }
              />
            </div>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
            <h2 className="text-lg font-semibold">
              About the company
            </h2>

            {fundamentals.businessSummary ? (
              <div className="mt-4">
                <CompanySummary
                  summary={fundamentals.businessSummary}
                />
              </div>
            ) : (
              <p className="mt-4 text-sm text-zinc-500">
                Company summary is not available.
              </p>
            )}

            {fundamentals.website && (
              <a
                href={fundamentals.website}
                target="_blank"
                rel="noreferrer"
                className="mt-5 inline-block text-sm font-medium text-blue-400 transition hover:text-blue-300"
              >
                                Visit company website &rarr;
              </a>
            )}
          </div>
        </section>

        <p className="mt-6 text-right text-xs text-zinc-500">
          Fundamentals fetched:{" "}
          {formatTimestamp(fundamentals.fetchedAt)} IST
        </p>
      </div>
    </main>
  );
}

type QuoteMetricProps = {
  label: string;
  value: string;
};

function QuoteMetric({
  label,
  value,
}: QuoteMetricProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
      <p className="text-xs uppercase tracking-wide text-zinc-500">
        {label}
      </p>

      <p className="mt-2 text-lg font-semibold">
        ₹{formatNumber(value)}
      </p>
    </div>
  );
}

type FundamentalMetricProps = {
  label: string;
  value: string;
};

function FundamentalMetric({
  label,
  value,
}: FundamentalMetricProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
      <p className="text-xs uppercase tracking-wide text-zinc-500">
        {label}
      </p>

      <p className="mt-2 break-words text-base font-semibold text-zinc-100">
        {value}
      </p>
    </div>
  );
}







