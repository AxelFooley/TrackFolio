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
  NewsArticle,
  NewsResponse,
  NewsFilters,
  NewsFetchResult,
  MoversNewsResponse,
  NewsSummary,
  NewsQualityLevel,
  NewsHealthMetrics,
} from './types';

// API Configuration
// Use the Next.js API route proxy which handles backend URL detection dynamically
const API_BASE_URL = '/api';

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
export function normalizeTransactionType<T extends { transaction_type?: string }>(data: T): T {
  if (data.transaction_type) {
    return {
      ...data,
      transaction_type: data.transaction_type.toLowerCase(),
    };
  }
  return data;
}

/**
 * Transform transaction data from frontend format to backend format.
 * Converts field names and casing to match backend expectations:
 * - transaction_type -> type (and lowercase it)
 * - date -> operation_date
 * - Removes isin, broker, description fields (backend fetches these)
 */
export function transformTransactionForBackend(data: TransactionCreate): any {
  const { transaction_type, date, isin, broker, description, ...rest } = data;

  return {
    type: transaction_type?.toLowerCase() || 'buy',
    operation_date: date,
    // Don't include isin, broker, description - backend fetches these from Yahoo Finance
    ...rest,
  };
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
  const response = await apiRequest<{
    portfolio_data: Array<{ date: string; value: string | number }>;
    benchmark_data: Array<{ date: string; value: string | number }>;
  }>({
    method: 'GET',
    url: '/portfolio/performance',
    params: { range },
  });

  // Transform backend response to frontend format
  // Convert portfolio_data.value to portfolio, merge benchmark data by date
  // Convert string values (Decimal) to numbers for Recharts
  const benchmarkMap = new Map(
    response.benchmark_data.map((b) => [b.date, parseFloat(String(b.value))])
  );

  return response.portfolio_data.map((point) => ({
    date: point.date,
    portfolio: parseFloat(String(point.value)), // Convert string to number for chart
    ...(benchmarkMap.has(point.date) && { benchmark: benchmarkMap.get(point.date) }),
  }));
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
  const response = await apiRequest<Array<{ date: string; value: string | number }>>({
    method: 'GET',
    url: `/assets/${ticker}/prices`,
    params: { range },
  });

  // Transform to PerformanceData format and convert string values to numbers
  return response.map((point) => ({
    date: point.date,
    portfolio: parseFloat(String(point.value)),
  }));
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
    url: '/transactions/',
    data: transformTransactionForBackend(data),
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


export async function getPriceHistory(ticker: string, days: number): Promise<{ data: PerformanceData[] }> {
  return apiRequest<{ data: PerformanceData[] }>({
    method: 'GET',
    url: `/assets/${ticker}/price-history`,
    params: { days },
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
export async function syncWallet(portfolioId: number, walletAddress: string): Promise<{ message: string; status: WalletSyncStatus }> {
  return apiRequest<{ message: string; status: WalletSyncStatus }>({
    method: 'POST',
    url: `/blockchain/sync/wallet`,
    data: {
      portfolio_id: portfolioId,
      wallet_address: walletAddress,
    },
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

// === News APIs ===

// Get news articles with filters
export async function getNews(filters: NewsFilters = {}): Promise<NewsResponse> {
  const {
    query,
    sources,
    tickers,
    sentiment,
    date_from,
    date_to,
    categories,
    language,
    limit = 20,
    page = 1,
  } = filters;

  // If no specific filters are provided, use the movers endpoint for dashboard news
  if (!query && !sources && !tickers && !sentiment && !date_from && !date_to && !categories) {
    const moversResponse = await apiRequest<any>({
      method: 'GET',
      url: '/news/movers',
      params: {
        limit,
        min_change_percent: 2.0, // Default minimum change percentage
        quality: 'medium'
      },
    });

    // Transform movers response to match NewsResponse format
    const allArticles = [];
    for (const mover of moversResponse.movers || []) {
      if (mover.data && mover.data.articles) {
        // Transform articles from each mover's data
        for (const article of mover.data.articles) {
          allArticles.push({
            id: article.title || `news-${Date.now()}`,
            title: article.title || 'Untitled Article',
            summary: article.summary || 'No summary available',
            content: article.summary || 'No content available',
            url: article.url || '#',
            source: article.source || article.source_name || 'Unknown',
            publish_date: article.time_published || new Date().toISOString(),
            sentiment: article.overall_sentiment_label || 'neutral',
            sentiment_score: parseFloat(article.overall_sentiment_score || '0.5'),
            relevance_score: article.relevance_score || 0.5,
            tickers: (article.ticker_sentiment || []).map((ts: any) => ts.ticker).filter(Boolean),
            categories: (article.topics || []).map((t: any) => t.topic || 'finance').filter(Boolean),
            language: language || 'en'
          });
        }
      }
    }

    return {
      articles: allArticles,
      total: allArticles.length,
      page: 1,
      per_page: limit,
      has_next: allArticles.length >= limit,
      has_prev: false
    };
  }

  // For specific filters, try to use available endpoints
  const params: any = {
    limit,
    page,
  };

  if (query) params.query = query;
  if (sources && sources.length > 0) params.sources = sources.join(',');
  if (tickers && tickers.length > 0) params.tickers = tickers.join(',');
  if (sentiment) params.sentiment = sentiment;
  if (date_from) params.date_from = date_from;
  if (date_to) params.date_to = date_to;
  if (categories && categories.length > 0) params.categories = categories.join(',');
  if (language) params.language = language;

  // For now, fallback to movers endpoint for general news until proper general news endpoint is available
  const moversResponse = await apiRequest<any>({
    method: 'GET',
    url: '/news/movers',
    params: {
      limit: params.limit,
      min_change_percent: 2.0,
      quality: 'high'
    },
  });

  // Transform movers response to match NewsResponse format (same logic as above)
    const allArticles = [];
    for (const mover of moversResponse.movers || []) {
      if (mover.data && mover.data.articles) {
        // Transform articles from each mover's data
        for (const article of mover.data.articles) {
          allArticles.push({
            id: article.title || `news-${Date.now()}`,
            title: article.title || 'Untitled Article',
            summary: article.summary || 'No summary available',
            content: article.summary || 'No content available',
            url: article.url || '#',
            source: article.source || article.source_name || 'Unknown',
            publish_date: article.time_published || new Date().toISOString(),
            sentiment: article.overall_sentiment_label || 'neutral',
            sentiment_score: parseFloat(article.overall_sentiment_score || '0.5'),
            relevance_score: article.relevance_score || 0.5,
            tickers: (article.ticker_sentiment || []).map((ts: any) => ts.ticker).filter(Boolean),
            categories: (article.topics || []).map((t: any) => t.topic || 'finance').filter(Boolean),
            language: language || 'en'
          });
        }
      }
    }

    return {
      articles: allArticles,
      total: allArticles.length,
      page: 1,
      per_page: limit,
      has_next: allArticles.length >= limit,
      has_prev: false
    };
}

// Get news article by ID
export async function getNewsArticle(id: string): Promise<NewsArticle> {
  return apiRequest<NewsArticle>({
    method: 'GET',
    url: `/news/${id}`,
  });
}

// Get news by specific ticker/symbol
export async function getNewsByTicker(ticker: string, limit: number = 10): Promise<NewsArticle[]> {
  const response = await apiRequest<any>({
    method: 'GET',
    url: `/news/${ticker}`,
    params: {
      limit,
    },
  });

  // Transform the response to match NewsArticle array format
  if (response.articles) {
    return response.articles;
  }

  // If the response is a single article, wrap it in an array
  if (response.title && response.summary) {
    return [{
      id: response.ticker || `news-${Date.now()}`,
      title: response.title,
      summary: response.summary,
      content: response.summary || response.content || '', // Add missing content property
      url: response.url || '#',
      source: response.source || 'Unknown',
      publish_date: response.publish_date || new Date().toISOString(),
      sentiment: response.sentiment || 'neutral',
      sentiment_score: response.sentiment_score || 0.5,
      relevance_score: response.relevance_score || 0.5,
      tickers: [ticker],
      categories: ['finance'],
      language: 'en'
    }];
  }

  return [];
}

// Get news by sentiment type
export async function getNewsBySentiment(
  sentiment: 'positive' | 'negative' | 'neutral',
  limit: number = 20
): Promise<NewsArticle[]> {
  // For sentiment-based news, we'll use the movers endpoint as a fallback
  // since there's no dedicated sentiment endpoint in the current backend
  const response = await apiRequest<any>({
    method: 'GET',
    url: '/news/movers',
    params: {
      limit,
      min_change_percent: 2.0,
      quality: 'high'
    },
  });

  // Filter articles by sentiment if available
  const articles = response.movers?.map((mover: any) => ({
    id: mover.ticker || `news-${Date.now()}`,
    title: `${mover.ticker || 'Unknown'} - ${mover.title || mover.summary || 'Latest news'}`,
    summary: mover.summary || mover.description || 'No summary available',
    url: mover.url || '#',
    source: mover.source || 'Unknown',
    publish_date: mover.publish_date || new Date().toISOString(),
    sentiment: mover.sentiment || sentiment,
    sentiment_score: mover.sentiment_score || 0.5,
    relevance_score: mover.relevance_score || 0.5,
    tickers: [mover.ticker].filter(Boolean),
    categories: ['finance'],
    language: 'en',
    content: mover.summary || mover.description || 'No content available'
  })) || [];

  // If no real articles are found, provide some demo content
  if (articles.length === 0 || (articles.length > 0 && articles[0].summary === 'No summary available')) {
    const demoArticles: NewsArticle[] = [
      {
        id: 'demo-1',
        title: 'Market Update: Tech Stocks Show Strong Performance',
        summary: 'Technology stocks continue to lead market gains as investors show confidence in innovative companies.',
        url: '#',
        source: 'Financial News Demo',
        publish_date: new Date().toISOString(),
        sentiment: 'positive',
        sentiment_score: 0.7,
        relevance_score: 0.8,
        tickers: ['TECH'],
        categories: ['finance'],
        language: 'en',
        content: 'Technology stocks continue to lead market gains as investors show confidence in innovative companies driving digital transformation across various industries.'
      },
      {
        id: 'demo-2',
        title: 'Global Markets React to Economic Data',
        summary: 'Markets are responding to the latest employment figures and inflation indicators.',
        url: '#',
        source: 'Market Analysis Demo',
        publish_date: new Date(Date.now() - 3600000).toISOString(),
        sentiment: 'neutral',
        sentiment_score: 0.5,
        relevance_score: 0.7,
        tickers: ['GLOBAL'],
        categories: ['finance'],
        language: 'en',
        content: 'Markets are responding to the latest employment figures and inflation indicators, with investors analyzing the potential impact on monetary policy decisions.'
      },
      {
        id: 'demo-3',
        title: 'Energy Sector Sees Volatility',
        summary: 'Energy companies face challenges amid fluctuating commodity prices and regulatory changes.',
        url: '#',
        source: 'Sector News Demo',
        publish_date: new Date(Date.now() - 7200000).toISOString(),
        sentiment: 'negative',
        sentiment_score: 0.3,
        relevance_score: 0.6,
        tickers: ['ENERGY'],
        categories: ['finance'],
        language: 'en',
        content: 'Energy companies face challenges amid fluctuating commodity prices and regulatory changes, creating uncertainty for investors in the sector.'
      }
    ];
    return demoArticles.slice(0, limit);
  }

  // Filter by sentiment if the sentiment information is available
  return articles.filter((article: NewsArticle) =>
    !article.sentiment || article.sentiment === sentiment
  );
}

// Search news articles
export async function searchNews(query: string, limit: number = 20): Promise<NewsArticle[]> {
  // For search functionality, we'll use the movers endpoint as a fallback
  // since there's no dedicated search endpoint in the current backend
  const response = await apiRequest<any>({
    method: 'GET',
    url: '/news/movers',
    params: {
      limit,
      min_change_percent: 2.0,
      quality: 'high'
    },
  });

  // Filter articles by query if possible
  const articles = response.movers?.map((mover: any) => ({
    id: mover.ticker || `news-${Date.now()}`,
    title: `${mover.ticker || 'Unknown'} - ${mover.title || mover.summary || 'Latest news'}`,
    summary: mover.summary || mover.description || 'No summary available',
    url: mover.url || '#',
    source: mover.source || 'Unknown',
    publish_date: mover.publish_date || new Date().toISOString(),
    sentiment: mover.sentiment || 'neutral',
    sentiment_score: mover.sentiment_score || 0.5,
    relevance_score: mover.relevance_score || 0.5,
    tickers: [mover.ticker].filter(Boolean),
    categories: ['finance'],
    language: 'en'
  })) || [];

  // Simple text search in title and summary
  if (query) {
    const queryLower = query.toLowerCase();
    return articles.filter((article: NewsArticle) =>
      article.title.toLowerCase().includes(queryLower) ||
      article.summary.toLowerCase().includes(queryLower)
    );
  }

  return articles;
}

// === Alpha Vantage News APIs ===

// Get news for top movers in the portfolio
export async function getMoversNews(
  limit: number = 10,
  minChangePercent: number = 2.0,
  quality: NewsQualityLevel = 'high'
): Promise<MoversNewsResponse> {
  return apiRequest<MoversNewsResponse>({
    method: 'GET',
    url: '/news/movers',
    params: {
      limit,
      min_change_percent: minChangePercent,
      quality,
    },
  });
}

// Get news for a specific ticker
export async function getTickerNews(
  ticker: string,
  limit: number = 50,
  quality: NewsQualityLevel = 'high'
): Promise<NewsFetchResult> {
  return apiRequest<NewsFetchResult>({
    method: 'GET',
    url: `/news/${ticker}`,
    params: {
      limit,
      quality,
    },
  });
}

// Get sentiment analysis for a specific ticker
export async function getTickerSentiment(
  ticker: string,
  days: number = 7,
  confidenceThreshold: number = 0.7
): Promise<{
  data: NewsSummary;
  high_confidence_articles: number;
  confidence_threshold: number;
  analysis_parameters: {
    ticker: string;
    days_analyzed: number;
    confidence_threshold: number;
    analysis_timestamp: string;
  };
}> {
  return apiRequest<{
    data: NewsSummary;
    high_confidence_articles: number;
    confidence_threshold: number;
    analysis_parameters: {
      ticker: string;
      days_analyzed: number;
      confidence_threshold: number;
      analysis_timestamp: string;
    };
  }>({
    method: 'GET',
    url: `/news/sentiment/${ticker}`,
    params: {
      days,
      confidence_threshold: confidenceThreshold,
    },
  });
}

// Refresh news data (clear cache and refetch)
export async function refreshNews(
  tickers?: string[],
  quality: NewsQualityLevel = 'high',
  forceRefresh: boolean = false
): Promise<{
  operation: 'refresh_specific' | 'cache_clear_specific' | 'cache_clear_all';
  tickers?: string[];
  cache_cleared: number;
  refresh_results?: {
    total_tickers: number;
    successful_tickers: number;
    failed_tickers: string[];
    total_api_calls: number;
    total_articles: number;
  };
  force_refresh: boolean;
}> {
  return apiRequest<{
    operation: 'refresh_specific' | 'cache_clear_specific' | 'cache_clear_all';
    tickers?: string[];
    cache_cleared: number;
    refresh_results?: {
      total_tickers: number;
      successful_tickers: number;
      failed_tickers: string[];
      total_api_calls: number;
      total_articles: number;
    };
    force_refresh: boolean;
  }>({
    method: 'POST',
    url: '/news/refresh',
    params: {
      tickers: tickers?.join(','),
      quality,
      force_refresh: forceRefresh,
    },
  });
}

// Get news fetcher health status
export async function getNewsHealthStatus(): Promise<NewsHealthMetrics> {
  return apiRequest<NewsHealthMetrics>({
    method: 'GET',
    url: '/news/health',
  });
}

// Clear news cache for specific ticker or all
export async function clearNewsCache(
  ticker?: string
): Promise<{
  cache_keys_cleared: number;
  operation: 'specific' | 'all';
  ticker?: string;
}> {
  return apiRequest<{
    cache_keys_cleared: number;
    operation: 'specific' | 'all';
    ticker?: string;
  }>({
    method: 'DELETE',
    url: '/news/cache',
    params: {
      ticker,
    },
  });
}

// Get available quality levels
export async function getNewsQualityLevels(): Promise<{
  high: {
    description: string;
    relevance_threshold: number;
    exclude_neutral: boolean;
    use_case: string;
  };
  medium: {
    description: string;
    relevance_threshold: number;
    exclude_neutral: boolean;
    use_case: string;
  };
  low: {
    description: string;
    relevance_threshold: number;
    exclude_neutral: boolean;
    use_case: string;
  };
  recent: {
    description: string;
    relevance_threshold: number;
    exclude_neutral: boolean;
    use_case: string;
  };
  popular: {
    description: string;
    relevance_threshold: number;
    exclude_neutral: boolean;
    use_case: string;
  };
}> {
  return apiRequest<{
    high: {
      description: string;
      relevance_threshold: number;
      exclude_neutral: boolean;
      use_case: string;
    };
    medium: {
      description: string;
      relevance_threshold: number;
      exclude_neutral: boolean;
      use_case: string;
    };
    low: {
      description: string;
      relevance_threshold: number;
      exclude_neutral: boolean;
      use_case: string;
    };
    recent: {
      description: string;
      relevance_threshold: number;
      exclude_neutral: boolean;
      use_case: string;
    };
    popular: {
      description: string;
      relevance_threshold: number;
      exclude_neutral: boolean;
      use_case: string;
    };
  }>({
    method: 'GET',
    url: '/news/quality-levels',
  });
}

// Get supported news sources
export async function getSupportedNewsSources(): Promise<{
  high_reliability: Array<{
    name: string;
    reliability: number;
    description: string;
  }>;
  medium_reliability: Array<{
    name: string;
    reliability: number;
    description: string;
  }>;
}> {
  return apiRequest<{
    high_reliability: Array<{
      name: string;
      reliability: number;
      description: string;
    }>;
    medium_reliability: Array<{
      name: string;
      reliability: number;
      description: string;
    }>;
  }>({
    method: 'GET',
    url: '/news/supported-sources',
  });
}