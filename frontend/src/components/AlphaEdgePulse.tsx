"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";

import {
  getStockDirectionPrediction,
  PredictionApiError,
  type PredictionDirection,
  type PredictionHorizon,
  type StockDirectionPrediction,
} from "@/services/api";

const HORIZONS: Array<{
  value: PredictionHorizon;
  label: string;
  description: string;
}> = [
  {
    value: 1,
    label: "Next session",
    description: "Very short-term",
  },
  {
    value: 5,
    label: "5 sessions",
    description: "Short-term",
  },
  {
    value: 20,
    label: "20 sessions",
    description: "Swing horizon",
  },
];

function formatPercentage(value: string): string {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return value;
  }

  return `${(parsed * 100).toFixed(1)}%`;
}

function formatPrice(value: string): string {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return value;
  }

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(parsed);
}

function formatTimestamp(value: string): string {
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

function directionClassName(
  direction: PredictionDirection,
): string {
  if (direction === "bullish") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  }

  if (direction === "bearish") {
    return "border-red-500/30 bg-red-500/10 text-red-300";
  }

  return "border-amber-500/30 bg-amber-500/10 text-amber-300";
}

function directionLabel(
  direction: PredictionDirection,
): string {
  return (
    direction.charAt(0).toUpperCase() +
    direction.slice(1)
  );
}

