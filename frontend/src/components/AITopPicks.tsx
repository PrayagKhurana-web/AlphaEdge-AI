import Link from "next/link";

import {
  getTopPicks,
  type StockAnalysisResponse,
  type TopPicksResponse,
} from "@/services/api";

type AITopPicksProps = {
  limit?: number;
  showHeader?: boolean;
};

function formatLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    );
}

function scoreClassName(score: number): string {
  if (score >= 65) {
    return "text-emerald-400";
  }

  if (score <= 40) {
    return "text-red-400";
  }

  return "text-amber-300";
}

function outlookClassName(outlook: string): string {
  if (outlook === "bullish") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  }

  if (outlook === "bearish") {
    return "border-red-500/30 bg-red-500/10 text-red-300";
  }

  return "border-amber-500/30 bg-amber-500/10 text-amber-300";
}

function formatCalculatedAt(value: string): string {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(parsed);
}

async function loadTopPicks(): Promise<TopPicksResponse | null> {
  try {
    return await getTopPicks();
  } catch {
    return null;
  }
}

export default async function AITopPicks({
  limit,
  showHeader = true,
}: AITopPicksProps) {
  const response = await loadTopPicks();

  const allPicks = response?.picks ?? [];
  const picks =
    limit === undefined
      ? allPicks
      : allPicks.slice(0, limit);

  return (
    <div>
      {showHeader && (
        <div className="mb-6">
          <h1 className="text-3xl font-semibold sm:text-4xl">
            AlphaEdge Top Picks
          </h1>

          <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-400">
            Stocks ranked using deterministic technical,
            financial-health and market-activity analysis.
          </p>
        </div>
      )}

      {!response ? (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-6">
          <p className="text-sm text-red-200">
            AlphaEdge Top Picks are temporarily unavailable.
          </p>
        </div>
      ) : (
        <>
          <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetadataCard
              label="Universe"
              value={String(response.universeSize)}
            />

            <MetadataCard
              label="Analysed"
              value={String(response.successfulCount)}
            />

            <MetadataCard
              label="Ranked picks"
              value={String(response.returnedPickCount)}
            />

            <MetadataCard
              label="Calculated"
              value={formatCalculatedAt(
                response.generatedAt,
              )}
            />
          </div>

          {picks.length === 0 ? (
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-6">
              <p className="text-sm text-amber-200">
                No non-bearish ranked opportunities are currently
                available from the configured stock universe.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {picks.map((pick, index) => (
                <PickCard
                  key={pick.displaySymbol}
                  pick={pick}
                  rank={index + 1}
                />
              ))}
            </div>
          )}

          {response.failedSymbols.length > 0 && (
            <div className="mt-5 rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3">
              <p className="text-xs leading-5 text-amber-200/80">
                Unavailable during this calculation:{" "}
                {response.failedSymbols.join(", ")}
              </p>
            </div>
          )}

          <p className="mt-5 text-xs leading-5 text-zinc-600">
            Methodology: {response.weights.technical}% technical,{" "}
            {response.weights.financial}% financial health and{" "}
            {response.weights.marketActivity}% market activity.
            Rankings cover a limited configured universe and are
            rule-based. They are not investment advice, guaranteed
            predictions, or SEBI-registered recommendations.
          </p>
        </>
      )}
    </div>
  );
}

function PickCard({
  pick,
  rank,
}: {
  pick: StockAnalysisResponse;
  rank: number;
}) {
  return (
    <Link
      href={`/stocks/${encodeURIComponent(
        pick.displaySymbol,
      )}`}
      className="block rounded-2xl border border-white/10 bg-black/50 p-5 transition hover:border-emerald-500/30 hover:bg-zinc-900"
    >
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
        <div className="flex items-start gap-4">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/10 bg-zinc-950 text-sm font-semibold text-zinc-400">
            {rank}
          </span>

          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-lg font-semibold text-white">
                {pick.displaySymbol}
              </h2>

              <span
                className={`rounded-full border px-3 py-1 text-xs font-medium ${outlookClassName(
                  pick.outlook,
                )}`}
              >
                {formatLabel(pick.outlook)}
              </span>

              <span className="rounded-full border border-white/10 bg-zinc-950 px-3 py-1 text-xs text-zinc-400">
                {formatLabel(pick.riskLevel)} risk
              </span>
            </div>

            <p className="mt-2 text-sm text-zinc-500">
              Bullish probability: {pick.bullishProbability}% |
              Confidence: {pick.confidenceScore}%
            </p>

            {pick.reasons[0] && (
              <p className="mt-2 text-sm leading-6 text-zinc-400">
                {pick.reasons[0].message}
              </p>
            )}
          </div>
        </div>

        <div className="shrink-0 sm:text-right">
          <p
            className={`text-3xl font-semibold ${scoreClassName(
              pick.overallScore,
            )}`}
          >
            {pick.overallScore}
          </p>

          <p className="text-xs uppercase tracking-wide text-zinc-600">
            AlphaEdge score
          </p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3 border-t border-white/5 pt-4">
        <ScoreMetric
          label="Technical"
          value={pick.technicalScore}
        />

        <ScoreMetric
          label="Financial"
          value={pick.financialScore}
        />

        <ScoreMetric
          label="Activity"
          value={pick.marketActivityScore}
        />
      </div>
    </Link>
  );
}

function MetadataCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/40 px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-zinc-600">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold text-zinc-200">
        {value}
      </p>
    </div>
  );
}

function ScoreMetric({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div>
      <p className="text-xs text-zinc-600">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold text-zinc-300">
        {value}/100
      </p>
    </div>
  );
}
