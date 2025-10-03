import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getLastUpdate, refreshPrices } from '@/lib/api';

export function useLastUpdate() {
  return useQuery({
    queryKey: ['prices', 'last-update'],
    queryFn: getLastUpdate,
    staleTime: 30000, // 30 seconds
  });
}

export function useRefreshPrices() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: refreshPrices,
    onSuccess: () => {
      // Invalidate all data that depends on prices
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['asset'] });
      queryClient.invalidateQueries({ queryKey: ['prices'] });
    },
  });
}
