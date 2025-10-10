import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getCryptoPortfolios,
  getCryptoPortfolio,
  createCryptoPortfolio,
  updateCryptoPortfolio,
  deleteCryptoPortfolio,
  getCryptoHoldings,
  getCryptoPosition,
  getCryptoTransactions,
  createCryptoTransaction,
  updateCryptoTransaction,
  deleteCryptoTransaction,
  getCryptoPrices,
  getCryptoPriceHistory,
  getCryptoPerformanceData,
  getCryptoPortfolioMetrics,
  searchCryptoAssets,
  importCryptoTransactions,
  refreshCryptoPrices,
  syncWallet,
  configureWalletAddress,
  getWalletTransactionsPreview,
  getBlockchainServiceStatus,
  getWalletSyncStatus,
} from '@/lib/api';
import type {
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
  PaginatedResponse,
  WalletSyncStatus,
  WalletTransactionPreview,
} from '@/lib/types';

// Portfolio Management
export function useCryptoPortfolios() {
  return useQuery({
    queryKey: ['crypto', 'portfolios'],
    queryFn: async () => {
      const result = await getCryptoPortfolios();
      return result.portfolios || [];
    },
    staleTime: 30000, // 30 seconds
  });
}

export function useCryptoPortfolio(id: number) {
  return useQuery({
    queryKey: ['crypto', 'portfolios', id],
    queryFn: () => getCryptoPortfolio(id),
    staleTime: 30000, // 30 seconds
    enabled: !!id,
  });
}

export function useCreateCryptoPortfolio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createCryptoPortfolio,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios'] });
    },
  });
}

export function useUpdateCryptoPortfolio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CryptoPortfolioUpdate }) =>
      updateCryptoPortfolio(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', id] });
    },
  });
}

export function useDeleteCryptoPortfolio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteCryptoPortfolio,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios'] });
    },
  });
}

// Holdings
export function useCryptoHoldings(portfolioId: number) {
  return useQuery({
    queryKey: ['crypto', 'portfolios', portfolioId, 'holdings'],
    queryFn: () => getCryptoHoldings(portfolioId),
    staleTime: 30000, // 30 seconds
    enabled: !!portfolioId,
  });
}

export function useCryptoPosition(portfolioId: number, symbol: string) {
  return useQuery({
    queryKey: ['crypto', 'portfolios', portfolioId, 'holdings', symbol],
    queryFn: () => getCryptoPosition(portfolioId, symbol),
    staleTime: 30000, // 30 seconds
    enabled: !!portfolioId && !!symbol,
  });
}

// Transactions
export function useCryptoTransactions(
  portfolioId: number,
  params?: {
    skip?: number;
    limit?: number;
    symbol?: string;
  }
) {
  return useQuery({
    queryKey: ['crypto', 'portfolios', portfolioId, 'transactions', params],
    queryFn: () => getCryptoTransactions(portfolioId, params),
    staleTime: 30000, // 30 seconds
    enabled: !!portfolioId,
  });
}

export function useCreateCryptoTransaction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ portfolioId, data }: { portfolioId: number; data: CryptoTransactionCreate }) =>
      createCryptoTransaction(portfolioId, data),
    onSuccess: (_, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'holdings'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'transactions'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'metrics'] });
    },
  });
}

export function useUpdateCryptoTransaction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      portfolioId,
      transactionId,
      data,
    }: {
      portfolioId: number;
      transactionId: number;
      data: CryptoTransactionUpdate;
    }) => updateCryptoTransaction(portfolioId, transactionId, data),
    onSuccess: (_, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'holdings'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'transactions'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'metrics'] });
    },
  });
}

export function useDeleteCryptoTransaction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ portfolioId, transactionId }: { portfolioId: number; transactionId: number }) =>
      deleteCryptoTransaction(portfolioId, transactionId),
    onSuccess: (_, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'holdings'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'transactions'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'metrics'] });
    },
  });
}

// Prices
export function useCryptoPrices(symbols: string[]) {
  return useQuery({
    queryKey: ['crypto', 'prices', symbols.join(',')],
    queryFn: () => getCryptoPrices(symbols),
    staleTime: 60000, // 1 minute
    enabled: symbols.length > 0,
  });
}

