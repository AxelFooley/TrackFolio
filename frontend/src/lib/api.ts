import axios, { AxiosError } from 'axios';
import type {
  Position,
  PortfolioOverview,
  Transaction,
  PerformanceData,
  Benchmark,
  PriceUpdate,
  TransactionCreate,
  TransactionUpdate,
  PaginatedResponse,
  CryptoPortfolio,
  CryptoPortfolioList,
  CryptoPosition,
  CryptoTransaction,
  CryptoPrice,
  CryptoPriceHistory,
  CryptoPerformanceData,
  CryptoPortfolioMetrics,
  CryptoPortfolioCreate,
  CryptoPortfolioUpdate,
  CryptoTransactionCreate,
  CryptoTransactionUpdate,
  RealtimePrice,
  RealtimePriceResponse,
  TickerSearchResult,
  WalletSyncStatus,
  WalletTransactionPreview,
} from './types';

// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Error handling
export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public response?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Normalize transaction type to lowercase for backend compatibility.
 * Frontend uses uppercase for better UX, backend expects lowercase.
 */
function normalizeTransactionType<T extends { transaction_type?: string }>(data: T): T {
  if (data.transaction_type) {
    return {
      ...data,
      transaction_type: data.transaction_type.toLowerCase(),
    };
  }
  return data;
}

// Request helper
async function apiRequest<T>(config: {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  url: string;
  data?: any;
  params?: any;
  headers?: any;
}): Promise<T> {
  try {
    const response = await apiClient.request<T>({
      ...config,
      method: config.method.toLowerCase() as any,
    });
    return response.data;
  } catch (error) {
    if (error instanceof AxiosError) {
      const message = error.response?.data?.detail || error.message;
      throw new ApiError(message, error.response?.status, error.response?.data);
    }
    throw new ApiError('An unexpected error occurred');
  }
}

// === Portfolio APIs (existing) ===

// Portfolio Overview
export async function getPortfolioOverview(): Promise<PortfolioOverview> {
  return apiRequest<PortfolioOverview>({
    method: 'GET',
    url: '/portfolio/overview',
  });
}

// Holdings
export async function getHoldings(): Promise<Position[]> {
  return apiRequest<Position[]>({
    method: 'GET',
    url: '/portfolio/holdings',
  });
}

// Performance Data
export async function getPerformanceData(range: string): Promise<PerformanceData[]> {
  return apiRequest<PerformanceData[]>({
    method: 'GET',
    url: '/portfolio/performance',
    params: { range },
  });
}

// Asset Detail
export async function getAssetDetail(ticker: string): Promise<Position> {
  return apiRequest<Position>({
    method: 'GET',
    url: `/assets/${ticker}`,
  });
}

// Asset Prices
export async function getAssetPrices(ticker: string, range: string): Promise<PerformanceData[]> {
  return apiRequest<PerformanceData[]>({
    method: 'GET',
    url: `/assets/${ticker}/prices`,
    params: { range },
  });
}

// Asset Transactions
export async function getAssetTransactions(ticker: string): Promise<Transaction[]> {
  return apiRequest<Transaction[]>({
    method: 'GET',
    url: `/assets/${ticker}/transactions`,
  });
}

// Transactions
export async function getTransactions(params?: {
  skip?: number;
  limit?: number;
}): Promise<PaginatedResponse<Transaction>> {
  return apiRequest<PaginatedResponse<Transaction>>({
    method: 'GET',
    url: '/transactions',
    params,
  });
}

