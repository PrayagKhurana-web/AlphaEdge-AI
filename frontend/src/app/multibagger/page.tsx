import Link from "next/link";

import DashboardAuthGate from "@/components/DashboardAuthGate";
import MultibaggerDashboard from "@/components/MultibaggerDashboard";

export default function MultibaggerPage() {
  return (
    <DashboardAuthGate>
      <main className="min-h-screen bg-black px-4 py-8 text-white sm:px-6 sm:py-10 lg:px-10">
        <div className="mx-auto max-w-7xl">
          <Link
            href="/dashboard"
            className="text-sm text-zinc-500 transition hover:text-white"
          >
            &larr; Back to dashboard
          </Link>

          <section className="mt-6 rounded-2xl border border-white/10 bg-zinc-950 p-5 sm:p-8">
            <MultibaggerDashboard />
          </section>
        </div>
      </main>
    </DashboardAuthGate>
  );
}
