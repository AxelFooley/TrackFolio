import axios from 'axios';
import type {
  Transaction,
  Position,
  PortfolioOverview,
  AssetDetail,
  Benchmark,
  PriceData,
  PerformanceData,
  LastUpdate,
  ImportResponse,
  TransactionUpdate,
  TransactionCreate,
  RealtimePrice,
} from './types';
import type {
  TickerSearchResult,
  PopularTickersResponse
} from './tickerUtils';

// Re-export ticker search types
export type { TickerSearchResult, PopularTickersResponse };

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Transaction endpoints
export async function importTransactions(file: File): Promise<ImportResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post<ImportResponse>('/api/transactions/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
}

export async function getTransactions(
  skip: number = 0,
  limit: number = 100
): Promise<Transaction[]> {
  const response = await api.get<Transaction[]>('/api/transactions/', {
    params: { skip, limit },
  });
  return response.data;
}

export async function createTransaction(
  data: TransactionCreate
): Promise<Transaction> {
  const response = await api.post<Transaction>('/api/transactions/', data);
  return response.data;
}

export async function updateTransaction(
  id: number,
  data: TransactionUpdate
): Promise<Transaction> {
  const response = await api.put<Transaction>(`/api/transactions/${id}`, data);
  return response.data;
}

export async function deleteTransaction(id: number): Promise<{ message: string }> {
  const response = await api.delete(`/api/transactions/${id}`);
  return response.data;
}

// Portfolio endpoints
export async function getPortfolioOverview(): Promise<PortfolioOverview> {
  const response = await api.get<PortfolioOverview>('/api/portfolio/overview');
  return response.data;
}

export async function getHoldings(): Promise<Position[]> {
  const response = await api.get<Position[]>('/api/portfolio/holdings');
  return response.data;
}

export async function getPerformanceData(range?: string): Promise<PerformanceData> {
  const response = await api.get<PerformanceData>('/api/portfolio/performance', {
    params: { range },
  });
  return response.data;
}

// Asset endpoints
export async function getAssetDetail(ticker: string): Promise<AssetDetail> {
  const response = await api.get<AssetDetail>(`/api/assets/${ticker}`);
  return response.data;
}

export async function getAssetTransactions(ticker: string): Promise<Transaction[]> {
  const response = await api.get<Transaction[]>(`/api/assets/${ticker}/transactions`);
  return response.data;
}

export async function getAssetPrices(
  ticker: string,
  range: string = '1Y'
): Promise<PriceData[]> {
  const response = await api.get<PriceData[]>(`/api/prices/${ticker}`, {
    params: { range },
  });
  return response.data;
}

// Benchmark endpoints
export async function getBenchmark(): Promise<Benchmark> {
  const response = await api.get<Benchmark>('/api/benchmark/');
  return response.data;
}

export async function setBenchmark(ticker: string): Promise<Benchmark> {
  const response = await api.post<Benchmark>('/api/benchmark/', { ticker });
  return response.data;
}

export async function searchTickers(query: string): Promise<TickerSearchResult[]> {
  const response = await api.get<TickerSearchResult[]>('/api/benchmark/search', {
    params: { q: query },
  });
  return response.data;
}

// Yahoo Finance ticker search
export async function searchYahooTickers(query: string): Promise<TickerSearchResult[]> {
  try {
    const response = await api.get<{results: TickerSearchResult[]}>('/api/tickers/search', {
      params: { q: query },
    });

    // Add robust error handling for response structure
    if (!response.data) {
      console.warn('No data in search response:', response);
      return [];
    }

    // Handle both array and object with results property
    if (Array.isArray(response.data)) {
      return response.data;
    }

    if (response.data.results && Array.isArray(response.data.results)) {
      return response.data.results;
    }

    console.warn('Unexpected response structure:', response.data);
    return [];
  } catch (error) {
    console.error('Error searching tickers:', error);
    return [];
  }
}

// Popular tickers
export async function getPopularTickers(): Promise<PopularTickersResponse> {
  const response = await api.get<PopularTickersResponse>('/api/tickers/popular');
  return response.data;
}

// Historical price fetching
export interface HistoricalPriceResponse {
  ticker: string;
  date: string;
  price: number | null;
  currency: string | null;
  is_historical: boolean;
  error: string | null;
}

export async function getHistoricalPrice(ticker: string, date: string, signal?: AbortSignal): Promise<HistoricalPriceResponse> {
  const response = await api.get<HistoricalPriceResponse>('/api/prices/historical', {
    params: { ticker, date },
    signal,
  });
  return response.data;
}

// Price update endpoints
export async function refreshPrices(): Promise<{ message: string }> {
  const response = await api.post<{ message: string }>('/api/prices/refresh');
  return response.data;
}

export async function getLastUpdate(): Promise<LastUpdate> {
  const response = await api.get<LastUpdate>('/api/prices/last-update');
  return response.data;
}

export async function getRealtimePrices(): Promise<RealtimePrice[]> {
  const response = await api.get<{ prices: RealtimePrice[] }>('/api/prices/realtime');
  return response.data.prices;
}

export default api;
