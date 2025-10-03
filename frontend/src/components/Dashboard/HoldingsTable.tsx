'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useHoldings } from '@/hooks/usePortfolio';
import { formatCurrency, formatPercentage, formatNumber } from '@/lib/utils';
import { ArrowUpDown } from 'lucide-react';
import type { Position } from '@/lib/types';

type SortField = keyof Position;
type SortDirection = 'asc' | 'desc';

export function HoldingsTable() {
  const router = useRouter();
  const { data: holdings, isLoading } = useHoldings();
  const [sortField, setSortField] = useState<SortField>('current_value');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

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

  const sortedHoldings = [...holdings].sort((a, b) => {
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
      <CardHeader>
        <CardTitle>Holdings</CardTitle>
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
              {sortedHoldings.map((holding) => (
                <TableRow
                  key={holding.ticker}
                  className="cursor-pointer hover:bg-gray-50"
                  onClick={() => router.push(`/asset/${holding.ticker}`)}
                >
                  <TableCell className="font-medium">{holding.ticker}</TableCell>
                  <TableCell className="max-w-xs truncate" title={holding.description}>
                    {holding.description || '—'}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatNumber(holding.quantity, 4)}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatCurrency(holding.average_cost, holding.currency)}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatCurrency(holding.current_price, holding.currency)}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatCurrency(holding.current_value, holding.currency)}
                  </TableCell>
                  <TableCell
                    className={`text-right font-mono ${
                      (holding.unrealized_gain ?? 0) >= 0 ? 'text-success' : 'text-danger'
                    }`}
                  >
                    {formatCurrency(holding.unrealized_gain, holding.currency)}
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
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
