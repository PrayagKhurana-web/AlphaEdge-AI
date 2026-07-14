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
      "Analyze ROE, ROCE, Debt, Cash Flow, Quarterly Results and Valuation.",
  },
  {
    icon: "📰",
    title: "AI News Intelligence",
    description:
      "Summarize news and identify stocks affected automatically.",
  },
  {
    icon: "🌍",
    title: "Geopolitical Intelligence",
    description:
      "Track wars, government policies, oil prices, RBI, Fed, elections and their stock market impact.",
  },
  {
    icon: "🤖",
    title: "AI Recommendations",
    description:
      "Provide probability-based Buy/Hold/Sell ideas with explanations.",
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
    <section className="relative w-full bg-black px-6 py-24 sm:px-10">
      {/* Ambient background glow */}
      <div className="pointer-events-none absolute left-1/2 top-0 h-[400px] w-[600px] -translate-x-1/2 rounded-full bg-emerald-500/5 blur-[140px]" />

      <div className="relative z-10 mx-auto max-w-6xl">
        {/* Section heading */}
        <div className="mx-auto mb-16 max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Why AlphaEdge AI?
          </h2>
          <p className="mt-4 text-base text-zinc-400 sm:text-lg">
            Everything an investor needs in one platform.
          </p>
        </div>

        {/* Feature grid */}
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="group relative overflow-hidden rounded-2xl border border-white/10 bg-zinc-950/60 p-8 transition-all duration-300 hover:-translate-y-1 hover:border-emerald-400/30 hover:bg-zinc-900/60 hover:shadow-[0_0_40px_-15px_rgba(52,211,153,0.4)]"
            >
              {/* Subtle hover glow */}
              <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-emerald-500/0 blur-2xl transition-all duration-300 group-hover:bg-emerald-500/10" />

              <div className="relative z-10">
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-2xl transition-transform duration-300 group-hover:scale-110">
                  {feature.icon}
                </div>
                <h3 className="mb-2 text-lg font-semibold text-white">
                  {feature.title}
                </h3>
                <p className="text-sm leading-relaxed text-zinc-400">
                  {feature.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}