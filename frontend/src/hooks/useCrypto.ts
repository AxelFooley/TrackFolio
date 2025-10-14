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

/**
 * Fetches the list of crypto portfolios.
 *
 * @returns The query result whose `data` is an array of crypto portfolio objects; `data` will be an empty array if no portfolios exist.
 */
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

/**
 * Fetches the crypto portfolio for the specified portfolio id.
 *
 * @param id - The numeric identifier of the crypto portfolio to fetch; the query is enabled only when `id` is truthy
 * @returns The query result containing the portfolio data for the given `id`
 */
export function useCryptoPortfolio(id: number) {
  return useQuery({
    queryKey: ['crypto', 'portfolios', id],
    queryFn: () => getCryptoPortfolio(id),
    staleTime: 30000, // 30 seconds
    enabled: !!id,
  });
}

/**
 * Provides a React Query mutation hook for creating a crypto portfolio.
 *
 * The mutation calls the `createCryptoPortfolio` API and, on success, invalidates the cached portfolios list.
 *
 * @returns A mutation result that executes the createCryptoPortfolio API and invalidates the `['crypto','portfolios']` query on success.
 */
export function useCreateCryptoPortfolio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createCryptoPortfolio,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios'] });
    },
  });
}

/**
 * Provides a mutation for updating an existing crypto portfolio and keeping related caches in sync.
 *
 * The mutation accepts an object with `id` and `data`; on success it invalidates the portfolios list and the specific portfolio's cache to refresh stale data.
 *
 * @returns The mutation result object with `mutate` / `mutateAsync` functions that accept `{ id, data }` to perform the update and status fields to observe progress and outcome.
 */
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

/**
 * Provides a React Query mutation for deleting a crypto portfolio.
 *
 * The mutation calls the delete operation and, on success, invalidates the ['crypto', 'portfolios'] query to refresh the portfolio list.
 *
 * @returns The React Query mutation object for performing the delete operation; when successful it invalidates the `['crypto', 'portfolios']` cache entry.
 */
export function useDeleteCryptoPortfolio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteCryptoPortfolio,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios'] });
    },
  });
}

/**
 * Fetches holdings for a crypto portfolio.
 *
 * @param portfolioId - The ID of the portfolio whose holdings to fetch
 * @returns The query result containing the portfolio's holdings array
 */
export function useCryptoHoldings(portfolioId: number) {
  return useQuery({
    queryKey: ['crypto', 'portfolios', portfolioId, 'holdings'],
    queryFn: () => getCryptoHoldings(portfolioId),
    staleTime: 30000, // 30 seconds
    enabled: !!portfolioId,
  });
}

/**
 * Provides a React Query for a crypto position within a portfolio identified by symbol.
 *
 * @returns A query result whose `data` is the position for `symbol` in the specified portfolio, or `undefined` if not available.
 */
export function useCryptoPosition(portfolioId: number, symbol: string) {
  return useQuery({
    queryKey: ['crypto', 'portfolios', portfolioId, 'holdings', symbol],
    queryFn: () => getCryptoPosition(portfolioId, symbol),
    staleTime: 30000, // 30 seconds
    enabled: !!portfolioId && !!symbol,
  });
}

/**
 * Fetches transactions for a crypto portfolio with optional pagination and symbol filtering.
 *
 * @param portfolioId - The ID of the portfolio to load transactions for.
 * @param params - Optional query parameters.
 * @param params.skip - Number of transactions to skip (offset).
 * @param params.limit - Maximum number of transactions to return.
 * @param params.symbol - If provided, filters transactions to the given asset symbol.
 * @returns The query result containing the fetched transactions and related query state.
 */
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

/**
 * Create a crypto transaction for a portfolio and refresh related cached data.
 *
 * The mutation accepts an object with `portfolioId` and `data` and, on success,
 * invalidates the portfolio, holdings, transactions, and metrics query caches
 * for the affected portfolio.
 *
 * @returns A React Query mutation object configured to create a crypto transaction and invalidate related caches on success.
 */
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

