import { useQuery } from '@tanstack/react-query';
import { getAssetDetail, getAssetPrices, getAssetTransactions, getPriceHistory } from '@/lib/api';

export function useAssetDetail(ticker: string) {
  return useQuery({
    queryKey: ['asset', ticker, 'detail'],
    queryFn: () => getAssetDetail(ticker),
    staleTime: 60000, // 1 minute
    enabled: !!ticker,
  });
}

export function useAssetPrices(ticker: string, range: string) {
  // Convert range to days
  const getDaysFromRange = (range: string): number => {
    switch (range) {
      case '1D': return 1;
      case '1W': return 7;
      case '1M': return 30;
      case '3M': return 90;
      case '6M': return 180;
      case '1Y': return 365;
      case 'YTD': return Math.floor((new Date().getTime() - new Date(new Date().getFullYear(), 0, 1).getTime()) / (1000 * 60 * 60 * 24)) + 1; // Days since Jan 1st
      case 'ALL': return 365 * 5; // 5 years
      default: return 365;
    }
  };

  const days = getDaysFromRange(range);

  return useQuery({
    queryKey: ['asset', ticker, 'prices', 'optimized', range],
    queryFn: () => getPriceHistory(ticker, days),
    staleTime: 300000, // 5 minutes - historical data doesn't change often
    enabled: !!ticker,
    select: (data) => {
      // Transform the response to match the expected format
      return data.data || [];
    },
  });
}

export function useAssetTransactions(ticker: string) {
  return useQuery({
    queryKey: ['asset', ticker, 'transactions'],
    queryFn: () => getAssetTransactions(ticker),
    staleTime: 60000, // 1 minute
    enabled: !!ticker,
  });
}
