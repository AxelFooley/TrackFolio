import { useQuery } from '@tanstack/react-query';
import { getPortfolioOverview, getHoldings, getPerformanceData } from '@/lib/api';

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
