export type HealthResponse = {
  status: string;
  service: string;
  version: string;
};

export type MarketIndexQuote = {
  displayName: string;
  price: string;
  change: string;
  changePercent: string;
  asOf: string;
};

export type MarketIndicesResponse = {
  nifty50?: MarketIndexQuote;
  sensex?: MarketIndexQuote;
  bankNifty?: MarketIndexQuote;
  indiaVix?: MarketIndexQuote;
  lastUpdated: string;
};

export type StockSearchResult = {
  symbol: string;
  companyName: string;
  exchange: "NSE" | "BSE";
  displaySymbol: string;
};

export type StockSearchResponse = {
  results: StockSearchResult[];
};

export type StockQuote = {
  symbol: string;
  displaySymbol: string;
  companyName: string;
  exchange: "NSE" | "BSE";
  price: string;
  change: string;
  changePercent: string;
  open: string;
  high: string;
  low: string;
  previousClose: string;
  asOf: string;
};

export type CompanyFundamentals = {
  symbol: string;
  displaySymbol: string;
  companyName: string;
  exchange: "NSE" | "BSE";
  sector: string | null;
  industry: string | null;
  website: string | null;
  businessSummary: string | null;
  marketCap: string | null;
  enterpriseValue: string | null;
  trailingPE: string | null;
  forwardPE: string | null;
  priceToBook: string | null;
  enterpriseToRevenue: string | null;
  enterpriseToEbitda: string | null;
  trailingEps: string | null;
  forwardEps: string | null;
  bookValuePerShare: string | null;
  returnOnEquity: string | null;
  returnOnAssets: string | null;
  profitMargin: string | null;
  operatingMargin: string | null;
  revenueGrowth: string | null;
  earningsGrowth: string | null;
  totalRevenue: string | null;
  netIncome: string | null;
  totalCash: string | null;
  totalDebt: string | null;
  debtToEquity: string | null;
  freeCashFlow: string | null;
  operatingCashFlow: string | null;
  dividendRate: string | null;
  dividendYield: string | null;
  payoutRatio: string | null;
  fiftyTwoWeekHigh: string | null;
  fiftyTwoWeekLow: string | null;
  fiftyDayAverage: string | null;
  twoHundredDayAverage: string | null;
  currency: string | null;
  fetchedAt: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function fetchApi<T>(
  endpoint: string,
  errorMessage: string,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`${errorMessage}. Status: ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function getHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>(
    "/api/v1/health",
    "Backend health check failed",
  );
}

export async function getMarketIndices(): Promise<MarketIndicesResponse> {
  return fetchApi<MarketIndicesResponse>(
    "/api/v1/market/indices",
    "Unable to fetch live market indices",
  );
}

export async function searchStocks(
  query: string,
  limit = 8,
): Promise<StockSearchResponse> {
  const normalizedQuery = query.trim();

  if (!normalizedQuery) {
    return { results: [] };
  }

  const params = new URLSearchParams({
    q: normalizedQuery,
    limit: String(limit),
  });

  return fetchApi<StockSearchResponse>(
    `/api/v1/stocks/search?${params.toString()}`,
    "Unable to search stocks",
  );
}

export async function getStockQuote(
  displaySymbol: string,
): Promise<StockQuote> {
  const normalizedDisplaySymbol = displaySymbol.trim();

  if (!normalizedDisplaySymbol) {
    throw new Error("Display symbol is required");
  }

  return fetchApi<StockQuote>(
    `/api/v1/stocks/${encodeURIComponent(normalizedDisplaySymbol)}/quote`,
    `Unable to fetch quote for ${normalizedDisplaySymbol}`,
  );
}
export async function getCompanyFundamentals(
  displaySymbol: string,
): Promise<CompanyFundamentals> {
  const normalizedDisplaySymbol = displaySymbol.trim();

  if (!normalizedDisplaySymbol) {
    throw new Error("Display symbol is required");
  }

  return fetchApi<CompanyFundamentals>(
    `/api/v1/stocks/${encodeURIComponent(normalizedDisplaySymbol)}/fundamentals`,
    `Unable to fetch fundamentals for ${normalizedDisplaySymbol}`,
  );
}
export type HistoricalCandle = {
  timestamp: string;
  open: string;
  high: string;
  low: string;
  close: string;
  adjustedClose: string | null;
  volume: number;
};

export type StockHistoryResponse = {
  symbol: string;
  displaySymbol: string;
  companyName: string;
  exchange: "NSE" | "BSE";
  interval: string;
  period: string;
  candles: HistoricalCandle[];
  fetchedAt: string;
};

export async function getStockHistory(
  displaySymbol: string,
  period = "1mo",
  interval = "1d",
): Promise<StockHistoryResponse> {
  const normalizedDisplaySymbol = displaySymbol.trim();

  if (!normalizedDisplaySymbol) {
    throw new Error("Display symbol is required");
  }

  const params = new URLSearchParams({
    period,
    interval,
  });

  return fetchApi<StockHistoryResponse>(
    `/api/v1/stocks/${encodeURIComponent(normalizedDisplaySymbol)}/history?${params.toString()}`,
    `Unable to fetch stock history for ${normalizedDisplaySymbol}`,
  );
}

export type TechnicalTrend =
  | "bullish"
  | "bearish"
  | "neutral";

export type TechnicalSignal =
  | "strong_buy"
  | "buy"
  | "hold"
  | "sell"
  | "strong_sell";

export type TechnicalAnalysisResponse = {
  symbol: string;
  displaySymbol: string;
  interval: string;
  currency: string | null;
  candleCount: number;
  latestCandleAt: string;
  calculatedAt: string;
  currentPrice: string;
  previousClose: string | null;
  priceChange: string | null;
  priceChangePercent: string | null;
  trend: TechnicalTrend;
  sma20: string | null;
  sma50: string | null;
  sma200: string | null;
  ema12: string | null;
  ema26: string | null;
  rsi14: string | null;
  macd: string | null;
  macdSignal: string | null;
  macdHistogram: string | null;
  bollingerUpper: string | null;
  bollingerMiddle: string | null;
  bollingerLower: string | null;
  atr14: string | null;
  currentVolume: number | null;
  averageVolume20: string | null;
  volumeRatio: string | null;
  fiftyTwoWeekHigh: string | null;
  fiftyTwoWeekLow: string | null;
  nearestSupport: string | null;
  nearestResistance: string | null;
  signal: TechnicalSignal;
};

export async function getTechnicalAnalysis(
  displaySymbol: string,
  period = "1y",
  interval = "1d",
): Promise<TechnicalAnalysisResponse> {
  const normalizedDisplaySymbol = displaySymbol.trim();

  if (!normalizedDisplaySymbol) {
    throw new Error("Display symbol is required");
  }

  const params = new URLSearchParams({
    period,
    interval,
  });

  return fetchApi<TechnicalAnalysisResponse>(
    `/api/v1/stocks/${encodeURIComponent(normalizedDisplaySymbol)}/technical-analysis?${params.toString()}`,
    `Unable to fetch technical analysis for ${normalizedDisplaySymbol}`,
  );
}
