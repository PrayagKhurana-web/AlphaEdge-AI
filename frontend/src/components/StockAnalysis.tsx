import {
  getStockAnalysis,
  type StockAnalysisReasonType,
  type StockOutlook,
  type StockRiskLevel,
} from "@/services/api";

type StockAnalysisProps = {
  displaySymbol: string;
};

function formatCurrency(value: string | null): string {
  if (value === null) {
    return "Not available";
  }

  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsedValue);
}

function formatTimestamp(value: string): string {
  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(parsedDate);
}

function formatLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    );
}

function getOutlookClasses(
  outlook: StockOutlook,
): string {
  if (outlook === "bullish") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  }

  if (outlook === "bearish") {
    return "border-red-500/30 bg-red-500/10 text-red-300";
  }

  return "border-amber-500/30 bg-amber-500/10 text-amber-300";
}

function getRiskClasses(
  riskLevel: StockRiskLevel,
): string {
  if (riskLevel === "low") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  }

  if (riskLevel === "high") {
    return "border-red-500/30 bg-red-500/10 text-red-300";
  }

  return "border-amber-500/30 bg-amber-500/10 text-amber-300";
}

function getReasonClasses(
  reasonType: StockAnalysisReasonType,
): string {
  if (reasonType === "positive") {
    return "border-emerald-500/20 bg-emerald-500/5";
  }

  if (reasonType === "negative") {
    return "border-red-500/20 bg-red-500/5";
  }

  return "border-zinc-700 bg-zinc-950/50";
}

function getReasonMarkerClasses(
  reasonType: StockAnalysisReasonType,
): string {
  if (reasonType === "positive") {
    return "bg-emerald-400";
  }

  if (reasonType === "negative") {
    return "bg-red-400";
  }

  return "bg-zinc-500";
}

export default async function StockAnalysis({
  displaySymbol,
}: StockAnalysisProps) {
  try {
    const analysis = await getStockAnalysis(
      displaySymbol,
    );

    return (
      <section className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6 shadow-xl sm:p-8">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-400">
              AlphaEdge outlook
            </p>

            <h2 className="mt-2 text-2xl font-semibold">
              Explainable stock analysis
            </h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">
              Deterministic short-term interpretation combining
              technical conditions, financial health and market
              activity.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <span
              className={`rounded-full border px-4 py-2 text-sm font-semibold ${getOutlookClasses(
                analysis.outlook,
              )}`}
            >
              {formatLabel(analysis.outlook)}
            </span>

            <span
              className={`rounded-full border px-4 py-2 text-sm font-semibold ${getRiskClasses(
                analysis.riskLevel,
              )}`}
            >
              {formatLabel(analysis.riskLevel)} risk
            </span>
          </div>
        </div>

        <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <AnalysisMetric
            label="Overall score"
            value={`${analysis.overallScore}/100`}
          />

          <AnalysisMetric
            label="Confidence"
            value={`${analysis.confidenceScore}%`}
          />

          <AnalysisMetric
            label="Nearest support"
            value={formatCurrency(
              analysis.nearestSupport,
            )}
          />

          <AnalysisMetric
            label="Nearest resistance"
            value={formatCurrency(
              analysis.nearestResistance,
            )}
          />
        </div>

        <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-950/60 p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-emerald-400">
                Bullish {analysis.bullishProbability}%
              </p>
            </div>

            <p className="text-sm font-medium text-red-400">
              Bearish {analysis.bearishProbability}%
            </p>
          </div>

          <div className="mt-3 flex h-3 overflow-hidden rounded-full bg-zinc-800">
            <div
              className="bg-emerald-500"
              style={{
                width: `${analysis.bullishProbability}%`,
              }}
            />

            <div
              className="bg-red-500"
              style={{
                width: `${analysis.bearishProbability}%`,
              }}
            />
          </div>

          <p className="mt-3 text-xs leading-5 text-zinc-500">
            These percentages are score-derived interpretations,
            not statistical forecasts or guaranteed probabilities.
          </p>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <ScoreCard
            label="Technical"
            score={analysis.technicalScore}
          />

          <ScoreCard
            label="Financial health"
            score={analysis.financialScore}
          />

          <ScoreCard
            label="Market activity"
            score={analysis.marketActivityScore}
          />
        </div>

        <div className="mt-7">
          <h3 className="text-lg font-semibold">
            Why this outlook?
          </h3>

          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {analysis.reasons.map((reason, index) => (
              <div
                key={`${reason.category}-${index}`}
                className={`rounded-xl border p-4 ${getReasonClasses(
                  reason.reasonType,
                )}`}
              >
                <div className="flex items-start gap-3">
                  <span
                    className={`mt-2 h-2 w-2 shrink-0 rounded-full ${getReasonMarkerClasses(
                      reason.reasonType,
                    )}`}
                  />

                  <div>
                    <p className="text-sm font-semibold text-zinc-200">
                      {reason.category}
                    </p>

                    <p className="mt-1 text-sm leading-6 text-zinc-400">
                      {reason.message}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-7 border-t border-zinc-800 pt-5">
          <p className="text-xs leading-5 text-zinc-500">
            Time horizon:{" "}
            <span className="text-zinc-400">
              {formatLabel(analysis.timeHorizon)}
            </span>
            {" | "}
            Calculated:{" "}
            <span className="text-zinc-400">
              {formatTimestamp(analysis.calculatedAt)} IST
            </span>
          </p>

          <p className="mt-2 text-xs leading-5 text-zinc-500">
            This analysis is rule-based and provided for
            informational purposes only. It is not investment
            advice, a recommendation, or a guarantee of future
            performance.
          </p>
        </div>
      </section>
    );
  } catch {
    return (
      <section className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
        <h2 className="text-xl font-semibold">
          AlphaEdge outlook
        </h2>

        <p className="mt-2 text-sm text-zinc-400">
          The combined stock analysis is temporarily unavailable.
          Technical and financial sections below may still be
          available.
        </p>
      </section>
    );
  }
}

type AnalysisMetricProps = {
  label: string;
  value: string;
};

function AnalysisMetric({
  label,
  value,
}: AnalysisMetricProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
      <p className="text-xs uppercase tracking-wide text-zinc-500">
        {label}
      </p>

      <p className="mt-2 text-lg font-semibold text-zinc-100">
        {value}
      </p>
    </div>
  );
}

type ScoreCardProps = {
  label: string;
  score: number;
};

function ScoreCard({
  label,
  score,
}: ScoreCardProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-zinc-300">
          {label}
        </p>

        <p className="text-sm font-semibold text-white">
          {score}/100
        </p>
      </div>

      <div className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-800">
        <div
          className="h-full bg-blue-500"
          style={{
            width: `${Math.max(0, Math.min(100, score))}%`,
          }}
        />
      </div>
    </div>
  );
}


