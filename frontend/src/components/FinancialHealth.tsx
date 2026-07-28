"use client";

import { useEffect, useMemo, useState } from "react";

import {
  getFinancialHealth,
  type FinancialHealthObservation,
  type FinancialHealthObservationType,
  type FinancialHealthRating,
  type FinancialHealthResponse,
} from "@/services/api";

type FinancialHealthProps = {
  displaySymbol: string;
};

type ScoreCard = {
  label: string;
  score: number;
};

function formatRating(rating: FinancialHealthRating): string {
  const labels: Record<FinancialHealthRating, string> = {
    strong: "Strong",
    healthy: "Healthy",
    mixed: "Mixed",
    weak: "Weak",
    high_risk: "High risk",
  };

  return labels[rating];
}

function ratingClassName(rating: FinancialHealthRating): string {
  if (rating === "strong" || rating === "healthy") {
    return "border-emerald-900/60 bg-emerald-950/20 text-emerald-300";
  }

  if (rating === "weak" || rating === "high_risk") {
    return "border-red-900/60 bg-red-950/20 text-red-300";
  }

  return "border-amber-900/60 bg-amber-950/20 text-amber-300";
}

function observationClassName(
  type: FinancialHealthObservationType,
): string {
  if (type === "positive") {
    return "border-emerald-900/50 bg-emerald-950/20 text-emerald-300";
  }

  if (type === "negative") {
    return "border-red-900/50 bg-red-950/20 text-red-300";
  }

  return "border-zinc-800 bg-zinc-900/70 text-zinc-300";
}

function observationLabel(
  type: FinancialHealthObservationType,
): string {
  if (type === "positive") {
    return "Strength";
  }

  if (type === "negative") {
    return "Risk";
  }

  return "Observation";
}

function ScoreBar({
  label,
  score,
}: ScoreCard) {
  return (
    <article className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-zinc-400">
          {label}
        </p>

        <p className="text-lg font-semibold text-zinc-100">
          {score}
        </p>
      </div>

      <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-zinc-800">
        <div
          className="h-full rounded-full bg-white transition-all"
          style={{ width: `${score}%` }}
        />
      </div>

      <p className="mt-2 text-right text-xs text-zinc-500">
        out of 100
      </p>
    </article>
  );
}

function ObservationCard({
  observation,
}: {
  observation: FinancialHealthObservation;
}) {
  return (
    <article
      className={`rounded-xl border p-4 ${observationClassName(
        observation.observationType,
      )}`}
    >
      <p className="text-xs font-medium uppercase tracking-wide opacity-70">
        {observationLabel(observation.observationType)}
      </p>

      <p className="mt-2 text-sm leading-6">
        {observation.message}
      </p>
    </article>
  );
}

export default function FinancialHealth({
  displaySymbol,
}: FinancialHealthProps) {
  const [data, setData] =
    useState<FinancialHealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isCancelled = false;

    async function loadFinancialHealth(): Promise<void> {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const response = await getFinancialHealth(
          displaySymbol,
          "annual",
        );

        if (!isCancelled) {
          setData(response);
        }
      } catch {
        if (!isCancelled) {
          setData(null);
          setErrorMessage(
            "Unable to load financial-health analysis right now.",
          );
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadFinancialHealth();

    return () => {
      isCancelled = true;
    };
  }, [displaySymbol]);

  const scoreCards = useMemo<ScoreCard[]>(
    () =>
      data
        ? [
            {
              label: "Growth",
              score: data.growthScore,
            },
            {
              label: "Profitability",
              score: data.profitabilityScore,
            },
            {
              label: "Balance sheet",
              score: data.balanceSheetScore,
            },
            {
              label: "Cash-flow quality",
              score: data.cashFlowScore,
            },
          ]
        : [],
    [data],
  );

  const groupedObservations = useMemo(() => {
    if (!data) {
      return {
        positive: [],
        neutral: [],
        negative: [],
      };
    }

    return {
      positive: data.observations.filter(
        (item) => item.observationType === "positive",
      ),
      neutral: data.observations.filter(
        (item) => item.observationType === "neutral",
      ),
      negative: data.observations.filter(
        (item) => item.observationType === "negative",
      ),
    };
  }, [data]);

  if (isLoading) {
    return (
      <section className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
        <p className="text-sm text-zinc-500">
          Loading financial-health analysis...
        </p>
      </section>
    );
  }

  if (errorMessage || !data) {
    return (
      <section className="mt-8 rounded-2xl border border-red-900/50 bg-red-950/20 p-6">
        <p className="text-sm text-red-300">
          {errorMessage ||
            "Financial-health analysis is unavailable."}
        </p>
      </section>
    );
  }

  return (
    <section className="mt-8">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-xl font-semibold">
            Financial health
          </h2>

          <p className="mt-1 text-sm text-zinc-400">
            Rule-based assessment using annual company statements
          </p>
        </div>

        <div
          className={`rounded-2xl border px-5 py-4 ${ratingClassName(
            data.rating,
          )}`}
        >
          <p className="text-xs uppercase tracking-wide opacity-70">
            Overall score
          </p>

          <div className="mt-1 flex items-baseline gap-2">
            <p className="text-3xl font-bold">
              {data.overallScore}
            </p>

            <p className="text-sm opacity-70">
              / 100
            </p>
          </div>

          <p className="mt-1 font-medium">
            {formatRating(data.rating)}
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {scoreCards.map((card) => (
          <ScoreBar
            key={card.label}
            label={card.label}
            score={card.score}
          />
        ))}
      </div>

      {groupedObservations.positive.length > 0 && (
        <div className="mt-6">
          <h3 className="text-base font-semibold">
            Strengths
          </h3>

          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {groupedObservations.positive.map(
              (observation, index) => (
                <ObservationCard
                  key={`positive-${index}`}
                  observation={observation}
                />
              ),
            )}
          </div>
        </div>
      )}

      {groupedObservations.negative.length > 0 && (
        <div className="mt-6">
          <h3 className="text-base font-semibold">
            Risks
          </h3>

          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {groupedObservations.negative.map(
              (observation, index) => (
                <ObservationCard
                  key={`negative-${index}`}
                  observation={observation}
                />
              ),
            )}
          </div>
        </div>
      )}

      {groupedObservations.neutral.length > 0 && (
        <div className="mt-6">
          <h3 className="text-base font-semibold">
            Other observations
          </h3>

          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {groupedObservations.neutral.map(
              (observation, index) => (
                <ObservationCard
                  key={`neutral-${index}`}
                  observation={observation}
                />
              ),
            )}
          </div>
        </div>
      )}

      <p className="mt-4 text-xs leading-5 text-zinc-500">
        This score is produced by deterministic rules using reported
        financial statements. It is not a prediction, recommendation,
        or financial advice.
      </p>
    </section>
  );
}
