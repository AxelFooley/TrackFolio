import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTransactions, importTransactions, updateTransaction } from '@/lib/api';
import type { TransactionUpdate } from '@/lib/types';

export function useTransactions(skip: number = 0, limit: number = 100) {
  return useQuery({
    queryKey: ['transactions', skip, limit],
    queryFn: () => getTransactions(skip, limit),
    staleTime: 30000, // 30 seconds
  });
}

export function useImportTransactions() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: importTransactions,
    onSuccess: () => {
      // Invalidate all relevant queries
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
}

export function useUpdateTransaction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TransactionUpdate }) =>
      updateTransaction(id, data),
    onSuccess: () => {
      // Invalidate all relevant queries
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
}
