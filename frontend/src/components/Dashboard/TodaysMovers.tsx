'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useHoldings } from '@/hooks/usePortfolio';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import { TrendingUp, TrendingDown } from 'lucide-react';

export function TodaysMovers() {
  const { data: holdings, isLoading } = useHoldings();

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

  // Filter holdings with today_change_percent and sort
  const holdingsWithChange = holdings
    .filter((h) => h.today_change_percent !== undefined && h.today_change_percent !== null)
    .sort((a, b) => (b.today_change_percent || 0) - (a.today_change_percent || 0));

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

  const gainers = holdingsWithChange.filter(h => (h.today_change_percent || 0) > 0).slice(0, 3);
  const losers = holdingsWithChange.filter(h => (h.today_change_percent || 0) < 0).slice(0, 3);

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