export default function AlphaEdgePulse() {
  const [symbol, setSymbol] = useState("RELIANCE.NSE");
  const [horizon, setHorizon] =
    useState<PredictionHorizon>(5);

  const [prediction, setPrediction] =
    useState<StockDirectionPrediction | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] =
    useState<string | null>(null);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    const normalizedSymbol =
      symbol.trim().toUpperCase();

    if (
      !/^[A-Z0-9&_-]+\.(NSE|BSE)$/.test(
        normalizedSymbol,
      )
    ) {
      setErrorMessage(
        "Use SYMBOL.NSE or SYMBOL.BSE format, for example RELIANCE.NSE.",
      );
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const result =
        await getStockDirectionPrediction(
          normalizedSymbol,
          horizon,
        );

      setPrediction(result);
      setSymbol(normalizedSymbol);
    } catch (error) {
      setPrediction(null);

      setErrorMessage(
        error instanceof PredictionApiError ||
        error instanceof Error
          ? error.message
          : "Unable to generate this prediction.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <div className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-emerald-400">
          AlphaEdge Pulse
        </p>

        <h1 className="mt-3 text-3xl font-semibold sm:text-5xl">
          Probability-based stock direction
        </h1>

        <p className="mt-4 text-sm leading-6 text-zinc-400 sm:text-base">
          Train a chronological baseline model on historical
          candles and estimate bearish, neutral and bullish
          probabilities for the selected horizon.
        </p>
      </div>

      <form
        onSubmit={(event) => void handleSubmit(event)}
        className="mt-8 rounded-2xl border border-white/10 bg-black/40 p-5 sm:p-6"
      >
        <div className="grid gap-5 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <label
              htmlFor="pulse-symbol"
              className="text-sm font-medium text-zinc-300"
            >
              Stock symbol
            </label>

            <input
              id="pulse-symbol"
              value={symbol}
              onChange={(event) =>
                setSymbol(event.target.value)
              }
              placeholder="RELIANCE.NSE"
              autoComplete="off"
              className="mt-2 w-full rounded-xl border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm text-white outline-none transition placeholder:text-zinc-700 focus:border-emerald-500/50"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-black transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoading
              ? "Training model..."
              : "Generate prediction"}
          </button>
        </div>

        <fieldset className="mt-5">
          <legend className="text-sm font-medium text-zinc-300">
            Prediction horizon
          </legend>

          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            {HORIZONS.map((option) => {
              const isSelected =
                option.value === horizon;

              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() =>
                    setHorizon(option.value)
                  }
                  className={`rounded-xl border p-4 text-left transition ${
                    isSelected
                      ? "border-emerald-500/40 bg-emerald-500/10"
                      : "border-white/10 bg-zinc-950 hover:border-zinc-700"
                  }`}
                >
                  <p
                    className={
                      isSelected
                        ? "text-sm font-semibold text-emerald-300"
                        : "text-sm font-semibold text-zinc-200"
                    }
                  >
                    {option.label}
                  </p>

                  <p className="mt-1 text-xs text-zinc-600">
                    {option.description}
                  </p>
                </button>
              );
            })}
          </div>
        </fieldset>

        {errorMessage && (
          <div className="mt-5 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3">
            <p className="text-sm text-red-300">
              {errorMessage}
            </p>
          </div>
        )}
      </form>

      {prediction && (
        <div className="mt-8 space-y-6">
          <section className="rounded-2xl border border-white/10 bg-black/40 p-5 sm:p-7">
            <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
              <div>
                <p className="text-sm text-zinc-500">
                  {prediction.displaySymbol}
                </p>

                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <h2 className="text-3xl font-semibold">
                    {directionLabel(
                      prediction.predictedDirection,
                    )}
                  </h2>

                  <span
                    className={`rounded-full border px-3 py-1 text-xs font-medium ${directionClassName(
                      prediction.predictedDirection,
                    )}`}
                  >
                    {prediction.horizon}-session outlook
                  </span>
                </div>

                <p className="mt-3 text-sm text-zinc-500">
                  Current price:{" "}
                  {formatPrice(prediction.currentPrice)}
                </p>
              </div>

              <div className="sm:text-right">
                <p className="text-4xl font-semibold text-emerald-300">
                  {prediction.confidenceScore}%
                </p>

                <p className="mt-1 text-xs uppercase tracking-wide text-zinc-600">
                  Model confidence
                </p>
              </div>
            </div>

            <div className="mt-7 grid gap-4 sm:grid-cols-3">
              <ProbabilityCard
                label="Bearish"
                value={prediction.bearishProbability}
                tone="bearish"
              />

              <ProbabilityCard
                label="Neutral"
                value={prediction.neutralProbability}
                tone="neutral"
              />

              <ProbabilityCard
                label="Bullish"
                value={prediction.bullishProbability}
                tone="bullish"
              />
            </div>

            <div className="mt-6 flex flex-col gap-2 border-t border-white/5 pt-5 text-xs text-zinc-600 sm:flex-row sm:justify-between">
              <span>
                As of {formatTimestamp(prediction.asOf)}
              </span>

              <Link
                href={`/stocks/${encodeURIComponent(
                  prediction.displaySymbol,
                )}`}
                className="text-emerald-400 transition hover:text-emerald-300"
              >
                Open full stock analysis -&gt;
              </Link>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-zinc-950 p-5 sm:p-7">
            <h2 className="text-xl font-semibold">
              Model evaluation
            </h2>

            <p className="mt-2 text-sm text-zinc-500">
              Chronological holdout and walk-forward
              out-of-sample performance.
            </p>

            <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                label="Holdout accuracy"
                value={formatPercentage(
                  prediction.evaluation.holdoutAccuracy,
                )}
              />

              <MetricCard
                label="Holdout balanced"
                value={formatPercentage(
                  prediction.evaluation
                    .holdoutBalancedAccuracy,
                )}
              />

              <MetricCard
                label="Walk-forward accuracy"
                value={formatPercentage(
                  prediction.evaluation
                    .walkForwardAccuracy,
                )}
              />

              <MetricCard
                label="Walk-forward balanced"
                value={formatPercentage(
                  prediction.evaluation
                    .walkForwardBalancedAccuracy,
                )}
              />
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <SmallMetric
                label="Training rows"
                value={String(
                  prediction.evaluation.trainingRowCount,
                )}
              />

              <SmallMetric
                label="Testing rows"
                value={String(
                  prediction.evaluation.testingRowCount,
                )}
              />

              <SmallMetric
                label="Walk-forward folds"
                value={String(
                  prediction.evaluation.walkForwardFoldCount,
                )}
              />

              <SmallMetric
                label="Out-of-sample predictions"
                value={String(
                  prediction.evaluation
                    .walkForwardTotalPredictions,
                )}
              />
            </div>
          </section>

          <section className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5">
            <p className="text-sm leading-6 text-amber-100/80">
              {prediction.disclaimer}
            </p>

            <p className="mt-2 text-xs text-amber-200/50">
              Model: {prediction.modelName} |{" "}
              {prediction.modelVersion}
            </p>
          </section>
        </div>
      )}
    </div>
  );
}

function ProbabilityCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: PredictionDirection;
}) {
  const width = Math.max(
    0,
    Math.min(100, Number(value) * 100),
  );

  const barClassName =
    tone === "bullish"
      ? "bg-emerald-400"
      : tone === "bearish"
        ? "bg-red-400"
        : "bg-amber-300";

  return (
    <div className="rounded-xl border border-white/10 bg-zinc-950 p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-400">
          {label}
        </p>

        <p className="text-lg font-semibold text-white">
          {formatPercentage(value)}
        </p>
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-zinc-800">
        <div
          className={`h-full rounded-full ${barClassName}`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/40 p-4">
      <p className="text-xs uppercase tracking-wide text-zinc-600">
        {label}
      </p>

      <p className="mt-2 text-2xl font-semibold text-zinc-100">
        {value}
      </p>
    </div>
  );
}

function SmallMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-white/5 bg-black/20 px-4 py-3">
      <p className="text-xs text-zinc-600">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold text-zinc-300">
        {value}
      </p>
    </div>
  );
}
