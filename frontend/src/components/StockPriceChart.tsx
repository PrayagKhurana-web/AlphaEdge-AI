"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  getStockHistory,
  type HistoricalCandle,
} from "@/services/api";

type StockPriceChartProps = {
  displaySymbol: string;
};

type ChartRange = {
  label: string;
  period: string;
  interval: string;
};

type ChartPoint = {
  timestamp: string;
  dateLabel: string;
  close: number;
  volume: number;
};

const CHART_RANGES: ChartRange[] = [
  { label: "1W", period: "5d", interval: "1d" },
  { label: "1M", period: "1mo", interval: "1d" },
  { label: "3M", period: "3mo", interval: "1d" },
  { label: "6M", period: "6mo", interval: "1d" },
  { label: "1Y", period: "1y", interval: "1d" },
];

function formatPrice(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatAxisPrice(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatDateLabel(
  timestamp: string,
  period: string,
): string {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  if (period === "5d" || period === "1mo") {
    return new Intl.DateTimeFormat("en-IN", {
      day: "2-digit",
      month: "short",
      timeZone: "Asia/Kolkata",
    }).format(date);
  }

  return new Intl.DateTimeFormat("en-IN", {
    month: "short",
    year: period === "1y" ? "2-digit" : undefined,
    timeZone: "Asia/Kolkata",
  }).format(date);
}

function formatTooltipDate(timestamp: string): string {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }

  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeZone: "Asia/Kolkata",
  }).format(date);
}

function convertCandles(
  candles: HistoricalCandle[],
  period: string,
): ChartPoint[] {
  return candles
    .map((candle) => ({
      timestamp: candle.timestamp,
      dateLabel: formatDateLabel(candle.timestamp, period),
      close: Number(candle.close),
      volume: candle.volume,
    }))
    .filter((point) => Number.isFinite(point.close));
}

type ChartTooltipProps = {
  active?: boolean;
  payload?: Array<{
    payload: ChartPoint;
  }>;
};

function ChartTooltip({
  active,
  payload,
}: ChartTooltipProps) {
  if (!active || !payload?.length) {
    return null;
  }

  const point = payload[0].payload;

  return (
    <div className="rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 shadow-xl">
      <p className="text-xs text-zinc-500">
        {formatTooltipDate(point.timestamp)}
      </p>

      <p className="mt-1 text-sm font-semibold text-white">
        {formatPrice(point.close)}
      </p>

      <p className="mt-1 text-xs text-zinc-500">
        Volume:{" "}
        {new Intl.NumberFormat("en-IN", {
          notation: "compact",
          maximumFractionDigits: 2,
        }).format(point.volume)}
      </p>
    </div>
  );
}

export default function StockPriceChart({
  displaySymbol,
}: StockPriceChartProps) {
  const [selectedRange, setSelectedRange] = useState(
    CHART_RANGES[1],
  );
  const [candles, setCandles] = useState<HistoricalCandle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isCancelled = false;

    async function loadHistory(): Promise<void> {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const response = await getStockHistory(
          displaySymbol,
          selectedRange.period,
          selectedRange.interval,
        );

        if (!isCancelled) {
          setCandles(response.candles);
        }
      } catch {
        if (!isCancelled) {
          setCandles([]);
          setErrorMessage(
            "Unable to load historical price data.",
          );
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadHistory();

    return () => {
      isCancelled = true;
    };
  }, [displaySymbol, selectedRange]);

  const chartData = useMemo(
    () => convertCandles(candles, selectedRange.period),
    [candles, selectedRange.period],
  );

  const firstPrice = chartData[0]?.close ?? 0;
  const latestPrice =
    chartData[chartData.length - 1]?.close ?? 0;
  const periodChange = latestPrice - firstPrice;
  const periodChangePercent =
    firstPrice !== 0 ? (periodChange / firstPrice) * 100 : 0;
  const isPositive = periodChange >= 0;

  const lineColour = isPositive ? "#10b981" : "#ef4444";
  const gradientId = isPositive
    ? "positivePriceGradient"
    : "negativePriceGradient";

  return (
    <section className="mt-8 rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5 sm:p-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <h2 className="text-xl font-semibold">
            Historical price
          </h2>

          <p className="mt-1 text-sm text-zinc-400">
            Closing-price movement for the selected range
          </p>

          {!isLoading &&
            !errorMessage &&
            chartData.length > 0 && (
              <p
                className={`mt-3 text-sm font-medium ${
                  isPositive
                    ? "text-emerald-400"
                    : "text-red-400"
                }`}
              >
                {isPositive ? "+" : ""}
                {formatPrice(periodChange)} (
                {isPositive ? "+" : ""}
                {periodChangePercent.toFixed(2)}%)
              </p>
            )}
        </div>

        <div className="flex flex-wrap gap-2">
          {CHART_RANGES.map((range) => {
            const isActive =
              range.label === selectedRange.label;

            return (
              <button
                key={range.label}
                type="button"
                onClick={() => setSelectedRange(range)}
                className={`rounded-lg px-3 py-2 text-xs font-medium transition ${
                  isActive
                    ? "bg-emerald-500 text-zinc-950"
                    : "border border-zinc-700 bg-zinc-950 text-zinc-400 hover:border-zinc-600 hover:text-white"
                }`}
              >
                {range.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-6 h-80">
        {isLoading ? (
          <div className="flex h-full items-center justify-center rounded-xl border border-zinc-800 bg-zinc-950/50">
            <p className="text-sm text-zinc-500">
              Loading price history...
            </p>
          </div>
        ) : errorMessage ? (
          <div className="flex h-full items-center justify-center rounded-xl border border-red-900/50 bg-red-950/20 px-4 text-center">
            <p className="text-sm text-red-300">
              {errorMessage}
            </p>
          </div>
        ) : chartData.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-xl border border-zinc-800 bg-zinc-950/50">
            <p className="text-sm text-zinc-500">
              No historical data is available for this range.
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={chartData}
              margin={{
                top: 10,
                right: 8,
                left: 0,
                bottom: 0,
              }}
            >
              <defs>
                <linearGradient
                  id={gradientId}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="5%"
                    stopColor={lineColour}
                    stopOpacity={0.28}
                  />
                  <stop
                    offset="95%"
                    stopColor={lineColour}
                    stopOpacity={0}
                  />
                </linearGradient>
              </defs>

              <CartesianGrid
                stroke="#27272a"
                strokeDasharray="3 3"
                vertical={false}
              />

              <XAxis
                dataKey="dateLabel"
                tick={{
                  fill: "#71717a",
                  fontSize: 11,
                }}
                tickLine={false}
                axisLine={false}
                minTickGap={24}
              />

              <YAxis
                domain={["auto", "auto"]}
                tickFormatter={formatAxisPrice}
                tick={{
                  fill: "#71717a",
                  fontSize: 11,
                }}
                tickLine={false}
                axisLine={false}
                width={52}
              />

              <Tooltip
                content={<ChartTooltip />}
                cursor={{
                  stroke: "#52525b",
                  strokeDasharray: "4 4",
                }}
              />

              <Area
                type="monotone"
                dataKey="close"
                stroke={lineColour}
                strokeWidth={2}
                fill={`url(#${gradientId})`}
                activeDot={{
                  r: 4,
                  fill: lineColour,
                  stroke: "#18181b",
                  strokeWidth: 2,
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
