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