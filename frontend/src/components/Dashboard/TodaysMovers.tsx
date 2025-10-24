'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useUnifiedMovers } from '@/hooks/usePortfolio';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useMemo } from 'react';

/**
 * Render a card showing the top daily gainers and losers from both traditional and crypto holdings.
 *
 * Displays top 5 gainers and losers combined from both asset types.
 * Provides loading, no-holdings, and no-movers fallback UIs.
 *
 * @returns A React element displaying today's movers (top gainers and top losers)
 */
export function TodaysMovers() {
  const { data: moversData, isLoading } = useUnifiedMovers();

  const gainers = useMemo(() => moversData?.gainers || [], [moversData]);
  const losers = useMemo(() => moversData?.losers || [], [moversData]);

  // Handle loading state
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s Movers</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-200 rounded animate-pulse"></div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Handle no movers state
  if (gainers.length === 0 && losers.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s Movers</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">No movers data available</p>
        </CardContent>
      </Card>
    );
  }

  const getAssetTypeBadge = (type: string) => {
    switch (type) {
      case 'STOCK':
        return <Badge variant="secondary" className="text-xs">Stock</Badge>;
      case 'ETF':
        return <Badge variant="secondary" className="text-xs">ETF</Badge>;
      case 'CRYPTO':
        return <Badge className="bg-orange-100 text-orange-800 text-xs">Crypto</Badge>;
      default:
        return <Badge variant="outline" className="text-xs">{type}</Badge>;
    }
  };

  const MoverRow = ({ mover, isGainer }: { mover: typeof gainers[0]; isGainer: boolean }) => {
    const changeColor = isGainer ? 'text-success' : 'text-danger';
    const Icon = isGainer ? TrendingUp : TrendingDown;

    return (
      <div className="flex items-center justify-between py-3 border-b last:border-b-0">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-sm">{mover.ticker}</span>
            {getAssetTypeBadge(mover.type)}
          </div>
          {mover.portfolio_name && (
            <p className="text-xs text-gray-500">{mover.portfolio_name}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="font-mono text-sm">{formatCurrency(mover.current_value, mover.currency)}</p>
            <p className={`font-mono text-xs ${changeColor}`}>
              {formatCurrency(mover.today_change, mover.currency)}
            </p>
          </div>
          <div className={`flex items-center gap-1 ${changeColor} min-w-max`}>
            <Icon className="h-4 w-4" />
            <span className="font-mono text-sm">{formatPercentage(mover.today_change_percent)}</span>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Gainers */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-success">
            <TrendingUp className="h-5 w-5" />
            Top Gainers
          </CardTitle>
        </CardHeader>
        <CardContent>
          {gainers.length === 0 ? (
            <p className="text-gray-500 text-sm">No gainers today</p>
          ) : (
            <div className="space-y-0">
              {gainers.slice(0, 5).map((mover, idx) => (
                <MoverRow key={`${mover.type}-${mover.ticker}-${idx}`} mover={mover} isGainer={true} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Losers */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-danger">
            <TrendingDown className="h-5 w-5" />
            Top Losers
          </CardTitle>
        </CardHeader>
        <CardContent>
          {losers.length === 0 ? (
            <p className="text-gray-500 text-sm">No losers today</p>
          ) : (
            <div className="space-y-0">
              {losers.slice(0, 5).map((mover, idx) => (
                <MoverRow key={`${mover.type}-${mover.ticker}-${idx}`} mover={mover} isGainer={false} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
