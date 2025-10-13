'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useHoldings } from '@/hooks/usePortfolio';
import { useRealtimePrices } from '@/hooks/useRealtimePrices';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useMemo } from 'react';

/**
 * Render a card showing the top daily gainers and losers from the user's holdings.
 *
 * Computes current value, unrealized gain, today's total position change, and today's percentage change using holdings and real-time price data, then displays the top three gainers and top three losers. Provides loading, no-holdings, and no-movers fallback UIs.
 *
 * @returns A React element displaying today's movers (top gainers and top losers) with current value and today's change.
 */
export function TodaysMovers() {
  const { data: holdings, isLoading } = useHoldings();
  const symbols = holdings?.map(h => h.ticker) || [];
  const { realtimePrices } = useRealtimePrices(symbols);

  // Merge holdings with real-time data for consistency
  const holdingsWithRealtimeData = useMemo(() => {
    if (!holdings) return [];

    return holdings.map((holding) => {
      const realtimePrice = realtimePrices.get(holding.ticker);

      if (realtimePrice) {
        // Calculate updated values with real-time price
        const currentValue = holding.quantity * realtimePrice.current_price;
        const costBasis = holding.cost_basis || 0;
        const unrealizedGain = currentValue - costBasis;
        const returnPercentage = costBasis > 0
          ? unrealizedGain / costBasis
          : 0;

        // Calculate change values if not provided
        const hasPrevClose = typeof realtimePrice.previous_close === 'number';
        const changeAmount = realtimePrice.change_amount ??
          (hasPrevClose ? (realtimePrice.current_price - realtimePrice.previous_close) : 0);
        const changePercent = realtimePrice.change_percent ??
          (realtimePrice.previous_close > 0 ?
            ((realtimePrice.current_price - realtimePrice.previous_close) / realtimePrice.previous_close) * 100 : 0);

        return {
          ...holding,
          current_price: realtimePrice.current_price,
          current_value: currentValue,
          unrealized_gain: unrealizedGain,
          return_percentage: returnPercentage,
          // Total position change (not per-share)
          today_change: changeAmount * holding.quantity,
          today_change_percent: changePercent,
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