export function useCryptoPriceHistory(symbol: string, days: number = 30) {
  return useQuery({
    queryKey: ['crypto', 'prices', symbol, 'history', days],
    queryFn: () => getCryptoPriceHistory(symbol, days),
    staleTime: 60000, // 1 minute
    enabled: !!symbol,
  });
}

// Performance
export function useCryptoPerformanceData(portfolioId: number, range: string = '1M') {
  return useQuery({
    queryKey: ['crypto', 'portfolios', portfolioId, 'performance', range],
    queryFn: () => getCryptoPerformanceData(portfolioId, range),
    staleTime: 30000, // 30 seconds
    enabled: !!portfolioId,
  });
}

export function useCryptoPortfolioMetrics(portfolioId: number) {
  return useQuery({
    queryKey: ['crypto', 'portfolios', portfolioId, 'metrics'],
    queryFn: () => getCryptoPortfolioMetrics(portfolioId),
    staleTime: 30000, // 30 seconds
    enabled: !!portfolioId,
  });
}

// Search
export function useCryptoAssetsSearch(query: string, enabled: boolean = false) {
  return useQuery({
    queryKey: ['crypto', 'search', query],
    queryFn: () => searchCryptoAssets(query),
    staleTime: 60000, // 1 minute
    enabled: enabled && query.length >= 2,
  });
}

// Bulk Operations
export function useImportCryptoTransactions() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ portfolioId, file }: { portfolioId: number; file: File }) =>
      importCryptoTransactions(portfolioId, file),
    onSuccess: (_, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'holdings'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'transactions'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'metrics'] });
    },
  });
}

export function useRefreshCryptoPrices() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (portfolioId?: number) => refreshCryptoPrices(portfolioId),
    onSuccess: (_, portfolioId) => {
      if (portfolioId) {
        queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId] });
        queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'holdings'] });
        queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'metrics'] });
      } else {
        // Invalidate all crypto price-related queries
        queryClient.invalidateQueries({ queryKey: ['crypto', 'prices'] });
      }
    },
  });
}

// Wallet Management
export function useWalletSyncStatus(portfolioId: number) {
  const queryKey = ['crypto', 'portfolios', portfolioId, 'wallet-sync-status'];

  return useQuery({
    queryKey,
    queryFn: () => getWalletSyncStatus(portfolioId),
    staleTime: 60000, // 1 minute
    enabled: !!portfolioId,
    refetchInterval: 300000, // Default: 5 minutes
  });
}

export function useSyncWallet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (portfolioId: number) => syncWallet(portfolioId),
    onMutate: async (portfolioId) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'wallet-sync-status'] });

      // Snapshot the previous value
      const previousStatus = queryClient.getQueryData(['crypto', 'portfolios', portfolioId, 'wallet-sync-status']);

      // Optimistically update to syncing status
      queryClient.setQueryData(['crypto', 'portfolios', portfolioId, 'wallet-sync-status'], {
        status: 'syncing',
        last_sync: null,
        transaction_count: null,
        error_message: null,
      });

      return { previousStatus };
    },
    onError: (err, portfolioId, context) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousStatus) {
        queryClient.setQueryData(['crypto', 'portfolios', portfolioId, 'wallet-sync-status'], context.previousStatus);
      }
    },
    onSuccess: (data, portfolioId) => {
      // Update with the new status from the server
      queryClient.setQueryData(['crypto', 'portfolios', portfolioId, 'wallet-sync-status'], data.status);

      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'holdings'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'transactions'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'metrics'] });
    },
  });
}

export function useConfigureWalletAddress() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ portfolioId, walletAddress }: { portfolioId: number; walletAddress: string }) =>
      configureWalletAddress(portfolioId, walletAddress),
    onSuccess: (_, { portfolioId }) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'wallet-sync-status'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios'] }); // Update the portfolio list
    },
  });
}

export function useWalletTransactionsPreview(walletAddress: string, enabled: boolean = false) {
  return useQuery({
    queryKey: ['blockchain', 'wallet', walletAddress, 'transactions-preview'],
    queryFn: () => getWalletTransactionsPreview(walletAddress),
    staleTime: 300000, // 5 minutes
    enabled: enabled && !!walletAddress,
  });
}

export function useBlockchainServiceStatus() {
  return useQuery({
    queryKey: ['blockchain', 'service-status'],
    queryFn: getBlockchainServiceStatus,
    staleTime: 300000, // 5 minutes
    refetchInterval: 300000, // Refetch every 5 minutes
  });
}