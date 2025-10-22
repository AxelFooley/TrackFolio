import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import {
  getMoversNews,
  getTickerNews,
  getTickerSentiment,
  getNewsHealthStatus,
  refreshNews,
  clearNewsCache,
  getNewsQualityLevels,
  getSupportedNewsSources,
} from '@/lib/api';
import type {
  NewsFetchResult,
  MoversNewsResponse,
  NewsSummary,
  NewsHealthMetrics,
  NewsQualityLevel,
} from '@/lib/types/news';

// Cache keys for consistent query management
const NEWS_QUERY_KEYS = {
  all: ['alpha-vantage-news'] as const,
  movers: () => [...NEWS_QUERY_KEYS.all, 'movers'] as const,
  moversWithParams: (limit: number, minChangePercent: number, quality: NewsQualityLevel) =>
    [...NEWS_QUERY_KEYS.movers(), { limit, minChangePercent, quality }] as const,
  ticker: (ticker: string) => [...NEWS_QUERY_KEYS.all, 'ticker', ticker] as const,
  tickerWithParams: (ticker: string, limit: number, quality: NewsQualityLevel) =>
    [...NEWS_QUERY_KEYS.ticker(ticker), { limit, quality }] as const,
  sentiment: (ticker: string) => [...NEWS_QUERY_KEYS.all, 'sentiment', ticker] as const,
  sentimentWithParams: (ticker: string, days: number, confidenceThreshold: number) =>
    [...NEWS_QUERY_KEYS.sentiment(ticker), { days, confidenceThreshold }] as const,
  health: () => [...NEWS_QUERY_KEYS.all, 'health'] as const,
  qualityLevels: () => [...NEWS_QUERY_KEYS.all, 'quality-levels'] as const,
  supportedSources: () => [...NEWS_QUERY_KEYS.all, 'supported-sources'] as const,
};

/**
 * Custom React hook for fetching news data with caching and error handling.
 * Follows the existing patterns in the codebase like usePortfolio and useRealtimePrices.
 */
export function useMoversNews({
  limit = 10,
  minChangePercent = 2.0,
  quality = 'high' as NewsQualityLevel,
  staleTime = 300000, // 5 minutes
  enabled = true,
  retry = 2,
} = {}) {
  return useQuery<MoversNewsResponse, Error>({
    queryKey: NEWS_QUERY_KEYS.moversWithParams(limit, minChangePercent, quality),
    queryFn: () => getMoversNews(limit, minChangePercent, quality),
    staleTime,
    enabled,
    retry,
    refetchOnWindowFocus: false, // Don't refocus on window focus for news (less critical data)
    select: (data) => {
      // Transform data if needed for UI consumption
      return {
        ...data,
        // Add any UI-specific transformations here
      };
    },
  });
}

/**
 * Custom hook for fetching news for a specific ticker symbol.
 * Optimized for individual ticker news consumption with proper caching.
 */
export function useTickerNews(
  ticker: string,
  options: {
    limit?: number;
    quality?: NewsQualityLevel;
    staleTime?: number;
    enabled?: boolean;
    retry?: number;
  } = {}
) {
  const { limit = 50, quality = 'high' as NewsQualityLevel, staleTime = 600000, enabled = true, retry = 2 } = options;

  return useQuery<NewsFetchResult, Error>({
    queryKey: NEWS_QUERY_KEYS.tickerWithParams(ticker, limit, quality),
    queryFn: () => getTickerNews(ticker, limit, quality),
    staleTime,
    enabled: enabled && !!ticker,
    retry,
    refetchOnWindowFocus: false,
    select: (data) => {
      // Transform data for better UI consumption
      return {
        ...data,
        // Add any UI-specific transformations here
        articles: data.articles.map(article => ({
          ...article,
          // Add any additional UI fields
        })),
      };
    },
  });
}

/**
 * Custom hook for fetching sentiment analysis for a specific ticker.
 * Provides comprehensive sentiment data with confidence scoring.
 */
export function useTickerSentiment(
  ticker: string,
  options: {
    days?: number;
    confidenceThreshold?: number;
    staleTime?: number;
    enabled?: boolean;
    retry?: number;
  } = {}
) {
  const { days = 7, confidenceThreshold = 0.7, staleTime = 1800000, enabled = true, retry = 2 } = options; // 30 minutes stale time

  return useQuery<{
    data: NewsSummary;
    high_confidence_articles: number;
    confidence_threshold: number;
    analysis_parameters: {
      ticker: string;
      days_analyzed: number;
      confidence_threshold: number;
      analysis_timestamp: string;
    };
  }, Error>({
    queryKey: NEWS_QUERY_KEYS.sentimentWithParams(ticker, days, confidenceThreshold),
    queryFn: () => getTickerSentiment(ticker, days, confidenceThreshold),
    staleTime,
    enabled: enabled && !!ticker,
    retry,
    refetchOnWindowFocus: false,
    select: (data) => {
      // Transform data for better UI consumption
      return {
        ...data,
        // Add any UI-specific transformations
      };
    },
  });
}

/**
 * Hook for getting news fetcher health status.
 * Useful for monitoring service health and debugging.
 */
