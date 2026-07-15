import {
  getHealth,
  getMarketIndices,
  type MarketIndexQuote,
  type MarketIndicesResponse,
} from "@/services/api";

const AI_PICKS = [
  { symbol: "RELIANCE", score: 84, outlook: "Bullish" },
  { symbol: "HAL", score: 81, outlook: "Bullish" },
  { symbol: "HDFCBANK", score: 76, outlook: "Moderate" },
];

type DashboardMetric = {
  key: string;
  label: string;
  value: string;
  change: string;
  numericChange: number | null;
};

type MarketMood = {
  score: number;
  label: string;
  description: string;
  textClassName: string;
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

function formatChangePercent(value: string): string {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return value;
  }

  const sign = numericValue > 0 ? "+" : "";

  return `${sign}${numericValue.toFixed(2)}%`;
}

function createMetric(
  key: string,
  fallbackLabel: string,
  quote: MarketIndexQuote | undefined,
): DashboardMetric {
  if (!quote) {
    return {
      key,
      label: fallbackLabel,
      value: "Unavailable",
      change: "—",
      numericChange: null,
    };
  }

  const numericChange = Number(quote.changePercent);

  return {
    key,
    label: quote.displayName || fallbackLabel,
    value: formatPrice(quote.price),
    change: formatChangePercent(quote.changePercent),
    numericChange: Number.isFinite(numericChange) ? numericChange : null,
  };
}

