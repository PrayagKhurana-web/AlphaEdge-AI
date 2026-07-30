import {
  announceUnauthorizedSession,
  clearStoredAuthentication,
  getStoredAccessToken,
} from "@/auth/storage";

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

export type FinancialStatementPeriod = "annual" | "quarterly";

export type FinancialStatementRecord = {
  reportingDate: string;

  totalRevenue: string | null;
  grossProfit: string | null;
  operatingIncome: string | null;
  ebitda: string | null;
  netIncome: string | null;
  dilutedEps: string | null;

  totalAssets: string | null;
  totalLiabilities: string | null;
  shareholderEquity: string | null;
  cashAndEquivalents: string | null;
  totalDebt: string | null;

  operatingCashFlow: string | null;
  capitalExpenditure: string | null;
  freeCashFlow: string | null;
  investingCashFlow: string | null;
  financingCashFlow: string | null;
};

export type FinancialStatementsResponse = {
  symbol: string;
  displaySymbol: string;
  companyName: string;
  exchange: "NSE" | "BSE";
  period: FinancialStatementPeriod;
  currency: string | null;
  statements: FinancialStatementRecord[];
  fetchedAt: string;
};

export async function getFinancialStatements(
  displaySymbol: string,
  period: FinancialStatementPeriod = "annual",
): Promise<FinancialStatementsResponse> {
  const normalizedDisplaySymbol = displaySymbol.trim();

  if (!normalizedDisplaySymbol) {
    throw new Error("Display symbol is required");
  }

  const params = new URLSearchParams({
    period,
  });

  return fetchApi<FinancialStatementsResponse>(
    `/api/v1/stocks/${encodeURIComponent(normalizedDisplaySymbol)}/financial-statements?${params.toString()}`,
    `Unable to fetch financial statements for ${normalizedDisplaySymbol}`,
  );
}

export type FinancialHealthRating =
  | "strong"
  | "healthy"
  | "mixed"
  | "weak"
  | "high_risk";

export type FinancialHealthObservationType =
  | "positive"
  | "neutral"
  | "negative";

export type FinancialHealthObservation = {
  category: string;
  observationType: FinancialHealthObservationType;
  message: string;
};

export type FinancialHealthResponse = {
  symbol: string;
  displaySymbol: string;
  companyName: string;
  exchange: "NSE" | "BSE";
  period: FinancialStatementPeriod;
  currency: string | null;

  overallScore: number;
  rating: FinancialHealthRating;

  growthScore: number;
  profitabilityScore: number;
  balanceSheetScore: number;
  cashFlowScore: number;

  revenueGrowth: string | null;
  netIncomeGrowth: string | null;
  ebitdaMargin: string | null;
  netProfitMargin: string | null;
  debtToEquity: string | null;
  operatingCashFlowGrowth: string | null;
  freeCashFlowGrowth: string | null;
  cashConversionRatio: string | null;

  observations: FinancialHealthObservation[];
  calculatedAt: string;
};

export async function getFinancialHealth(
  displaySymbol: string,
  period: FinancialStatementPeriod = "annual",
): Promise<FinancialHealthResponse> {
  const normalizedDisplaySymbol = displaySymbol.trim();

  if (!normalizedDisplaySymbol) {
    throw new Error("Display symbol is required");
  }

  const params = new URLSearchParams({
    period,
  });

  return fetchApi<FinancialHealthResponse>(
    `/api/v1/stocks/${encodeURIComponent(normalizedDisplaySymbol)}/financial-health?${params.toString()}`,
    `Unable to fetch financial health for ${normalizedDisplaySymbol}`,
  );
}


export type StockOutlook =
  | "bullish"
  | "neutral"
  | "bearish";

export type StockRiskLevel =
  | "low"
  | "medium"
  | "high";

export type StockAnalysisReasonType =
  | "positive"
  | "neutral"
  | "negative";

export type StockAnalysisReason = {
  category: string;
  reasonType: StockAnalysisReasonType;
  message: string;
};

export type StockAnalysisResponse = {
  symbol: string;
  displaySymbol: string;

  outlook: StockOutlook;
  bullishProbability: number;
  bearishProbability: number;
  confidenceScore: number;
  riskLevel: StockRiskLevel;
  timeHorizon: string;

  overallScore: number;
  technicalScore: number;
  financialScore: number;
  marketActivityScore: number;

  currentPrice: string;
  nearestSupport: string | null;
  nearestResistance: string | null;

  reasons: StockAnalysisReason[];
  calculatedAt: string;
};

