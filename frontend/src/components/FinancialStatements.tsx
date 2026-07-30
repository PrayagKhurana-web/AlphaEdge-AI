"use client";

import { useEffect, useMemo, useState } from "react";

import {
  getFinancialStatements,
  type FinancialStatementPeriod,
  type FinancialStatementRecord,
  type FinancialStatementsResponse,
} from "@/services/api";

type FinancialStatementsProps = {
  displaySymbol: string;
};

type StatementSection = {
  title: string;
  rows: {
    label: string;
    key: keyof FinancialStatementRecord;
  }[];
};

const statementSections: StatementSection[] = [
  {
    title: "Income statement",
    rows: [
      { label: "Revenue", key: "totalRevenue" },
      { label: "Gross profit", key: "grossProfit" },
      { label: "Operating income", key: "operatingIncome" },
      { label: "EBITDA", key: "ebitda" },
      { label: "Net income", key: "netIncome" },
      { label: "Diluted EPS", key: "dilutedEps" },
    ],
  },
  {
    title: "Balance sheet",
    rows: [
      { label: "Total assets", key: "totalAssets" },
      { label: "Total liabilities", key: "totalLiabilities" },
      { label: "Shareholder equity", key: "shareholderEquity" },
      { label: "Cash and equivalents", key: "cashAndEquivalents" },
      { label: "Total debt", key: "totalDebt" },
    ],
  },
  {
    title: "Cash flow",
    rows: [
      { label: "Operating cash flow", key: "operatingCashFlow" },
      { label: "Capital expenditure", key: "capitalExpenditure" },
      { label: "Free cash flow", key: "freeCashFlow" },
      { label: "Investing cash flow", key: "investingCashFlow" },
      { label: "Financing cash flow", key: "financingCashFlow" },
    ],
  },
];

function formatReportingDate(
  value: string,
  period: FinancialStatementPeriod,
): string {
  const parsedDate = new Date(`${value}T00:00:00`);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-IN", {
    month: period === "quarterly" ? "short" : undefined,
    year: "numeric",
  }).format(parsedDate);
}

function formatStatementValue(
  key: keyof FinancialStatementRecord,
  value: string | null,
  currency: string | null,
): string {
  if (value === null) {
    return "—";
  }

  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  if (key === "dilutedEps") {
    return new Intl.NumberFormat("en-IN", {
      maximumFractionDigits: 2,
    }).format(parsedValue);
  }

  const formattedValue = new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(parsedValue);

  return currency === "INR" ? `₹${formattedValue}` : formattedValue;
}


function formatLatestReportingDate(
  value: string | undefined,
): string {
  if (!value) {
    return "Unavailable";
  }

  const parsedDate = new Date(`${value}T00:00:00`);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
  }).format(parsedDate);
}

function calculateGrowth(
  currentValue: string | null,
  previousValue: string | null,
): number | null {
  if (currentValue === null || previousValue === null) {
    return null;
  }

  const current = Number(currentValue);
  const previous = Number(previousValue);

  if (
    !Number.isFinite(current) ||
    !Number.isFinite(previous) ||
    previous === 0
  ) {
    return null;
  }

  return ((current - previous) / Math.abs(previous)) * 100;
}

function formatGrowth(value: number | null): string {
  if (value === null) {
    return "Not available";
  }

  const prefix = value > 0 ? "+" : "";

  return `${prefix}${new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 1,
  }).format(value)}%`;
}

