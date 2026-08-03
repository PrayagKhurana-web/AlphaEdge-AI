export function Hero() {
  return (
    <section className="relative z-10 px-6 py-24 text-center sm:px-10 sm:py-28">
      <div className="mx-auto flex max-w-5xl flex-col items-center">
        <div className="mb-6 flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_12px_2px_rgba(52,211,153,0.7)]" />

          <span className="text-sm font-medium uppercase tracking-[0.3em] text-zinc-400">
            Alpha<span className="text-emerald-400">Edge</span> AI
          </span>
        </div>

        <h1 className="bg-gradient-to-b from-white via-white to-zinc-400 bg-clip-text text-4xl font-semibold tracking-tight text-transparent sm:text-6xl md:text-7xl">
          AlphaEdge AI
        </h1>

        <p className="mt-6 max-w-2xl text-lg font-medium text-zinc-300 sm:text-xl">
          AI-Powered Stock Intelligence Platform for Indian Markets
        </p>

        <p className="mt-6 max-w-3xl text-sm leading-relaxed text-zinc-400 sm:text-base">
          AlphaEdge AI combines{" "}
          <span className="text-zinc-200">fundamental analysis</span>,{" "}
          <span className="text-zinc-200">technical analysis</span>,{" "}
          <span className="text-zinc-200">artificial intelligence</span>,{" "}
          <span className="text-zinc-200">
            geopolitical intelligence
          </span>
          , <span className="text-zinc-200">news analysis</span>, and{" "}
          <span className="text-zinc-200">machine learning</span> in one
          research platform.
        </p>

        <div className="mt-10 flex w-full flex-col items-center justify-center gap-4 sm:w-auto sm:flex-row">
          <a
            href="/dashboard"
            className="w-full rounded-xl bg-emerald-500 px-8 py-3 text-sm font-semibold text-black shadow-[0_0_30px_-5px_rgba(52,211,153,0.6)] transition-colors hover:bg-emerald-400 sm:w-auto"
          >
            Launch Dashboard
          </a>

          <a
            href="https://github.com/PrayagKhurana-web/AlphaEdge-AI"
            target="_blank"
            rel="noopener noreferrer"
            className="w-full rounded-xl border border-zinc-700 bg-zinc-900/70 px-8 py-3 text-sm font-semibold text-zinc-200 transition-colors hover:border-zinc-500 hover:bg-zinc-800 sm:w-auto"
          >
            View GitHub
          </a>
        </div>

        <p className="mt-14 text-xs uppercase tracking-[0.22em] text-zinc-600">
          Research &middot; Signals &middot; Probability &mdash; Not Guaranteed
          Advice
        </p>
      </div>
    </section>
  );
}