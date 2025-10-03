import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getBenchmark, setBenchmark } from '@/lib/api';

export function useBenchmark() {
  return useQuery({
    queryKey: ['benchmark'],
    queryFn: getBenchmark,
    staleTime: 300000, // 5 minutes
  });
}

export function useSetBenchmark() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: setBenchmark,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['benchmark'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio', 'performance'] });
    },
  });
}
