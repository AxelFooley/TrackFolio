import { useQuery } from '@tanstack/react-query';
import {
  getPortfolioOverview,
  getHoldings,
  getPerformanceData,
  getUnifiedOverview,
  getUnifiedHoldings,
  getUnifiedPerformance,
  getUnifiedMovers,
} from '@/lib/api';

export function usePortfolioOverview() {
  return useQuery({
    queryKey: ['portfolio', 'overview'],
    queryFn: getPortfolioOverview,
    staleTime: 60000, // 1 minute
  });
}

export function useHoldings() {
  return useQuery({
    queryKey: ['portfolio', 'holdings'],
    queryFn: getHoldings,
    staleTime: 60000, // 1 minute
  });
}

export function usePerformanceData(range: string) {
  return useQuery({
    queryKey: ['portfolio', 'performance', range],
    queryFn: () => getPerformanceData(range),
    staleTime: 60000, // 1 minute
  });
}

// === Unified Portfolio Hooks (Traditional + Crypto) ===

export function useUnifiedOverview() {
  return useQuery({
    queryKey: ['portfolio', 'unified-overview'],
    queryFn: getUnifiedOverview,
    staleTime: 60000, // 1 minute
  });
}

export function useUnifiedHoldings(skip?: number, limit?: number) {
  return useQuery({
    queryKey: ['portfolio', 'unified-holdings', skip, limit],
    queryFn: () => getUnifiedHoldings({ skip, limit }),
    staleTime: 60000, // 1 minute
  });
}

export function useUnifiedPerformance(range: string) {
  return useQuery({
    queryKey: ['portfolio', 'unified-performance', range],
    queryFn: () => getUnifiedPerformance(range),
    staleTime: 60000, // 1 minute
  });
}

export function useUnifiedMovers() {
  return useQuery({
    queryKey: ['portfolio', 'unified-movers'],
    queryFn: getUnifiedMovers,
    staleTime: 60000, // 1 minute
  });
}
