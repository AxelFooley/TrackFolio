'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useHoldings } from '@/hooks/usePortfolio';
import { useRealtimePrices } from '@/hooks/useRealtimePrices';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useMemo } from 'react';

export function TodaysMovers() {
  const { data: holdings, isLoading } = useHoldings();
  const { realtimePrices } = useRealtimePrices();

  // Merge holdings with real-time data for consistency
  const holdingsWithRealtimeData = useMemo(() => {
    if (!holdings) return [];

    return holdings.map((holding) => {
      const realtimePrice = realtimePrices.get(holding.ticker);

      if (realtimePrice) {
        // Calculate updated values with real-time price
        const currentValue = holding.quantity * realtimePrice.current_price;
        const unrealizedGain = currentValue - holding.cost_basis;
        const returnPercentage = holding.cost_basis > 0
          ? unrealizedGain / holding.cost_basis
          : 0;

        return {
          ...holding,
          current_price: realtimePrice.current_price,
          current_value: currentValue,
          unrealized_gain: unrealizedGain,
          return_percentage: returnPercentage,
          // Total position change (not per-share)
          today_change: realtimePrice.change_amount * holding.quantity,
          today_change_percent: realtimePrice.change_percent,
        };
      }

      return holding;
    });
  }, [holdings, realtimePrices]);

  // Filter holdings with today_change_percent and sort
  const holdingsWithChange = useMemo(() => {
    return holdingsWithRealtimeData
      .filter((h) => h.today_change_percent !== null && h.today_change_percent !== undefined && h.today_change_percent !== 0)
      .sort((a, b) => (b.today_change_percent || 0) - (a.today_change_percent || 0));
  }, [holdingsWithRealtimeData]);

  const gainers = useMemo(() => holdingsWithChange.filter(h => (h.today_change_percent || 0) > 0).slice(0, 3), [holdingsWithChange]);
  const losers = useMemo(() => {
    const filteredLosers = holdingsWithChange.filter(h => (h.today_change_percent || 0) < 0);
    return [...filteredLosers].sort((a, b) => (a.today_change_percent || 0) - (b.today_change_percent || 0)).slice(0, 3);
  }, [holdingsWithChange]);

  // Debug logging (remove in production)
  console.log('Today\'s Movers Debug:', {
    totalHoldings: holdingsWithRealtimeData.length,
    holdingsWithChange: holdingsWithChange.length,
    gainers: gainers.length,
    losers: losers.length,
    sampleData: holdingsWithChange.slice(0, 5)
  });

  // Handle loading and empty states
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s Movers</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-200 rounded"></div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!holdings || holdings.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s Movers</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <p className="text-gray-500 mb-2">No holdings data available</p>
            <p className="text-sm text-gray-400">
              Import transactions to start tracking your portfolio
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // If no holdings have today's change data
  if (holdingsWithChange.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s Movers</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <p className="text-gray-500 mb-2">No movers data available yet</p>
            <p className="text-sm text-gray-400">
              Data will appear after we have multiple days of price history
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Today&apos;s Movers</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="text-sm font-semibold text-success mb-3 flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Top Gainers
            </h3>
            <div className="space-y-3">
              {gainers.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-4">No gainers</p>
              ) : (
                gainers.map((holding) => (
                  <div
                    key={holding.ticker}
                    className="flex items-center justify-between"
                  >
                    <div>
                      <p className="font-medium">{holding.ticker}</p>
                      <p className="text-sm text-gray-600">
                        {formatCurrency(holding.current_value, holding.currency)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium text-success">
                        {holding.today_change_percent !== null && holding.today_change_percent !== undefined
                          ? formatPercentage(holding.today_change_percent)
                          : '—'}
                      </p>
                      <p className="text-sm text-gray-600">
                        {formatCurrency(holding.today_change, holding.currency)}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-danger mb-3 flex items-center gap-2">
              <TrendingDown className="h-4 w-4" />
              Top Losers
            </h3>
            <div className="space-y-3">
              {losers.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-4">No losers</p>
              ) : (
                losers.map((holding) => (
                  <div
                    key={holding.ticker}
                    className="flex items-center justify-between"
                  >
                    <div>
                      <p className="font-medium">{holding.ticker}</p>
                      <p className="text-sm text-gray-600">
                        {formatCurrency(holding.current_value, holding.currency)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium text-danger">
                        {holding.today_change_percent !== null && holding.today_change_percent !== undefined
                          ? formatPercentage(holding.today_change_percent)
                          : '—'}
                      </p>
                      <p className="text-sm text-gray-600">
                        {formatCurrency(holding.today_change, holding.currency)}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
