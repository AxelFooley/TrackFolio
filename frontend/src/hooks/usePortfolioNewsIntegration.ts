import { useMemo, useCallback, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useHoldings } from './usePortfolio';
import { useMoversNews, useTickerNews, useRefreshNews } from './useAlphaVantageNews';
import type { NewsFetchResult, MoversNewsResponse, NewsQualityLevel } from '@/lib/types/news';
import type { Position } from '@/lib/types';

/**
 * Enhanced hook for portfolio news integration that automatically:
 * 1. Gets portfolio holdings
 * 2. Fetches news for the top movers
 * 3. Provides smart ticker selection based on holdings changes
 * 4. Integrates with portfolio data for context-aware news filtering
 */
export function usePortfolioNewsIntegration(options: {
  limit?: number;
  minChangePercent?: number;
  quality?: NewsQualityLevel;
  autoRefreshHoldings?: boolean;
  enabled?: boolean;
  retry?: number;
} = {}) {
  const {
    limit = 10,
    minChangePercent = 2.0,
    quality = 'high' as NewsQualityLevel,
    autoRefreshHoldings = true,
    enabled = true,
    retry = 2,
  } = options;

  // Get holdings data
  const holdingsQuery = useHoldings();

  // Get movers news based on holdings
  const moversNewsQuery = useMoversNews({
    limit,
    minChangePercent,
    quality,
    enabled: enabled && holdingsQuery.data && holdingsQuery.data.length > 0,
    retry,
  });

  // Query client for cache management
  const queryClient = useQueryClient();

  // Get news for a specific ticker with portfolio context
  const useTickerNewsWithContext = (ticker: string) => {
    return useTickerNews(ticker, {
      quality,
      retry,
    });
  };

  // Filter holdings to get the most relevant tickers for news fetching
  const getRelevantTickersForNews = useCallback(() => {
    if (!holdingsQuery.data) return [];

    // Sort holdings by various criteria to prioritize news fetching
    return holdingsQuery.data
      .filter(holding => holding.quantity > 0) // Only holdings with positions
      .sort((a, b) => {
        // Priority: holdings with today's change > high value holdings > recent holdings
        const aChange = a.today_change_percent || 0;
        const bChange = b.today_change_percent || 0;
        const aValue = a.current_value || 0;
        const bValue = b.current_value || 0;

        // Primary: Sort by today's change percentage (absolute value)
        if (Math.abs(aChange) !== Math.abs(bChange)) {
          return Math.abs(bChange) - Math.abs(aChange);
        }
        // Secondary: Sort by current value
        if (aValue !== bValue) {
          return bValue - aValue;
        }
        // Tertiary: Sort by unrealized gain/loss
        const aGain = a.unrealized_gain || 0;
        const bGain = b.unrealized_gain || 0;
        return Math.abs(bGain) - Math.abs(aGain);
      })
      .slice(0, limit)
      .map(holding => holding.ticker);
  }, [holdingsQuery.data, limit]);

  // Get top tickers from holdings
  const topHoldingsTickers = useMemo(() => {
    return getRelevantTickersForNews();
  }, [getRelevantTickersForNews]);

  // Get holdings that have significant news coverage
  const holdingsWithNews = useMemo(() => {
    if (!holdingsQuery.data || !moversNewsQuery.data) return [];

    const moversTickers = new Set(
      moversNewsQuery.data.movers
        .filter(mover => mover.success)
        .map(mover => mover.ticker)
    );

    return holdingsQuery.data
      .filter(holding => moversTickers.has(holding.ticker))
      .map(holding => ({
        ...holding,
        hasNews: true,
        newsCount: moversNewsQuery.data.movers.find(m => m.ticker === holding.ticker)?.processed_articles || 0,
      }));
  }, [holdingsQuery.data, moversNewsQuery.data]);

  // Get holdings that don't have news yet
  const holdingsWithoutNews = useMemo(() => {
    if (!holdingsQuery.data || !moversNewsQuery.data) return [];

    const moversTickers = new Set(
      moversNewsQuery.data.movers
        .map(mover => mover.ticker)
    );

    return holdingsQuery.data
      .filter(holding => !moversTickers.has(holding.ticker))
      .map(holding => ({
        ...holding,
        hasNews: false,
        newsCount: 0,
      }));
  }, [holdingsQuery.data, moversNewsQuery.data]);

  // Auto-refresh news when holdings change significantly
  const shouldRefreshNews = useMemo(() => {
    return autoRefreshHoldings && holdingsQuery.data && holdingsQuery.data.length > 0;
  }, [autoRefreshHoldings, holdingsQuery.data]);

  // Refetch news when holdings change
  useEffect(() => {
    if (shouldRefreshNews) {
      moversNewsQuery.refetch();
    }
  }, [shouldRefreshNews, holdingsQuery.data, moversNewsQuery.refetch]);

  // Get the best performing holdings with news
  const bestPerformingHoldings = useMemo(() => {
    if (!holdingsWithNews.length) return [];

    return holdingsWithNews
      .filter(h => (h.today_change_percent || 0) > 0)
      .sort((a, b) => (b.today_change_percent || 0) - (a.today_change_percent || 0))
      .slice(0, 3);
  }, [holdingsWithNews]);

  // Get the worst performing holdings with news
  const worstPerformingHoldings = useMemo(() => {
    if (!holdingsWithNews.length) return [];

    return holdingsWithNews
      .filter(h => (h.today_change_percent || 0) < 0)
      .sort((a, b) => (a.today_change_percent || 0) - (b.today_change_percent || 0))
      .slice(0, 3);
  }, [holdingsWithNews]);

  // Combined mutation for portfolio news refresh
  const refreshPortfolioNews = useRefreshNews();

  // Refresh news for specific holdings
  const refreshHoldingsNews = useCallback(async (tickers?: string[]) => {
    const targetTickers = tickers || topHoldingsTickers;
    if (targetTickers.length === 0) return;

    await refreshPortfolioNews.mutateAsync({
    tickers: targetTickers,
    quality,
    forceRefresh: true
  } as any);
  }, [refreshPortfolioNews, topHoldingsTickers, quality]);

  // Refresh all portfolio news
  const refreshAllPortfolioNews = useCallback(async () => {
    const allHoldingsTickers = holdingsQuery.data?.map(h => h.ticker) || [];
    await refreshHoldingsNews(allHoldingsTickers);
  }, [refreshHoldingsNews, holdingsQuery.data]);

  // Get news summary for the portfolio
  const portfolioNewsSummary = useMemo(() => {
    if (!moversNewsQuery.data) return null;

    const totalArticles = moversNewsQuery.data.total_articles;
    const successfulMovers = moversNewsQuery.data.successful_movers;
    const cacheHitRate = moversNewsQuery.data.cache_hit_rate;
    const averageArticlesPerMover = totalArticles / Math.max(1, moversNewsQuery.data.total_movers);

    return {
      totalArticles,
      successfulMovers,
      totalMovers: moversNewsQuery.data.total_movers,
      cacheHitRate: cacheHitRate * 100,
      averageArticlesPerMover,
      hasCoverage: successfulMovers > 0,
      coveragePercentage: (successfulMovers / Math.max(1, moversNewsQuery.data.total_movers)) * 100,
    };
  }, [moversNewsQuery.data]);

  return {
    // Data
    holdings: holdingsQuery.data || [],
    topHoldingsTickers,
    moversNews: moversNewsQuery.data,
    holdingsWithNews,
    holdingsWithoutNews,
    bestPerformingHoldings,
    worstPerformingHoldings,
    portfolioNewsSummary,

    // Loading and error states
    isLoading: holdingsQuery.isLoading || moversNewsQuery.isLoading,
    isHoldingsLoading: holdingsQuery.isLoading,
    isNewsLoading: moversNewsQuery.isLoading,
    holdingsError: holdingsQuery.error,
    newsError: moversNewsQuery.error,

    // Actions
    refreshHoldingsNews,
    refreshAllPortfolioNews,
    refreshPortfolioNews,

    // Derived state
    hasHoldings: holdingsQuery.data && holdingsQuery.data.length > 0,
    hasNews: holdingsWithNews.length > 0,
    needsMoreNews: holdingsWithoutNews.length > 0,
    portfolioHealth: {
      holdingsCount: holdingsQuery.data?.length || 0,
      newsCoverage: portfolioNewsSummary?.coveragePercentage || 0,
      cacheEfficiency: portfolioNewsSummary?.cacheHitRate || 0,
    },

    // Query instances for direct manipulation
    holdingsQuery,
    moversNewsQuery,
  };
}

