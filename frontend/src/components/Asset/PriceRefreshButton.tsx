'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { RefreshCw, Download } from 'lucide-react';
import { refreshPrices, ensurePriceCoverage } from '@/lib/api';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

interface PriceRefreshButtonProps {
  symbols?: string[];
  showFullRefresh?: boolean;
  variant?: 'default' | 'outline' | 'ghost' | 'destructive';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  className?: string;
}

/**
 * Manual price refresh button with options for current prices or full history.
 */
export function PriceRefreshButton({
  symbols,
  showFullRefresh = false,
  variant = 'outline',
  size = 'sm',
  className = '',
}: PriceRefreshButtonProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const queryClient = useQueryClient();

  // Mutation for refreshing current prices
  const refreshMutation = useMutation({
    mutationFn: async (currentOnly: boolean) => {
      const response = await refreshPrices(currentOnly, symbols);
      return response;
    },
    onSuccess: (data) => {
      toast.success(`Price refresh triggered: ${data.message}`);

      // Invalidate related queries to refresh UI data
      if (symbols) {
        symbols.forEach(symbol => {
          queryClient.invalidateQueries({ queryKey: ['asset', symbol, 'prices'] });
        });
      } else {
        queryClient.invalidateQueries({ queryKey: ['asset'] });
        queryClient.invalidateQueries({ queryKey: ['portfolio'] });
        queryClient.invalidateQueries({ queryKey: ['crypto'] });
      }

      setIsRefreshing(false);
    },
    onError: (error) => {
      toast.error(`Failed to refresh prices: ${error.message}`);
      setIsRefreshing(false);
    },
  });

  // Mutation for ensuring complete coverage
  const coverageMutation = useMutation({
    mutationFn: async () => {
      const response = await ensurePriceCoverage(symbols);
      return response;
    },
    onSuccess: (data) => {
      toast.success(`Price coverage check: ${data.message}`);
      setIsRefreshing(false);
    },
    onError: (error) => {
      toast.error(`Failed to check price coverage: ${error.message}`);
      setIsRefreshing(false);
    },
  });

  const handleCurrentRefresh = () => {
    setIsRefreshing(true);
    refreshMutation.mutate(true); // current_only = true
  };

  const handleFullRefresh = () => {
    setIsRefreshing(true);
    refreshMutation.mutate(false); // current_only = false
  };

  const handleCoverageCheck = () => {
    setIsRefreshing(true);
    coverageMutation.mutate();
  };

  const isLoading = refreshMutation.isPending || coverageMutation.isPending;

  return (
    <div className={`flex gap-2 ${className}`}>
      <Button
        variant={variant}
        size={size}
        onClick={handleCurrentRefresh}
        disabled={isLoading}
        className="relative"
      >
        <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
        <span className="hidden sm:inline ml-2">
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </span>
        <span className="sm:hidden">
          {isRefreshing ? '...' : '↻'}
        </span>
      </Button>

      {showFullRefresh && (
        <>
          <Button
            variant={variant}
            size={size}
            onClick={handleFullRefresh}
            disabled={isLoading}
            className="relative"
            title="Fetch complete historical data for all symbols"
          >
            <Download className="h-4 w-4" />
            <span className="hidden sm:inline ml-2">Full History</span>
            <span className="sm:hidden">📊</span>
          </Button>

          <Button
            variant={variant}
            size={size}
            onClick={handleCoverageCheck}
            disabled={isLoading}
            className="relative"
            title="Check and fill gaps in historical data"
          >
            <RefreshCw className="h-4 w-4" />
            <span className="hidden sm:inline ml-2">Ensure Coverage</span>
            <span className="sm:hidden">✓</span>
          </Button>
        </>
      )}
    </div>
  );
}

/**
 * Simple refresh button for inline use.
 */
export function SimpleRefreshButton({ symbols }: { symbols?: string[] }) {
  return (
    <PriceRefreshButton
      symbols={symbols}
      variant="ghost"
      size="icon"
      className="h-8 w-8"
    />
  );
}