import { useQuery } from '@tanstack/react-query';
import { getAssetDetail, getAssetPrices, getAssetTransactions } from '@/lib/api';

export function useAssetDetail(ticker: string) {
  return useQuery({
    queryKey: ['asset', ticker, 'detail'],
    queryFn: () => getAssetDetail(ticker),
    staleTime: 60000, // 1 minute
    enabled: !!ticker,
  });
}

export function useAssetPrices(ticker: string, range: string) {
  return useQuery({
    queryKey: ['asset', ticker, 'prices', range],
    queryFn: () => getAssetPrices(ticker, range),
    staleTime: 60000, // 1 minute
    enabled: !!ticker,
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
