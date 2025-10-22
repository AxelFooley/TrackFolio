import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { getNews, getNewsByTicker, getNewsBySentiment, searchNews } from '@/lib/api';
import type { NewsArticle, NewsFilters, NewsResponse } from '@/lib/types';

export function useNews(filters: NewsFilters = {}, enabled: boolean = true) {
  return useQuery({
    queryKey: ['news', filters],
    queryFn: () => getNews(filters),
    enabled: enabled && (!filters.query || Boolean(filters.query?.trim())),
    staleTime: 5 * 60 * 1000, // 5 minutes
    placeholderData: previousData => previousData,
  });
}

export function useNewsByTicker(ticker: string, limit: number = 10, enabled: boolean = true) {
  return useQuery({
    queryKey: ['news', 'ticker', ticker],
    queryFn: () => getNewsByTicker(ticker, limit),
    enabled: enabled && Boolean(ticker?.trim()),
    staleTime: 5 * 60 * 1000, // 5 minutes,
  });
}

export function useNewsBySentiment(sentiment: 'positive' | 'negative' | 'neutral', limit: number = 20, enabled: boolean = true) {
  return useQuery({
    queryKey: ['news', 'sentiment', sentiment],
    queryFn: () => getNewsBySentiment(sentiment, limit),
    enabled: enabled && Boolean(sentiment),
    staleTime: 5 * 60 * 1000, // 5 minutes,
  });
}

export function useNewsSearch(query: string, limit: number = 20, enabled: boolean = true) {
  return useQuery({
    queryKey: ['news', 'search', query],
    queryFn: () => searchNews(query, limit),
    enabled: enabled && Boolean(query?.trim()),
    staleTime: 5 * 60 * 1000, // 5 minutes,
    placeholderData: previousData => previousData,
  });
}

export function useNewsInfinite(filters: NewsFilters = {}, enabled: boolean = true) {
  return useInfiniteQuery({
    queryKey: ['news', 'infinite', filters],
    queryFn: ({ pageParam = 1 }) =>
      getNews({
        ...filters,
        page: pageParam,
        limit: filters.limit || 20,
      }),
    enabled: enabled && (!filters.query || Boolean(filters.query?.trim())),
    staleTime: 5 * 60 * 1000, // 5 minutes
    placeholderData: previousData => previousData,
    initialPageParam: 1,
    getNextPageParam: (lastPage: NewsResponse) => {
      return lastPage.has_next ? lastPage.page + 1 : undefined;
    },
  });
}