/**
 * Hook for getting news specifically for holdings that are performing well.
 * Useful for showing positive news to users.
 */
export function useBestPerformersNews(options: {
  limit?: number;
  quality?: NewsQualityLevel;
} = {}) {
  const portfolioNews = usePortfolioNewsIntegration({
    ...options,
    minChangePercent: 2.0, // Only get news for significant movers
  });

  return {
    ...portfolioNews,
    performersNews: portfolioNews.bestPerformingHoldings,
  };
}

/**
 * Hook for getting news specifically for holdings that are performing poorly.
 * Useful for showing potential risks or opportunities.
 */
export function useUnderperformersNews(options: {
  limit?: number;
  quality?: NewsQualityLevel;
} = {}) {
  const portfolioNews = usePortfolioNewsIntegration({
    ...options,
    minChangePercent: -2.0, // Only get news for significant losers
  });

  return {
    ...portfolioNews,
    underperformersNews: portfolioNews.worstPerformingHoldings,
  };
}

/**
 * Hook for getting holdings that don't have news coverage yet.
 * Useful for identifying tickers that might need additional attention.
 */
export function useHoldingsWithoutNews(options: {
  limit?: number;
  quality?: NewsQualityLevel;
} = {}) {
  const portfolioNews = usePortfolioNewsIntegration(options);

  return {
    ...portfolioNews,
    holdingsWithoutNews: portfolioNews.holdingsWithoutNews,
    needsNewsResearch: portfolioNews.needsMoreNews,
  };
}