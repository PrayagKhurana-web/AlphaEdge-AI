import { getHealth } from "@/services/api";

const METRICS = [
  { label: "NIFTY 50", value: "24,572.30", change: "+0.82%" },
  { label: "SENSEX", value: "80,645.12", change: "+0.64%" },
  { label: "BANK NIFTY", value: "52,318.75", change: "-0.21%" },
  { label: "INDIA VIX", value: "13.42", change: "-1.08%" },
];

const AI_PICKS = [
  { symbol: "RELIANCE", score: 84, outlook: "Bullish" },
  { symbol: "HAL", score: 81, outlook: "Bullish" },
  { symbol: "HDFCBANK", score: 76, outlook: "Moderate" },
];

export default async function DashboardPage() {
  let backendStatus = "Offline";
  let backendVersion = "Unavailable";

  try {
    const health = await getHealth();
    backendStatus =
      health.status === "healthy" ? "Connected" : health.status;
    backendVersion = health.version;
  } catch {
    backendStatus = "Offline";
  }

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
        </div>

        <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {METRICS.map((metric) => {
            const isPositive = metric.change.startsWith("+");

            return (
              <article
                key={metric.label}
                className="rounded-2xl border border-white/10 bg-zinc-950 p-5"
              >
                <p className="text-xs uppercase tracking-wider text-zinc-500">
                  {metric.label}
                </p>

                <div className="mt-3 flex items-end justify-between gap-3">
                  <p className="text-xl font-semibold">{metric.value}</p>

                  <p
                    className={`text-sm font-medium ${
                      isPositive ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {metric.change}
                  </p>
                </div>
              </article>
            );
          })}
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
            <h2 className="text-xl font-semibold">Market Mood</h2>

            <div className="mt-6">
              <div className="flex items-end gap-2">
                <p className="text-5xl font-semibold text-emerald-400">72</p>
                <p className="pb-1 text-sm text-zinc-500">/100</p>
              </div>

              <p className="mt-3 text-sm font-medium text-zinc-200">
                Moderately Bullish
              </p>

              <p className="mt-3 text-sm leading-relaxed text-zinc-500">
                Momentum is positive, but volatility and global cues should
                still be monitored.
              </p>
            </div>
          </article>
        </section>
      </div>
    </main>
  );
}