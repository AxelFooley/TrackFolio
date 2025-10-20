import { useQuery } from '@tanstack/react-query';
import { getLastUpdate } from '@/lib/api';

export function useLastUpdate() {
  return useQuery({
    queryKey: ['prices', 'last-update'],
    queryFn: getLastUpdate,
    staleTime: 30000, // 30 seconds
  });
}
