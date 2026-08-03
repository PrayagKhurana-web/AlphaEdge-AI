"use client";

import { useEffect, useMemo, useState } from "react";

import {
  getTechnicalAnalysis,
  type TechnicalAnalysisResponse,
  type TechnicalSignal,
  type TechnicalTrend,
} from "@/services/api";

type TechnicalIndicatorsProps = {
  displaySymbol: string;
};

type SignalTone = "bullish" | "bearish" | "neutral";

type IndicatorCard = {
  label: string;
  value: string;
  interpretation: string;
  tone: SignalTone;
};

function formatNumber(
  value: string | null,
  maximumFractionDigits = 2,
): string {
  if (value === null) {
    return "Not available";
  }

  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits,
  }).format(parsedValue);
}

function formatPrice(value: string | null): string {
  if (value === null) {
    return "Not available";
  }

  return `₹${formatNumber(value)}`;
}

function formatSignal(signal: TechnicalSignal): string {
  const labels: Record<TechnicalSignal, string> = {
    strong_buy: "Strong buy",
    buy: "Buy",
    hold: "Hold",
    sell: "Sell",
    strong_sell: "Strong sell",
  };

  return labels[signal];
}

function formatTrend(trend: TechnicalTrend): string {
  return `${trend.charAt(0).toUpperCase()}${trend.slice(1)}`;
}

function signalTone(signal: TechnicalSignal): SignalTone {
  if (signal === "strong_buy" || signal === "buy") {
    return "bullish";
  }

  if (signal === "strong_sell" || signal === "sell") {
    return "bearish";
  }

  return "neutral";
}

function trendTone(trend: TechnicalTrend): SignalTone {
  if (trend === "bullish") {
    return "bullish";
  }

  if (trend === "bearish") {
    return "bearish";
  }

  return "neutral";
}

function comparePriceToAverage(
  currentPrice: string,
  average: string | null,
  label: string,
): Pick<IndicatorCard, "interpretation" | "tone"> {
  if (average === null) {
    return {
      interpretation: `${label} is not available.`,
      tone: "neutral",
    };
  }

  const price = Number(currentPrice);
  const averageValue = Number(average);

  if (!Number.isFinite(price) || !Number.isFinite(averageValue)) {
    return {
      interpretation: "Unable to interpret this value.",
      tone: "neutral",
    };
  }

  if (price > averageValue) {
    return {
      interpretation: `Price is above ${label}, indicating positive momentum.`,
      tone: "bullish",
    };
  }

  if (price < averageValue) {
    return {
      interpretation: `Price is below ${label}, indicating weak momentum.`,
      tone: "bearish",
    };
  }

  return {
    interpretation: `Price is near ${label}.`,
    tone: "neutral",
  };
}

function interpretRsi(value: string | null): Pick<
  IndicatorCard,
  "interpretation" | "tone"
> {
  if (value === null) {
    return {
      interpretation: "RSI is not available.",
      tone: "neutral",
    };
  }

  const rsi = Number(value);

  if (!Number.isFinite(rsi)) {
    return {
      interpretation: "Unable to interpret RSI.",
      tone: "neutral",
    };
  }

  if (rsi >= 70) {
    return {
      interpretation: "Overbought territory; momentum may be stretched.",
      tone: "bearish",
    };
  }

  if (rsi <= 30) {
    return {
      interpretation: "Oversold territory; selling pressure may be stretched.",
      tone: "bullish",
    };
  }

  if (rsi >= 55) {
    return {
      interpretation: "Momentum is moderately positive.",
      tone: "bullish",
    };
  }

  if (rsi <= 45) {
    return {
      interpretation: "Momentum is moderately weak.",
      tone: "bearish",
    };
  }

  return {
    interpretation: "Momentum is neutral.",
    tone: "neutral",
  };
}

function interpretMacd(
  macd: string | null,
  macdSignal: string | null,
): Pick<IndicatorCard, "interpretation" | "tone"> {
  if (macd === null || macdSignal === null) {
    return {
      interpretation: "MACD comparison is not available.",
      tone: "neutral",
    };
  }

  const macdValue = Number(macd);
  const signalValue = Number(macdSignal);

  if (!Number.isFinite(macdValue) || !Number.isFinite(signalValue)) {
    return {
      interpretation: "Unable to interpret MACD.",
      tone: "neutral",
    };
  }

  if (macdValue > signalValue) {
    return {
      interpretation: "MACD is above its signal line.",
      tone: "bullish",
    };
  }

  if (macdValue < signalValue) {
    return {
      interpretation: "MACD is below its signal line.",
      tone: "bearish",
    };
  }

  return {
    interpretation: "MACD is aligned with its signal line.",
    tone: "neutral",
  };
}