/**
 * Provides a mutation hook to update a crypto transaction and refresh related caches.
 *
 * The returned mutation expects an object with `portfolioId`, `transactionId`, and `data`
 * (a `CryptoTransactionUpdate`) and, on success, invalidates queries for the portfolio,
 * its holdings, transactions list, and portfolio metrics so related UI stays in sync.
 *
 * @returns A React Query mutation object whose `mutate` / `mutateAsync` functions accept:
 * - `portfolioId` — the id of the portfolio containing the transaction
 * - `transactionId` — the id of the transaction to update
 * - `data` — the update payload (`CryptoTransactionUpdate`)
 */
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

/**
 * Provides a mutation hook to delete a crypto transaction and invalidate related portfolio caches.
 *
 * @returns A mutation hook that accepts `{ portfolioId, transactionId }` to delete the transaction; on success it invalidates the portfolio, holdings, transactions, and metrics queries for that portfolio.
 */
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

/**
 * Fetches current market prices for the given crypto symbols.
 *
 * @param symbols - Array of asset symbols to fetch prices for
 * @returns The current prices for the provided symbols
 */
export function useCryptoPrices(symbols: string[]) {
  return useQuery({
    queryKey: ['crypto', 'prices', symbols.join(',')],
    queryFn: () => getCryptoPrices(symbols),
    staleTime: 60000, // 1 minute
    enabled: symbols.length > 0,
  });
}

/**
 * Provides a React Query hook that fetches historical price data for a crypto symbol over a given number of days.
 *
 * @param symbol - The crypto asset symbol to fetch history for (e.g., `"BTC"`). The query is disabled when this is falsy.
 * @param days - Number of days of history to retrieve; defaults to `30`.
 * @returns The React Query result containing the requested price history data for the symbol.
 */
export function useCryptoPriceHistory(symbol: string, days: number = 30) {
  return useQuery({
    queryKey: ['crypto', 'prices', symbol, 'history', days],
    queryFn: () => getCryptoPriceHistory(symbol, days),
    staleTime: 60000, // 1 minute
    enabled: !!symbol,
  });
}

/**
 * Fetches crypto performance data for a portfolio over the specified range.
 *
 * @param portfolioId - The numeric identifier of the portfolio
 * @param range - Time range for performance data (e.g., '1M', '3M', '1Y')
 * @returns The portfolio's crypto performance data for the specified range
 */
export function useCryptoPerformanceData(portfolioId: number, range: string = '1M') {
  return useQuery({
    queryKey: ['crypto', 'portfolios', portfolioId, 'performance', range],
    queryFn: () => getCryptoPerformanceData(portfolioId, range),
    staleTime: 30000, // 30 seconds
    enabled: !!portfolioId,
  });
}

/**
 * Fetches metrics for a crypto portfolio identified by portfolioId.
 *
 * @param portfolioId - The ID of the crypto portfolio to fetch metrics for; the query is disabled if this value is falsy.
 * @returns The React Query result containing the portfolio metrics data.
 */
export function useCryptoPortfolioMetrics(portfolioId: number) {
  return useQuery({
    queryKey: ['crypto', 'portfolios', portfolioId, 'metrics'],
    queryFn: () => getCryptoPortfolioMetrics(portfolioId),
    staleTime: 30000, // 30 seconds
    enabled: !!portfolioId,
  });
}

/**
 * Fetches crypto assets matching a search query.
 *
 * @param query - The search string used to find assets; the query is only enabled when its length is at least 2.
 * @param enabled - When true, allows the search query to run; when false the query remains disabled regardless of `query`.
 * @returns A React Query result whose `data` is an array of matching crypto assets.
 */
export function useCryptoAssetsSearch(query: string, enabled: boolean = false) {
  return useQuery({
    queryKey: ['crypto', 'search', query],
    queryFn: () => searchCryptoAssets(query),
    staleTime: 60000, // 1 minute
    enabled: enabled && query.length >= 2,
  });
}