export async function importTransactions(file: File): Promise<{ message: string }> {
  const formData = new FormData();
  formData.append('file', file);

  return apiRequest<{ message: string }>({
    method: 'POST',
    url: '/transactions/import',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
}

export async function createTransaction(data: TransactionCreate): Promise<Transaction> {
  return apiRequest<Transaction>({
    method: 'POST',
    url: '/transactions',
    data: normalizeTransactionType(data),
  });
}

export async function updateTransaction(id: number, data: TransactionUpdate): Promise<Transaction> {
  return apiRequest<Transaction>({
    method: 'PUT',
    url: `/transactions/${id}`,
    data: normalizeTransactionType(data),
  });
}

export async function deleteTransaction(id: number): Promise<void> {
  return apiRequest<void>({
    method: 'DELETE',
    url: `/transactions/${id}`,
  });
}

// Benchmark
export async function getBenchmark(): Promise<Benchmark | null> {
  return apiRequest<Benchmark | null>({
    method: 'GET',
    url: '/benchmark',
  });
}

export async function setBenchmark(data: {
  ticker: string;
  description?: string;
}): Promise<Benchmark> {
  return apiRequest<Benchmark>({
    method: 'POST',
    url: '/benchmark',
    data,
  });
}

// Price Updates
export async function refreshPrices(): Promise<{ message: string }> {
  return apiRequest<{ message: string }>({
    method: 'POST',
    url: '/prices/refresh',
  });
}

export async function getLastUpdate(): Promise<PriceUpdate> {
  return apiRequest<PriceUpdate>({
    method: 'GET',
    url: '/prices/last-update',
  });
}

// Realtime Prices
export async function getRealtimePrices(symbols: string[]): Promise<RealtimePriceResponse> {
  return apiRequest<RealtimePriceResponse>({
    method: 'GET',
    url: '/prices/realtime',
    params: { symbols: symbols.join(',') },
  });
}

// === Crypto Portfolio APIs ===

// Crypto Portfolio Management
export async function getCryptoPortfolios(): Promise<CryptoPortfolioList> {
  return apiRequest<CryptoPortfolioList>({
    method: 'GET',
    url: '/crypto/portfolios',
  });
}

export async function getCryptoPortfolio(id: number): Promise<CryptoPortfolio> {
  return apiRequest<CryptoPortfolio>({
    method: 'GET',
    url: `/crypto/portfolios/${id}`,
  });
}

export async function createCryptoPortfolio(data: CryptoPortfolioCreate): Promise<CryptoPortfolio> {
  return apiRequest<CryptoPortfolio>({
    method: 'POST',
    url: '/crypto/portfolios',
    data,
  });
}

export async function updateCryptoPortfolio(
  id: number,
  data: CryptoPortfolioUpdate
): Promise<CryptoPortfolio> {
  return apiRequest<CryptoPortfolio>({
    method: 'PUT',
    url: `/crypto/portfolios/${id}`,
    data,
  });
}

export async function deleteCryptoPortfolio(id: number): Promise<void> {
  return apiRequest<void>({
    method: 'DELETE',
    url: `/crypto/portfolios/${id}`,
  });
}

// Crypto Holdings
export async function getCryptoHoldings(portfolioId: number): Promise<CryptoPosition[]> {
  return apiRequest<CryptoPosition[]>({
    method: 'GET',
    url: `/crypto/portfolios/${portfolioId}/holdings`,
  });
}

export async function getCryptoPosition(
  portfolioId: number,
  symbol: string
): Promise<CryptoPosition> {
  return apiRequest<CryptoPosition>({
    method: 'GET',
    url: `/crypto/portfolios/${portfolioId}/holdings/${symbol}`,
  });
}

// Crypto Transactions
export async function getCryptoTransactions(
  portfolioId: number,
  params?: {
    skip?: number;
    limit?: number;
    symbol?: string;
  }
): Promise<PaginatedResponse<CryptoTransaction>> {
  return apiRequest<PaginatedResponse<CryptoTransaction>>({
    method: 'GET',
    url: `/crypto/portfolios/${portfolioId}/transactions`,
    params,
  });
}

export async function createCryptoTransaction(
  portfolioId: number,
  data: CryptoTransactionCreate
): Promise<CryptoTransaction> {
  return apiRequest<CryptoTransaction>({
    method: 'POST',
    url: `/crypto/portfolios/${portfolioId}/transactions`,
    data: normalizeTransactionType(data),
  });
}

export async function updateCryptoTransaction(
  portfolioId: number,
  transactionId: number,
  data: CryptoTransactionUpdate
): Promise<CryptoTransaction> {
  return apiRequest<CryptoTransaction>({
    method: 'PUT',
    url: `/crypto/portfolios/${portfolioId}/transactions/${transactionId}`,
    data: normalizeTransactionType(data),
  });
}

export async function deleteCryptoTransaction(
  portfolioId: number,
  transactionId: number
): Promise<void> {
  return apiRequest<void>({
    method: 'DELETE',
    url: `/crypto/portfolios/${portfolioId}/transactions/${transactionId}`,
  });
}

// Crypto Prices
export async function getCryptoPrices(symbols: string[]): Promise<CryptoPrice[]> {
  return apiRequest<CryptoPrice[]>({
    method: 'GET',
    url: '/crypto/prices',
    params: { symbols: symbols.join(',') },
  });
}

export async function getCryptoPriceHistory(
  symbol: string,
  days: number = 30
): Promise<CryptoPriceHistory[]> {
  return apiRequest<CryptoPriceHistory[]>({
    method: 'GET',
    url: `/crypto/prices/${symbol}/history`,
    params: { days },
  });
}

// Crypto Performance
export async function getCryptoPerformanceData(
  portfolioId: number,
  range: string = '1M'
): Promise<CryptoPerformanceData[]> {
  return apiRequest<CryptoPerformanceData[]>({
    method: 'GET',
    url: `/crypto/portfolios/${portfolioId}/performance`,
    params: { range },
  });
}

export async function getCryptoPortfolioMetrics(
  portfolioId: number
): Promise<CryptoPortfolioMetrics> {
  return apiRequest<CryptoPortfolioMetrics>({
    method: 'GET',
    url: `/crypto/portfolios/${portfolioId}/metrics`,
  });
}

// Crypto Search
export async function searchCryptoAssets(query: string): Promise<any[]> {
  return apiRequest<any[]>({
    method: 'GET',
    url: '/crypto/search',
    params: { q: query },
  });
}

// Asset Search (traditional)
export async function searchTickers(query: string): Promise<TickerSearchResult[]> {
  return apiRequest<TickerSearchResult[]>({
    method: 'GET',
    url: '/assets/search',
    params: { q: query },
  });
}

// Export TickerSearchResult type for use in components
export type { TickerSearchResult } from './types';

// Bulk Operations
export async function importCryptoTransactions(
  portfolioId: number,
  file: File
): Promise<{ message: string; imported: number }> {
  const formData = new FormData();
  formData.append('file', file);

  return apiRequest<{ message: string; imported: number }>({
    method: 'POST',
    url: `/crypto/portfolios/${portfolioId}/import`,
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
}

export async function refreshCryptoPrices(portfolioId?: number): Promise<{ message: string }> {
  const url = portfolioId
    ? `/crypto/portfolios/${portfolioId}/refresh-prices`
    : '/crypto/refresh-prices';

  return apiRequest<{ message: string }>({
    method: 'POST',
    url,
  });
}

// === Blockchain / Wallet APIs ===

// Wallet Sync
export async function syncWallet(portfolioId: number): Promise<{ message: string; status: WalletSyncStatus }> {
  return apiRequest<{ message: string; status: WalletSyncStatus }>({
    method: 'POST',
    url: `/blockchain/sync/wallet`,
    data: { portfolio_id: portfolioId },
  });
}

// Configure wallet address for portfolio
export async function configureWalletAddress(
  portfolioId: number,
  walletAddress: string
): Promise<{ message: string }> {
  return apiRequest<{ message: string }>({
    method: 'POST',
    url: `/blockchain/config/wallet`,
    data: { portfolio_id: portfolioId, wallet_address: walletAddress },
  });
}

// Get wallet transactions preview
export async function getWalletTransactionsPreview(
  walletAddress: string,
  limit?: number
): Promise<WalletTransactionPreview> {
  return apiRequest<WalletTransactionPreview>({
    method: 'GET',
    url: `/blockchain/wallet/${walletAddress}/transactions`,
    params: { limit: limit || 50 },
  });
}

// Get blockchain service status
export async function getBlockchainServiceStatus(): Promise<{
  status: 'active' | 'inactive' | 'error';
  supported_networks: string[];
  rate_limits: object;
  last_update: string;
}> {
  return apiRequest<{
    status: 'active' | 'inactive' | 'error';
    supported_networks: string[];
    rate_limits: object;
    last_update: string;
  }>({
    method: 'GET',
    url: '/blockchain/status',
  });
}

// Get wallet sync status for portfolio
export async function getWalletSyncStatus(portfolioId: number): Promise<WalletSyncStatus> {
  return apiRequest<WalletSyncStatus>({
    method: 'GET',
    url: `/crypto/portfolios/${portfolioId}/wallet-sync-status`,
  });
}