export function useNewsHealthStatus({
  staleTime = 600000, // 10 minutes
  enabled = true,
  retry = 1,
} = {}) {
  return useQuery<NewsHealthMetrics, Error>({
    queryKey: NEWS_QUERY_KEYS.health(),
    queryFn: () => getNewsHealthStatus(),
    staleTime,
    enabled,
    retry,
    refetchOnWindowFocus: false,
  });
}

/**
 * Hook for getting available quality levels configuration.
 * Useful for UI components that need to show quality level options.
 */
export function useNewsQualityLevels({
  staleTime = 86400000, // 24 hours (this is static configuration)
  enabled = true,
  retry = 1,
} = {}) {
  return useQuery<{
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
  }, Error>({
    queryKey: NEWS_QUERY_KEYS.qualityLevels(),
    queryFn: () => getNewsQualityLevels(),
    staleTime,
    enabled,
    retry,
    refetchOnWindowFocus: false,
  });
}

/**
 * Hook for getting supported news sources information.
 * Useful for UI components that need to show source reliability information.
 */
export function useSupportedNewsSources({
  staleTime = 86400000, // 24 hours (static configuration)
  enabled = true,
  retry = 1,
} = {}) {
  return useQuery<{
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
  }, Error>({
    queryKey: NEWS_QUERY_KEYS.supportedSources(),
    queryFn: () => getSupportedNewsSources(),
    staleTime,
    enabled,
    retry,
    refetchOnWindowFocus: false,
  });
}

/**
 * Mutation hook for refreshing news data.
 * Provides cache invalidation and refetch capabilities.
 */
export function useRefreshNews() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: refreshNews,
    onSuccess: (response) => {
      // Invalidate relevant queries based on the operation
      if (response.operation === 'cache_clear_all') {
        // Invalidate all news queries
        queryClient.invalidateQueries({
          predicate: (query) => query.queryKey[0] === 'alpha-vantage-news',
        });
      } else if (response.operation === 'refresh_specific' && response.tickers) {
        // Invalidate specific ticker queries
        response.tickers.forEach(ticker => {
          queryClient.invalidateQueries({
            queryKey: NEWS_QUERY_KEYS.ticker(ticker),
          });
          queryClient.invalidateQueries({
            queryKey: NEWS_QUERY_KEYS.sentiment(ticker),
          });
        });
      } else if (response.operation === 'cache_clear_specific' && response.tickers) {
        // Invalidate specific ticker queries
        response.tickers.forEach(ticker => {
          queryClient.invalidateQueries({
            queryKey: NEWS_QUERY_KEYS.ticker(ticker),
          });
          queryClient.invalidateQueries({
            queryKey: NEWS_QUERY_KEYS.sentiment(ticker),
          });
        });
      }
    },
    onError: (error) => {
      console.error('Failed to refresh news:', error);
    },
  });
}

/**
 * Mutation hook for clearing news cache.
 * Provides cache clearing capabilities for specific tickers or all cache.
 */
export function useClearNewsCache() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: clearNewsCache,
    onSuccess: (response, ticker) => {
      // Invalidate relevant queries based on the operation
      if (ticker) {
        // Clear cache for specific ticker
        queryClient.invalidateQueries({
          queryKey: NEWS_QUERY_KEYS.ticker(ticker),
        });
        queryClient.invalidateQueries({
          queryKey: NEWS_QUERY_KEYS.sentiment(ticker),
        });
      } else {
        // Clear all news cache
        queryClient.invalidateQueries({
          predicate: (query) => query.queryKey[0] === 'alpha-vantage-news',
        });
      }
    },
    onError: (error) => {
      console.error('Failed to clear news cache:', error);
    },
  });
}

/**
 * Combined hook that automatically fetches news for all holdings in the portfolio.
 * Integrates with portfolio data to provide relevant news based on holdings.
 */
export function usePortfolioNewsIntegration({
  limit = 5, // Limit to top holdings to avoid too many API calls
  minChangePercent = 2.0,
  quality = 'high' as NewsQualityLevel,
  enabled = true,
  retry = 2,
} = {}) {
  // We would typically use the portfolio data here, but since this hook is focused
  // on news data and follows existing patterns, we keep it focused on news APIs.
  // Portfolio integration would happen at the component level.

  return useQuery<MoversNewsResponse, Error>({
    queryKey: NEWS_QUERY_KEYS.moversWithParams(limit, minChangePercent, quality),
    queryFn: () => getMoversNews(limit, minChangePercent, quality),
    staleTime: 300000, // 5 minutes
    enabled,
    retry,
    refetchOnWindowFocus: false,
  });
}

// Export utility hooks for component-level portfolio integration
export function useHoldingsNewsIntegration() {
  // This would be implemented with a component that combines this hook
  // with portfolio data to provide holdings-specific news
  // For now, it serves as a placeholder for future enhancement
  return {
    // Implementation would go here
  };
}

// Export type definitions for external use
export type {
  NewsFetchResult,
  MoversNewsResponse,
  NewsSummary,
  NewsHealthMetrics,
  NewsQualityLevel,
};

// Export query keys for manual query management if needed
export { NEWS_QUERY_KEYS };