export async function getStockAnalysis(
  displaySymbol: string,
  technicalPeriod = "1y",
  interval = "1d",
  financialPeriod: FinancialStatementPeriod = "annual",
): Promise<StockAnalysisResponse> {
  const normalizedDisplaySymbol = displaySymbol.trim();

  if (!normalizedDisplaySymbol) {
    throw new Error("Display symbol is required");
  }

  const params = new URLSearchParams({
    interval,
    technicalPeriod,
    financialPeriod,
  });

  return fetchApi<StockAnalysisResponse>(
    `/api/v1/stocks/${encodeURIComponent(
      normalizedDisplaySymbol,
    )}/analysis?${params.toString()}`,
    `Unable to fetch stock analysis for ${normalizedDisplaySymbol}`,
  );
}


export type AuthenticatedUser = {
  id: number;
  email: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
};

export type AuthenticationResponse = {
  accessToken: string;
  tokenType: "bearer";
  user: AuthenticatedUser;
};

type AuthenticationErrorDetail = {
  code?: string;
  message?: string;
};

type AuthenticationValidationIssue = {
  msg?: string;
};

type AuthenticationErrorResponse = {
  detail?:
    | AuthenticationErrorDetail
    | AuthenticationValidationIssue[];
};

export class AuthenticationApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(
    message: string,
    status: number,
    code: string | null = null,
  ) {
    super(message);
    this.name = "AuthenticationApiError";
    this.status = status;
    this.code = code;
  }
}

async function requestAuthenticationApi<T>(
  endpoint: string,
  init?: RequestInit,
  accessToken?: string,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init?.body
        ? { "Content-Type": "application/json" }
        : {}),
      ...(accessToken
        ? { Authorization: `Bearer ${accessToken}` }
        : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let errorBody: AuthenticationErrorResponse | null = null;

    try {
      errorBody =
        (await response.json()) as AuthenticationErrorResponse;
    } catch {
      errorBody = null;
    }

    const detail = errorBody?.detail;
    const validationMessage = Array.isArray(detail)
      ? detail[0]?.msg
      : undefined;
    const structuredMessage = !Array.isArray(detail)
      ? detail?.message
      : undefined;
    const structuredCode = !Array.isArray(detail)
      ? detail?.code ?? null
      : null;

    throw new AuthenticationApiError(
      structuredMessage ??
        validationMessage ??
        `Authentication request failed with status ${response.status}`,
      response.status,
      structuredCode,
    );
  }

  return (await response.json()) as T;
}

export async function registerUser(
  email: string,
  password: string,
): Promise<AuthenticationResponse> {
  return requestAuthenticationApi<AuthenticationResponse>(
    "/api/v1/auth/register",
    {
      method: "POST",
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        password,
      }),
    },
  );
}

export async function loginUser(
  email: string,
  password: string,
): Promise<AuthenticationResponse> {
  return requestAuthenticationApi<AuthenticationResponse>(
    "/api/v1/auth/login",
    {
      method: "POST",
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        password,
      }),
    },
  );
}

export async function getCurrentUser(
  accessToken: string,
): Promise<AuthenticatedUser> {
  return requestAuthenticationApi<AuthenticatedUser>(
    "/api/v1/auth/me",
    undefined,
    accessToken,
  );
}

function createAuthenticatedHeaders(
  init?: RequestInit,
): HeadersInit {
  const accessToken = getStoredAccessToken();

  return {
    Accept: "application/json",
    ...(init?.body
      ? { "Content-Type": "application/json" }
      : {}),
    ...(accessToken
      ? { Authorization: `Bearer ${accessToken}` }
      : {}),
    ...init?.headers,
  };
}

function handleProtectedAuthenticationFailure(
  status: number,
): void {
  if (status !== 401) {
    return;
  }

  clearStoredAuthentication();
  announceUnauthorizedSession();
}

export type WatchlistItem = {
  id: number;
  displaySymbol: string;
  exchange: "NSE" | "BSE";
  createdAt: string;
};

export type WatchlistResponse = {
  items: WatchlistItem[];
  count: number;
};

type WatchlistErrorDetail = {
  code?: string;
  message?: string;
};

type WatchlistErrorResponse = {
  detail?: WatchlistErrorDetail;
};

export class WatchlistApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(
    message: string,
    status: number,
    code: string | null = null,
  ) {
    super(message);
    this.name = "WatchlistApiError";
    this.status = status;
    this.code = code;
  }
}