function buildIndicatorCards(
  analysis: TechnicalAnalysisResponse,
): IndicatorCard[] {
  const sma20 = comparePriceToAverage(
    analysis.currentPrice,
    analysis.sma20,
    "SMA 20",
  );

  const sma50 = comparePriceToAverage(
    analysis.currentPrice,
    analysis.sma50,
    "SMA 50",
  );

  const sma200 = comparePriceToAverage(
    analysis.currentPrice,
    analysis.sma200,
    "SMA 200",
  );

  const rsi = interpretRsi(analysis.rsi14);
  const macd = interpretMacd(
    analysis.macd,
    analysis.macdSignal,
  );

  return [
    {
      label: "RSI 14",
      value: formatNumber(analysis.rsi14),
      ...rsi,
    },
    {
      label: "SMA 20",
      value: formatPrice(analysis.sma20),
      ...sma20,
    },
    {
      label: "SMA 50",
      value: formatPrice(analysis.sma50),
      ...sma50,
    },
    {
      label: "SMA 200",
      value: formatPrice(analysis.sma200),
      ...sma200,
    },
    {
      label: "MACD",
      value: formatNumber(analysis.macd),
      ...macd,
    },
    {
      label: "MACD signal",
      value: formatNumber(analysis.macdSignal),
      interpretation:
        analysis.macdHistogram === null
          ? "Histogram is not available."
          : `Histogram: ${formatNumber(analysis.macdHistogram)}`,
      tone:
        Number(analysis.macdHistogram) > 0
          ? "bullish"
          : Number(analysis.macdHistogram) < 0
            ? "bearish"
            : "neutral",
    },
    {
      label: "ATR 14",
      value: formatPrice(analysis.atr14),
      interpretation:
        "Measures recent price volatility, not direction.",
      tone: "neutral",
    },
    {
      label: "Volume ratio",
      value:
        analysis.volumeRatio === null
          ? "Not available"
          : `${formatNumber(analysis.volumeRatio)}x`,
      interpretation:
        analysis.volumeRatio !== null &&
        Number(analysis.volumeRatio) >= 1
          ? "Current volume is above its 20-day average."
          : "Current volume is below its 20-day average.",
      tone:
        analysis.volumeRatio !== null &&
        Number(analysis.volumeRatio) >= 1
          ? "bullish"
          : "neutral",
    },
  ];
}

function toneClassName(tone: SignalTone): string {
  if (tone === "bullish") {
    return "border-emerald-900/60 bg-emerald-950/20 text-emerald-300";
  }

  if (tone === "bearish") {
    return "border-red-900/60 bg-red-950/20 text-red-300";
  }

  return "border-zinc-700 bg-zinc-900 text-zinc-300";
}

export default function TechnicalIndicators({
  displaySymbol,
}: TechnicalIndicatorsProps) {
  const [analysis, setAnalysis] =
    useState<TechnicalAnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isCancelled = false;

    async function loadAnalysis(): Promise<void> {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const response = await getTechnicalAnalysis(
          displaySymbol,
          "1y",
          "1d",
        );

        if (!isCancelled) {
          setAnalysis(response);
        }
      } catch {
        if (!isCancelled) {
          setAnalysis(null);
          setErrorMessage(
            "Unable to load technical analysis right now.",
          );
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadAnalysis();

    return () => {
      isCancelled = true;
    };
  }, [displaySymbol]);

  const cards = useMemo(
    () => (analysis ? buildIndicatorCards(analysis) : []),
    [analysis],
  );

  if (isLoading) {
    return (
      <section className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
        <p className="text-sm text-zinc-500">
          Loading technical indicators...
        </p>
      </section>
    );
  }

  if (errorMessage || !analysis) {
    return (
      <section className="mt-8 rounded-2xl border border-red-900/50 bg-red-950/20 p-6">
        <p className="text-sm text-red-300">
          {errorMessage || "Technical analysis is unavailable."}
        </p>
      </section>
    );
  }

  const outlookTone = signalTone(analysis.signal);

  return (
    <section className="mt-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-xl font-semibold">
            Technical indicators
          </h2>

          <p className="mt-1 text-sm text-zinc-400">
            Rule-based signals calculated from one year of daily data
          </p>
        </div>

        <div
          className={`rounded-xl border px-4 py-3 ${toneClassName(
            outlookTone,
          )}`}
        >
          <p className="text-xs uppercase tracking-wide opacity-70">
            Overall signal
          </p>

          <p className="mt-1 text-lg font-semibold">
            {formatSignal(analysis.signal)}
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <article
            key={card.label}
            className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5"
          >
            <div className="flex items-start justify-between gap-3">
              <p className="text-xs uppercase tracking-wide text-zinc-500">
                {card.label}
              </p>

              <span
                className={`rounded-full border px-2 py-1 text-[10px] font-medium uppercase tracking-wide ${toneClassName(
                  card.tone,
                )}`}
              >
                {card.tone}
              </span>
            </div>

            <p className="mt-3 text-xl font-semibold text-zinc-100">
              {card.value}
            </p>

            <p className="mt-2 text-sm leading-6 text-zinc-400">
              {card.interpretation}
            </p>
          </article>
        ))}
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <LevelCard
          label="Trend"
          value={formatTrend(analysis.trend)}
          tone={trendTone(analysis.trend)}
        />

        <LevelCard
          label="Nearest support"
          value={formatPrice(analysis.nearestSupport)}
          tone="bullish"
        />

        <LevelCard
          label="Nearest resistance"
          value={formatPrice(analysis.nearestResistance)}
          tone="bearish"
        />

        <LevelCard
          label="Bollinger range"
          value={`${formatPrice(
            analysis.bollingerLower,
          )} - ${formatPrice(analysis.bollingerUpper)}`}
          tone="neutral"
        />
      </div>

      <p className="mt-4 text-xs leading-5 text-zinc-500">
        These indicators are deterministic technical signals based on
        historical prices. They are not predictions or financial advice.
      </p>
    </section>
  );
}

type LevelCardProps = {
  label: string;
  value: string;
  tone: SignalTone;
};

function LevelCard({
  label,
  value,
  tone,
}: LevelCardProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/50 p-4">
      <p className="text-xs uppercase tracking-wide text-zinc-500">
        {label}
      </p>

      <p className="mt-2 break-words text-base font-semibold text-zinc-100">
        {value}
      </p>

      <span
        className={`mt-3 inline-block rounded-full border px-2 py-1 text-[10px] font-medium uppercase tracking-wide ${toneClassName(
          tone,
        )}`}
      >
        {tone}
      </span>
    </div>
  );
}