/**
 * Provides a mutation hook to import multiple crypto transactions into a portfolio from a file.
 *
 * The mutation calls the API to import transactions for a given `portfolioId` and `file`, and on success invalidates cached queries for the portfolio, its holdings, transactions, and metrics so related UI updates.
 *
 * @returns A React Query mutation object configured to import crypto transactions for a portfolio.
 */
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

/**
 * Provides a mutation to refresh crypto prices and update related caches.
 *
 * When executed with a `portfolioId`, refreshes prices for that portfolio and invalidates that portfolio's queries (portfolio, holdings, metrics). When executed without an argument, refreshes global crypto prices and invalidates all crypto price queries.
 *
 * @returns A mutation object that accepts an optional `portfolioId` (number) to trigger the refresh and performs appropriate cache invalidation on success.
 */
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

/**
 * Fetches the wallet synchronization status for a portfolio.
 *
 * @param portfolioId - The portfolio ID to retrieve wallet sync status for
 * @returns The wallet sync status and associated query metadata
 */
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

/**
 * Provides a React Query mutation hook to trigger wallet synchronization for a portfolio.
 *
 * Optimistically sets the portfolio's wallet-sync-status to `syncing`, snapshots the previous status for rollback on error, and on success replaces the status with the server response and invalidates related portfolio queries (portfolio, holdings, transactions, metrics).
 *
 * @returns A React Query mutation object that accepts `{ portfolioId: number, walletAddress: string }` to start synchronization and manages optimistic updates, rollback on error, and cache invalidation on success.
 */
export function useSyncWallet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ portfolioId, walletAddress }: { portfolioId: number; walletAddress: string }) =>
      syncWallet(portfolioId, walletAddress),
    onMutate: async ({ portfolioId }) => {
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
    onError: (err, { portfolioId }, context) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousStatus) {
        queryClient.setQueryData(['crypto', 'portfolios', portfolioId, 'wallet-sync-status'], context.previousStatus);
      }
    },
    onSuccess: (data, { portfolioId }) => {
      // Update with the full response data from the server
      queryClient.setQueryData(['crypto', 'portfolios', portfolioId, 'wallet-sync-status'], data);

      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'holdings'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'transactions'] });
      queryClient.invalidateQueries({ queryKey: ['crypto', 'portfolios', portfolioId, 'metrics'] });
    },
  });
}

/**
 * Provides a mutation hook to configure a wallet address for a portfolio.
 *
 * @returns A mutation object that accepts `{ portfolioId, walletAddress }` and configures the wallet address for that portfolio. On success, invalidates the portfolio cache, the portfolio's wallet-sync-status cache, and the portfolio list cache.
 */
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

/**
 * Fetches a preview of transactions for a blockchain wallet address.
 *
 * @param walletAddress - The wallet address to fetch transactions for; when empty the query is disabled.
 * @param enabled - When `true`, enables the query (also requires a non-empty `walletAddress`).
 * @returns The query result containing the wallet transactions preview data.
 */
export function useWalletTransactionsPreview(walletAddress: string, enabled: boolean = false) {
  return useQuery({
    queryKey: ['blockchain', 'wallet', walletAddress, 'transactions-preview'],
    queryFn: () => getWalletTransactionsPreview(walletAddress),
    staleTime: 300000, // 5 minutes
    enabled: enabled && !!walletAddress,
  });
}

/**
 * Fetches the overall blockchain service status and refreshes it every five minutes.
 *
 * @returns An object containing the current blockchain service status in `data` along with React Query metadata such as `status`, `error`, `isFetching`, and other query fields.
 */
export function useBlockchainServiceStatus() {
  return useQuery({
    queryKey: ['blockchain', 'service-status'],
    queryFn: getBlockchainServiceStatus,
    staleTime: 300000, // 5 minutes
    refetchInterval: 300000, // Refetch every 5 minutes
  });
}