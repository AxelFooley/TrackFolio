'use client';

import { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatCurrency, formatPercentage, formatNumber } from '@/lib/utils';
import { ArrowUpDown, TrendingUp, TrendingDown, PieChart, ExternalLink } from 'lucide-react';
import type { CryptoHolding } from '@/types/crypto-paper';

type SortField = keyof CryptoHolding | 'allocation_pct';
type SortDirection = 'asc' | 'desc';

interface CryptoHoldingWithAllocation extends CryptoHolding {
  allocation_pct: number;
}

interface CryptoHoldingsTableProps {
  holdings: CryptoHolding[];
  totalValue: number;
  isLoading?: boolean;
}

export function CryptoHoldingsTable({ holdings, totalValue, isLoading }: CryptoHoldingsTableProps) {
  const [sortField, setSortField] = useState<SortField>('current_value_usd');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  // Calculate allocation percentages
  const holdingsWithAllocation = useMemo((): CryptoHoldingWithAllocation[] => {
    return holdings.map(holding => ({
      ...holding,
      allocation_pct: totalValue > 0 ? (holding.current_value_usd / totalValue) * 100 : 0,
    }));
  }, [holdings, totalValue]);

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
          <CardTitle>Crypto Holdings</CardTitle>
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
          <CardTitle>Crypto Holdings</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">No crypto holdings data available</p>
        </CardContent>
      </Card>
    );
  }

  const sortedHoldings = [...holdingsWithAllocation].sort((a, b) => {
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
        <CardTitle className="flex items-center gap-2">
          <PieChart className="h-5 w-5" />
          Crypto Holdings
        </CardTitle>
        <Badge variant="outline" className="font-mono">
          {holdings.length} assets
        </Badge>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead
                  className="cursor-pointer"
                  onClick={() => handleSort('symbol')}
                >
                  <div className="flex items-center gap-2">
                    Symbol
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer"
                  onClick={() => handleSort('name')}
                >
                  <div className="flex items-center gap-2">
                    Name
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('quantity')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Quantity
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('average_cost_usd')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Avg Cost
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('current_price_usd')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Current Price
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('allocation_pct')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Allocation
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('current_value_usd')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Value
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('unrealized_profit_usd')}
                >
                  <div className="flex items-center justify-end gap-2">
                    P&L
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('unrealized_profit_pct')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Return
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedHoldings.map((holding) => {
                const isPositiveProfit = holding.unrealized_profit_usd >= 0;
                const isPositiveReturn = holding.unrealized_profit_pct >= 0;

                return (
                  <TableRow key={holding.symbol} className="hover:bg-gray-50">
                    <TableCell className="font-medium font-mono">
                      <div className="flex items-center gap-2">
                        {holding.symbol}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 hover:bg-blue-50"
                          onClick={() => {
                            // Open external link to crypto price chart or details
                            const url = `https://www.coingecko.com/en/coins/${holding.symbol.toLowerCase()}`;
                            window.open(url, '_blank');
                          }}
                        >
                          <ExternalLink className="h-3 w-3" />
                        </Button>
                      </div>
                    </TableCell>
                    <TableCell className="max-w-xs truncate" title={holding.name || undefined}>
                      {holding.name || '—'}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatNumber(holding.quantity, 6)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(holding.average_cost_usd, 'USD')}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(holding.current_price_usd, 'USD')}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      <div className="flex items-center justify-end gap-1">
                        <div className="w-12 h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500"
                            style={{ width: `${Math.min(holding.allocation_pct, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs">
                          {formatPercentage(holding.allocation_pct)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(holding.current_value_usd, 'USD')}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${
                        isPositiveProfit ? 'text-green-600' : 'text-red-600'
                      }`}
                    >
                      <div className="flex items-center justify-end gap-1">
                        {isPositiveProfit ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : (
                          <TrendingDown className="h-3 w-3" />
                        )}
                        <span>
                          {formatCurrency(Math.abs(holding.unrealized_profit_usd), 'USD')}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${
                        isPositiveReturn ? 'text-green-600' : 'text-red-600'
                      }`}
                    >
                      {formatPercentage(holding.unrealized_profit_pct)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>

        {/* Summary Row */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Total Value:</span>
              <div className="font-semibold text-lg">
                {formatCurrency(totalValue, 'USD')}
              </div>
            </div>
            <div>
              <span className="text-gray-600">Total Cost:</span>
              <div className="font-semibold text-lg">
                {formatCurrency(holdings.reduce((sum, h) => sum + h.cost_basis_usd, 0), 'USD')}
              </div>
            </div>
            <div>
              <span className="text-gray-600">Total P&L:</span>
              <div className={`font-semibold text-lg ${
                holdings.reduce((sum, h) => sum + h.unrealized_profit_usd, 0) >= 0
                  ? 'text-green-600'
                  : 'text-red-600'
              }`}>
                {formatCurrency(
                  holdings.reduce((sum, h) => sum + h.unrealized_profit_usd, 0),
                  'USD'
                )}
              </div>
            </div>
            <div>
              <span className="text-gray-600">Assets:</span>
              <div className="font-semibold text-lg">{holdings.length}</div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}