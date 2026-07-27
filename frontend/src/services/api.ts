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