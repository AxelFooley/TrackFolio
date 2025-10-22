'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useHoldings } from '@/hooks/usePortfolio';
import { useRealtimePrices } from '@/hooks/useRealtimePrices';
import { formatCurrency, formatPercentage, formatNumber } from '@/lib/utils';
import { ArrowUpDown, TrendingUp, TrendingDown, Activity } from 'lucide-react';
import type { Position } from '@/lib/types';

type SortField = keyof Position;
type SortDirection = 'asc' | 'desc';

/**
 * Render a sortable holdings table that displays portfolio positions augmented with real-time price data.
 *
 * The component shows loading skeletons while holdings load, an empty state when there are no holdings,
 * and a table of positions when data is available. Each row is clickable to navigate to the asset detail page.
 * The table supports sorting by multiple fields and displays live-update metadata when real-time prices are available.
 *
 * @returns The rendered holdings table React element
 */
export function HoldingsTable() {
  const router = useRouter();
  const { data: holdings, isLoading } = useHoldings();
  const symbols = holdings?.map(h => h.ticker) || [];
  const { realtimePrices, isLoading: pricesLoading, lastUpdate } = useRealtimePrices(symbols);
  const [sortField, setSortField] = useState<SortField>('current_value');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  // Merge holdings with real-time prices
  const holdingsWithRealtimePrices = useMemo(() => {
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

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Holdings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 rounded animate-pulse"></div>
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
          <CardTitle>Holdings</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">No holdings data available</p>
        </CardContent>
      </Card>
    );
  }

  const sortedHoldings = [...holdingsWithRealtimePrices].sort((a, b) => {
    const aValue = a[sortField];
    const bValue = b[sortField];

    if (typeof aValue === 'number' && typeof bValue === 'number') {
      return sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
    }

    if (typeof aValue === 'string' && typeof bValue === 'string') {
      return sortDirection === 'asc'
        ? aValue.localeCompare(bValue)
        : bValue.localeCompare(aValue);
    }

    return 0;
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Holdings</CardTitle>
        {!pricesLoading && lastUpdate && (
          <Badge variant="outline" className="gap-1.5">
            <Activity className="h-3 w-3 animate-pulse text-green-500" />
            <span className="text-xs text-gray-500">
              Live - Updated {lastUpdate.toLocaleTimeString()}
            </span>
          </Badge>
        )}
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead
                  className="cursor-pointer"
                  onClick={() => handleSort('ticker')}
                >
                  <div className="flex items-center gap-2">
                    Ticker
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer"
                  onClick={() => handleSort('description')}
                >
                  <div className="flex items-center gap-2">
                    Description
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('quantity')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Shares
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('average_cost')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Avg Cost
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('current_price')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Current Price
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('today_change')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Today&apos;s Change
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('current_value')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Value
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('unrealized_gain')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Profit
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('return_percentage')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Return
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('irr')}
                >
                  <div className="flex items-center justify-end gap-2">
                    IRR
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedHoldings.map((holding) => {
                const hasRealtimeData = realtimePrices.has(holding.ticker);
                const todayChange = holding.today_change ?? 0;
                const todayChangePercent = holding.today_change_percent ?? 0;

                return (
                  <TableRow
                    key={holding.ticker}
                    className="cursor-pointer hover:bg-gray-50"
                    onClick={() => router.push(`/asset/${holding.ticker}`)}
                  >
                    <TableCell className="font-medium">{holding.ticker}</TableCell>
                    <TableCell className="max-w-xs truncate" title={holding.description || undefined}>
                      {holding.description || '—'}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatNumber(holding.quantity, 4)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(holding.average_cost, holding.currency || 'EUR')}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      <div className="flex items-center justify-end gap-1.5">
                        {formatCurrency(holding.current_price, holding.currency || 'EUR')}
                        {hasRealtimeData && (
                          <span className="inline-block h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${
                        todayChange >= 0 ? 'text-success' : 'text-danger'
                      }`}
                    >
                      {hasRealtimeData ? (
                        <div className="flex items-center justify-end gap-1">
                          {todayChange >= 0 ? (
                            <TrendingUp className="h-3 w-3" />
                          ) : (
                            <TrendingDown className="h-3 w-3" />
                          )}
                          <span>
                            {formatCurrency(Math.abs(todayChange), holding.currency || 'EUR')} (
                            {formatPercentage(todayChangePercent)})
                          </span>
                        </div>
                      ) : (
                        '—'
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(holding.current_value, holding.currency || 'EUR')}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${
                        (holding.unrealized_gain ?? 0) >= 0 ? 'text-success' : 'text-danger'
                      }`}
                    >
                      {formatCurrency(holding.unrealized_gain, holding.currency || 'EUR')}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${
                        (holding.return_percentage ?? 0) >= 0 ? 'text-success' : 'text-danger'
                      }`}
                    >
                      {holding.return_percentage !== null && holding.return_percentage !== undefined
                        ? formatPercentage(holding.return_percentage * 100)
                        : '—'}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${
                        (holding.irr ?? 0) >= 0 ? 'text-success' : 'text-danger'
                      }`}
                    >
                      {holding.irr !== null && holding.irr !== undefined
                        ? formatPercentage(holding.irr * 100)
                        : '—'}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}