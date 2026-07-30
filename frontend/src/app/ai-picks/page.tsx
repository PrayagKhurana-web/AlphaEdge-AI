import Link from "next/link";

import AITopPicks from "@/components/AITopPicks";
import DashboardAuthGate from "@/components/DashboardAuthGate";

export default function AIPicksPage() {
  return (
    <DashboardAuthGate>
      <main className="min-h-screen bg-black px-6 py-10 text-white sm:px-10">
        <div className="mx-auto max-w-6xl">
          <Link
            href="/dashboard"
            className="text-sm text-zinc-500 transition hover:text-white"
          >
            &larr; Back to dashboard
          </Link>

          <section className="mt-6 rounded-2xl border border-white/10 bg-zinc-950 p-6 sm:p-8">
            <AITopPicks />
          </section>
        </div>
      </main>
    </DashboardAuthGate>
  );
}
