import Link from "next/link";

export default function OfflinePage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-black px-6 text-white">
      <section className="w-full max-w-md rounded-2xl border border-white/10 bg-zinc-950 p-7 text-center">
        <div className="mx-auto h-3 w-3 rounded-full bg-amber-400 shadow-[0_0_14px_rgba(251,191,36,0.7)]" />

        <h1 className="mt-5 text-2xl font-semibold">
          You are offline
        </h1>

        <p className="mt-3 text-sm leading-6 text-zinc-400">
          AlphaEdge needs an internet connection for live stock
          data, predictions and account information.
        </p>

        <Link
          href="/dashboard"
          className="mt-6 inline-block rounded-xl bg-emerald-500 px-5 py-3 text-sm font-semibold text-black transition hover:bg-emerald-400"
        >
          Try again
        </Link>
      </section>
    </main>
  );
}