function createMetrics(
  marketIndices?: MarketIndicesResponse,
): DashboardMetric[] {
  return [
    createMetric("nifty50", "NIFTY 50", marketIndices?.nifty50),
    createMetric("sensex", "SENSEX", marketIndices?.sensex),
    createMetric("bankNifty", "BANK NIFTY", marketIndices?.bankNifty),
    createMetric("indiaVix", "INDIA VIX", marketIndices?.indiaVix),
  ];
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

function calculateMarketMood(metrics: DashboardMetric[]): MarketMood {
  const nifty50 = metrics.find((metric) => metric.key === "nifty50");
  const sensex = metrics.find((metric) => metric.key === "sensex");
  const bankNifty = metrics.find((metric) => metric.key === "bankNifty");
  const indiaVix = metrics.find((metric) => metric.key === "indiaVix");

  const equityChanges = [
    nifty50?.numericChange,
    sensex?.numericChange,
    bankNifty?.numericChange,
  ].filter((value): value is number => value !== null && value !== undefined);

  if (equityChanges.length === 0) {
    return {
      score: 50,
      label: "Unavailable",
      description:
        "Not enough live index data is available to calculate market mood.",
      textClassName: "text-zinc-400",
    };
  }

  const averageEquityChange =
    equityChanges.reduce((total, change) => total + change, 0) /
    equityChanges.length;

  const vixChange = indiaVix?.numericChange ?? 0;

  /*
   * Transparent heuristic:
   * - Equity indices contribute positively when they rise.
   * - VIX contributes inversely because a falling VIX generally indicates
   *   lower short-term fear.
   * - The final score is bounded between 0 and 100.
   */
  const rawScore =
    50 +
    clamp(averageEquityChange, -3, 3) * 12 -
    clamp(vixChange, -10, 10) * 1.5;

  const score = Math.round(clamp(rawScore, 0, 100));

  if (score >= 80) {
    return {
      score,
      label: "Strongly Bullish",
      description:
        "Major indices are showing broad strength while volatility conditions are supportive.",
      textClassName: "text-emerald-400",
    };
  }

  if (score >= 65) {
    return {
      score,
      label: "Moderately Bullish",
      description:
        "Market breadth is positive, though short-term risks should still be monitored.",
      textClassName: "text-emerald-400",
    };
  }

  if (score >= 45) {
    return {
      score,
      label: "Neutral",
      description:
        "Index movement is mixed or limited, with no strong directional signal.",
      textClassName: "text-amber-300",
    };
  }

  if (score >= 25) {
    return {
      score,
      label: "Moderately Bearish",
      description:
        "Major indices are under pressure or volatility conditions are becoming less supportive.",
      textClassName: "text-red-400",
    };
  }

  return {
    score,
    label: "Strongly Bearish",
    description:
      "Broad index weakness and elevated volatility indicate a defensive market environment.",
    textClassName: "text-red-400",
  };
}

function formatLastUpdated(value: string | null): string {
  if (!value) {
    return "Live market data unavailable";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Update time unavailable";
  }

  return `Last updated ${new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(date)}`;
}

export default async function DashboardPage() {
  let backendStatus = "Offline";
  let backendVersion = "Unavailable";
  let marketDataError = false;
  let lastUpdated: string | null = null;
  let marketIndices: MarketIndicesResponse | undefined;

  const [healthResult, marketIndicesResult] = await Promise.allSettled([
    getHealth(),
    getMarketIndices(),
  ]);

  if (healthResult.status === "fulfilled") {
    backendStatus =
      healthResult.value.status === "healthy"
        ? "Connected"
        : healthResult.value.status;

    backendVersion = healthResult.value.version;
  }

  if (marketIndicesResult.status === "fulfilled") {
    marketIndices = marketIndicesResult.value;
    lastUpdated = marketIndicesResult.value.lastUpdated;
  } else {
    marketDataError = true;
  }

  const metrics = createMetrics(marketIndices);
  const marketMood = calculateMarketMood(metrics);
  const backendIsConnected = backendStatus === "Connected";

  return (
    <main className="min-h-screen bg-black px-6 py-10 text-white sm:px-10">
      <div className="mx-auto max-w-7xl">
        <div className="mb-10 flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm uppercase tracking-[0.25em] text-emerald-400">
              AlphaEdge AI
            </p>

            <div className="flex items-center gap-3 rounded-full border border-white/10 bg-zinc-950 px-4 py-2">
              <span
                className={`h-2 w-2 rounded-full ${
                  backendIsConnected
                    ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]"
                    : "bg-red-400"
                }`}
              />

              <p className="text-xs text-zinc-300">
                Backend: {backendStatus}
              </p>

              <span className="text-xs text-zinc-600">
                v{backendVersion}
              </span>
            </div>
          </div>

          <h1 className="text-3xl font-semibold sm:text-4xl">
            Market Intelligence Dashboard
          </h1>

          <p className="max-w-2xl text-sm leading-relaxed text-zinc-400 sm:text-base">
            Track market movement, AI-ranked opportunities, sentiment and
            portfolio insights from one place.
          </p>

          <p className="text-xs text-zinc-600">
            {formatLastUpdated(lastUpdated)}
          </p>
        </div>

        {marketDataError && (
          <div className="mb-6 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300">
            Live market data could not be loaded. Make sure the FastAPI backend
            is running on port 8000.
          </div>
        )}

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map((metric) => (
            <article
              key={metric.key}
              className="rounded-2xl border border-white/10 bg-zinc-950 p-5"
            >
              <p className="text-xs uppercase tracking-wider text-zinc-500">
                {metric.label}
              </p>

              <div className="mt-3 flex items-end justify-between gap-3">
                <p className="text-xl font-semibold">{metric.value}</p>

                <p
                  className={`text-sm font-medium ${
                    metric.numericChange === null
                      ? "text-zinc-600"
                      : metric.numericChange >= 0
                        ? "text-emerald-400"
                        : "text-red-400"
                  }`}
                >
                  {metric.change}
                </p>
              </div>
            </article>
          ))}
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-[2fr_1fr]">
          <article className="rounded-2xl border border-white/10 bg-zinc-950 p-6">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold">AI Top Picks</h2>
                <p className="mt-1 text-sm text-zinc-500">
                  Mock data for layout testing
                </p>
              </div>

              <a
                href="/ai-picks"
                className="text-sm font-medium text-emerald-400 hover:text-emerald-300"
              >
                View all
              </a>
            </div>

            <div className="space-y-3">
              {AI_PICKS.map((stock) => (
                <div
                  key={stock.symbol}
                  className="flex items-center justify-between rounded-xl border border-white/5 bg-black/50 px-4 py-4"
                >
                  <div>
                    <p className="font-semibold text-zinc-100">
                      {stock.symbol}
                    </p>

                    <p className="mt-1 text-xs text-zinc-500">
                      Outlook: {stock.outlook}
                    </p>
                  </div>

                  <div className="text-right">
                    <p className="text-lg font-semibold text-emerald-400">
                      {stock.score}
                    </p>

                    <p className="text-xs text-zinc-500">AI Score</p>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="rounded-2xl border border-white/10 bg-zinc-950 p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold">Market Mood</h2>
                <p className="mt-1 text-xs text-zinc-600">
                  Live index-based heuristic
                </p>
              </div>

              <span className="rounded-full border border-white/10 bg-black/40 px-3 py-1 text-xs text-zinc-500">
                Not a trade signal
              </span>
            </div>

            <div className="mt-6">
              <div className="flex items-end gap-2">
                <p
                  className={`text-5xl font-semibold ${marketMood.textClassName}`}
                >
                  {marketMood.score}
                </p>

                <p className="pb-1 text-sm text-zinc-500">/100</p>
              </div>

              <p className="mt-3 text-sm font-medium text-zinc-200">
                {marketMood.label}
              </p>

              <p className="mt-3 text-sm leading-relaxed text-zinc-500">
                {marketMood.description}
              </p>
            </div>
          </article>
        </section>
      </div>
    </main>
  );
}