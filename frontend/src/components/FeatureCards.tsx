const FEATURES = [
  {
    icon: "📈",
    title: "Technical Analysis",
    description:
      "AI detects breakouts, support, resistance, RSI, MACD, Supertrend and trend changes.",
  },
  {
    icon: "📊",
    title: "Fundamental Analysis",
    description:
      "Analyze ROE, ROCE, debt, cash flow, quarterly results and valuation.",
  },
  {
    icon: "📰",
    title: "AI News Intelligence",
    description:
      "Summarize market news and identify affected stocks and sectors.",
  },
  {
    icon: "🌍",
    title: "Geopolitical Intelligence",
    description:
      "Track policy, conflicts, oil prices, RBI, Fed and global market events.",
  },
  {
    icon: "🤖",
    title: "AI Recommendations",
    description:
      "Generate probability-based Buy, Hold or Sell ideas with clear reasoning.",
  },
  {
    icon: "💼",
    title: "Portfolio Intelligence",
    description:
      "Connect Zerodha Kite and analyze risk, diversification and opportunities.",
  },
];

export function FeatureCards() {
  return (
    <section className="relative z-10 w-full bg-black px-6 py-16 sm:px-10">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-0 h-80 w-[500px] -translate-x-1/2 rounded-full bg-emerald-500/5 blur-[120px]"
      />

      <div className="relative mx-auto max-w-7xl">
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Why AlphaEdge AI?
          </h2>

          <p className="mt-4 text-base text-zinc-400 sm:text-lg">
            Everything an investor needs in one intelligent platform.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {FEATURES.map((feature) => (
            <article
              key={feature.title}
              className="group relative overflow-hidden rounded-2xl border border-white/10 bg-zinc-950/60 p-8 transition-all duration-300 hover:-translate-y-1 hover:border-emerald-400/30 hover:bg-zinc-900"
            >
              <div className="relative z-10">
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-2xl">
                  {feature.icon}
                </div>

                <h3 className="mb-3 text-lg font-semibold text-white">
                  {feature.title}
                </h3>

                <p className="text-sm leading-7 text-zinc-400">
                  {feature.description}
                </p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}