async function requestWatchlistApi<T>(
  endpoint: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...init,
    cache: "no-store",
    headers: createAuthenticatedHeaders(init),
  });

  if (!response.ok) {
    handleProtectedAuthenticationFailure(response.status);

    let errorBody: WatchlistErrorResponse | null = null;

    try {
      errorBody = (await response.json()) as WatchlistErrorResponse;
    } catch {
      errorBody = null;
    }

    throw new WatchlistApiError(
      errorBody?.detail?.message ??
        `Watchlist request failed with status ${response.status}`,
      response.status,
      errorBody?.detail?.code ?? null,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function getWatchlist(): Promise<WatchlistResponse> {
  return requestWatchlistApi<WatchlistResponse>(
    "/api/v1/watchlist",
  );
}

export async function addToWatchlist(
  displaySymbol: string,
): Promise<WatchlistItem> {
  const normalizedDisplaySymbol = displaySymbol.trim().toUpperCase();

  if (!normalizedDisplaySymbol) {
    throw new Error("Display symbol is required");
  }

  return requestWatchlistApi<WatchlistItem>(
    "/api/v1/watchlist",
    {
      method: "POST",
      body: JSON.stringify({
        displaySymbol: normalizedDisplaySymbol,
      }),
    },
  );
}

export async function removeFromWatchlist(
  displaySymbol: string,
): Promise<void> {
  const normalizedDisplaySymbol = displaySymbol.trim().toUpperCase();

  if (!normalizedDisplaySymbol) {
    throw new Error("Display symbol is required");
  }

  await requestWatchlistApi<void>(
    `/api/v1/watchlist/${encodeURIComponent(
      normalizedDisplaySymbol,
    )}`,
    {
      method: "DELETE",
    },
  );
}


export type PortfolioHolding = {
  id: number;
  displaySymbol: string;
  exchange: "NSE" | "BSE";
  quantity: string;
  averageBuyPrice: string;
  createdAt: string;
  updatedAt: string;
};

export type PortfolioPosition = {
  id: number;
  displaySymbol: string;
  companyName: string;
  exchange: "NSE" | "BSE";
  quantity: string;
  averageBuyPrice: string;
  currentPrice: string;
  investedAmount: string;
  currentValue: string;
  profitLoss: string;
  returnPercent: string;
  allocationPercent: string;
};

export type PortfolioResponse = {
  positions: PortfolioPosition[];
  count: number;
  totalInvested: string;
  totalCurrentValue: string;
  totalProfitLoss: string;
  totalReturnPercent: string;
};

type PortfolioErrorDetail = {
  code?: string;
  message?: string;
};

type PortfolioValidationIssue = {
  msg?: string;
};

type PortfolioErrorResponse = {
  detail?: PortfolioErrorDetail | PortfolioValidationIssue[];
};

export class PortfolioApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(
    message: string,
    status: number,
    code: string | null = null,
  ) {
    super(message);
    this.name = "PortfolioApiError";
    this.status = status;
    this.code = code;
  }
}

async function requestPortfolioApi<T>(
  endpoint: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...init,
    cache: "no-store",
    headers: createAuthenticatedHeaders(init),
  });

  if (!response.ok) {
    handleProtectedAuthenticationFailure(response.status);

    let errorBody: PortfolioErrorResponse | null = null;

    try {
      errorBody = (await response.json()) as PortfolioErrorResponse;
    } catch {
      errorBody = null;
    }

    const detail = errorBody?.detail;

    const validationMessage = Array.isArray(detail)
      ? detail[0]?.msg
      : undefined;

    const structuredMessage = !Array.isArray(detail)
      ? detail?.message
      : undefined;

    const structuredCode = !Array.isArray(detail)
      ? detail?.code ?? null
      : null;

    throw new PortfolioApiError(
      structuredMessage ??
        validationMessage ??
        `Portfolio request failed with status ${response.status}`,
      response.status,
      structuredCode,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function getPortfolio(): Promise<PortfolioResponse> {
  return requestPortfolioApi<PortfolioResponse>(
    "/api/v1/portfolio",
  );
}

export async function addPortfolioHolding(
  displaySymbol: string,
  quantity: string,
  averageBuyPrice: string,
): Promise<PortfolioHolding> {
  return requestPortfolioApi<PortfolioHolding>(
    "/api/v1/portfolio",
    {
      method: "POST",
      body: JSON.stringify({
        displaySymbol: displaySymbol.trim().toUpperCase(),
        quantity,
        averageBuyPrice,
      }),
    },
  );
}

export async function updatePortfolioHolding(
  displaySymbol: string,
  quantity: string,
  averageBuyPrice: string,
): Promise<PortfolioHolding> {
  return requestPortfolioApi<PortfolioHolding>(
    `/api/v1/portfolio/${encodeURIComponent(
      displaySymbol.trim().toUpperCase(),
    )}`,
    {
      method: "PUT",
      body: JSON.stringify({
        quantity,
        averageBuyPrice,
      }),
    },
  );
}

export async function deletePortfolioHolding(
  displaySymbol: string,
): Promise<void> {
  await requestPortfolioApi<void>(
    `/api/v1/portfolio/${encodeURIComponent(
      displaySymbol.trim().toUpperCase(),
    )}`,
    {
      method: "DELETE",
    },
  );
}
