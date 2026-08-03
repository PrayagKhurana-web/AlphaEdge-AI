import Link from "next/link";

import AlphaEdgePulse from "@/components/AlphaEdgePulse";
import DashboardAuthGate from "@/components/DashboardAuthGate";

export default function PulsePage() {
  return (
    <DashboardAuthGate>
      <main className="min-h-screen bg-black px-4 py-8 text-white sm:px-6 sm:py-10 lg:px-10">
        <div className="mx-auto max-w-6xl">
          <Link
            href="/dashboard"
            className="text-sm text-zinc-500 transition hover:text-white"
          >
            &larr; Back to dashboard
          </Link>

          <section className="mt-6 rounded-2xl border border-white/10 bg-zinc-950 p-5 sm:p-8">
            <AlphaEdgePulse />
          </section>
        </div>
      </main>
    </DashboardAuthGate>
  );
}