export default function FinancialStatements({
  displaySymbol,
}: FinancialStatementsProps) {
  const [period, setPeriod] =
    useState<FinancialStatementPeriod>("annual");
  const [data, setData] =
    useState<FinancialStatementsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isCancelled = false;

    async function loadStatements(): Promise<void> {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const response = await getFinancialStatements(
          displaySymbol,
          period,
        );

        if (!isCancelled) {
          setData(response);
        }
      } catch {
        if (!isCancelled) {
          setData(null);
          setErrorMessage(
            "Unable to load financial statements right now.",
          );
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadStatements();

    return () => {
      isCancelled = true;
    };
  }, [displaySymbol, period]);

  const healthMetrics = useMemo(() => {
    if (!data || data.statements.length < 2) {
      return [];
    }

    const latest = data.statements[0];
    const previous = data.statements[1];

    return [
      {
        label: "Revenue growth",
        value: formatGrowth(
          calculateGrowth(
            latest.totalRevenue,
            previous.totalRevenue,
          ),
        ),
      },
      {
        label: "Net income growth",
        value: formatGrowth(
          calculateGrowth(
            latest.netIncome,
            previous.netIncome,
          ),
        ),
      },
      {
        label: "Free cash flow growth",
        value: formatGrowth(
          calculateGrowth(
            latest.freeCashFlow,
            previous.freeCashFlow,
          ),
        ),
      },
    ];
  }, [data]);

  return (
    <section className="mt-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-xl font-semibold">
            Financial statements
          </h2>

          <p className="mt-1 text-sm text-zinc-400">
            Income statement, balance sheet and cash-flow history
          </p>
        </div>

        <div className="inline-flex rounded-xl border border-zinc-800 bg-zinc-900 p-1">
          {(["annual", "quarterly"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setPeriod(option)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                period === option
                  ? "bg-white text-zinc-950"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              {option === "annual" ? "Annual" : "Quarterly"}
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="mt-5 rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
          <p className="text-sm text-zinc-500">
            Loading financial statements...
          </p>
        </div>
      )}

      {!isLoading && (errorMessage || !data) && (
        <div className="mt-5 rounded-2xl border border-red-900/50 bg-red-950/20 p-6">
          <p className="text-sm text-red-300">
            {errorMessage || "Financial statements are unavailable."}
          </p>
        </div>
      )}

      {!isLoading && data && (
        <>
          <div
            className={`mt-5 rounded-xl border px-4 py-4 ${
              data.isPotentiallyStale
                ? "border-amber-500/20 bg-amber-500/5"
                : "border-emerald-500/20 bg-emerald-500/5"
            }`}
          >
            <p
              className={`text-sm font-medium ${
                data.isPotentiallyStale
                  ? "text-amber-200"
                  : "text-emerald-200"
              }`}
            >
              {data.isPotentiallyStale
                ? "Provider data may be behind"
                : "Provider data appears current"}
            </p>

            <div className="mt-2 grid gap-1 text-xs leading-5 text-zinc-400 sm:grid-cols-2">
              <p>
                Latest available:{" "}
                <span className="text-zinc-200">
                  {formatLatestReportingDate(
                    data.latestReportingDate,
                  )}
                </span>
              </p>

              <p>
                Expected period:{" "}
                <span className="text-zinc-200">
                  {formatLatestReportingDate(
                    data.expectedLatestReportingDate,
                  )}
                </span>
              </p>

              <p>
                Provider data age:{" "}
                <span className="text-zinc-200">
                  {data.dataAgeDays} days
                </span>
              </p>

              <p>
                Status:{" "}
                <span className="text-zinc-200">
                  {data.freshnessStatus ===
                  "potentially_stale"
                    ? "Potentially stale"
                    : "Current"}
                </span>
              </p>
            </div>

            <p
              className={`mt-3 text-xs leading-5 ${
                data.isPotentiallyStale
                  ? "text-amber-200/70"
                  : "text-emerald-200/70"
              }`}
            >
              {data.isPotentiallyStale
                ? "The provider has not yet returned the latest calendar period expected by AlphaEdge. Check the company or NSE/BSE filing before relying on these figures."
                : "The latest provider period matches AlphaEdge's calendar-based freshness expectation."}
            </p>

            <p className="mt-2 text-xs leading-5 text-zinc-600">
              Freshness is a calendar heuristic, not confirmation
              of a company-specific exchange filing.
            </p>
          </div>

          {healthMetrics.length > 0 && (
            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              {healthMetrics.map((metric) => (
                <div
                  key={metric.label}
                  className="rounded-xl border border-zinc-800 bg-zinc-950/50 p-4"
                >
                  <p className="text-xs uppercase tracking-wide text-zinc-500">
                    {metric.label}
                  </p>

                  <p className="mt-2 text-lg font-semibold text-zinc-100">
                    {metric.value}
                  </p>
                </div>
              ))}
            </div>
          )}

          <div className="mt-5 space-y-5">
            {statementSections.map((section) => (
              <div
                key={section.title}
                className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/70"
              >
                <div className="border-b border-zinc-800 px-5 py-4">
                  <h3 className="font-semibold">
                    {section.title}
                  </h3>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left">
                    <thead>
                      <tr className="border-b border-zinc-800 text-xs uppercase tracking-wide text-zinc-500">
                        <th className="px-5 py-3 font-medium">
                          Metric
                        </th>

                        {data.statements.map((statement) => (
                          <th
                            key={statement.reportingDate}
                            className="px-5 py-3 text-right font-medium"
                          >
                            {formatReportingDate(
                              statement.reportingDate,
                              data.period,
                            )}
                          </th>
                        ))}
                      </tr>
                    </thead>

                    <tbody>
                      {section.rows.map((row) => (
                        <tr
                          key={row.key}
                          className="border-b border-zinc-800/70 last:border-b-0"
                        >
                          <td className="px-5 py-3 text-sm text-zinc-400">
                            {row.label}
                          </td>

                          {data.statements.map((statement) => (
                            <td
                              key={`${row.key}-${statement.reportingDate}`}
                              className="px-5 py-3 text-right text-sm font-medium text-zinc-100"
                            >
                              {formatStatementValue(
                                row.key,
                                statement[row.key] as string | null,
                                data.currency,
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>

          <p className="mt-4 text-xs leading-5 text-zinc-500">
            Values are shown as reported by the provider. Missing data
            is displayed as an em dash and is never replaced with zero.
          </p>
        </>
      )}
    </section>
  );
}
