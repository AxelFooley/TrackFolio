'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
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
import { Search, ArrowUpDown } from 'lucide-react';
import type { Position } from '@/lib/types';

type SortField = keyof Position;
type SortDirection = 'asc' | 'desc';

export default function HoldingsPage() {
  const router = useRouter();
  const { data: holdings, isLoading } = useHoldings();
  const [searchTerm, setSearchTerm] = useState('');
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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          <div>
            <h1 className="text-3xl font-bold mb-2">Holdings</h1>
            <p className="text-gray-600">Detailed view of all your positions</p>
          </div>
          <Card>
            <CardContent className="pt-6">
              <div className="space-y-4">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-16 bg-gray-200 rounded animate-pulse"></div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (!holdings || holdings.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          <div>
            <h1 className="text-3xl font-bold mb-2">Holdings</h1>
            <p className="text-gray-600">Detailed view of all your positions</p>
          </div>
          <Card>
            <CardContent className="pt-6">
              <p className="text-gray-500 text-center py-8">
                No holdings found. Import transactions to get started.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const filteredHoldings = holdings.filter((holding) =>
    holding.ticker.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const sortedHoldings = [...filteredHoldings].sort((a, b) => {
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

  const totalValue = holdings.reduce((sum, h) => sum + (Number(h.current_value) || 0), 0);
  const totalProfit = holdings.reduce((sum, h) => sum + (Number(h.unrealized_gain) || 0), 0);
  const totalCostBasis = holdings.reduce((sum, h) => sum + (Number(h.cost_basis) || 0), 0);
  const totalReturnPercent = totalCostBasis > 0 ? (totalProfit / totalCostBasis) * 100 : 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Holdings</h1>
          <p className="text-gray-600">Detailed view of all your positions</p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Total Value
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold font-mono">
                {formatCurrency(totalValue, 'EUR')}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Total Profit
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div
                className={`text-2xl font-bold font-mono ${
                  totalProfit >= 0 ? 'text-success' : 'text-danger'
                }`}
              >
                {formatCurrency(totalProfit, 'EUR')}
              </div>
              <p className="text-xs text-gray-600 mt-1">
                {formatPercentage(totalReturnPercent)}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Total Positions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{holdings.length}</div>
            </CardContent>
          </Card>
        </div>

        {/* Holdings Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>All Holdings</CardTitle>
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search by ticker..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
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
                      onClick={() => handleSort('cost_basis')}
                    >
                      <div className="flex items-center justify-end gap-2">
                        Cost Basis
                        <ArrowUpDown className="h-4 w-4" />
                      </div>
                    </TableHead>
                    <TableHead
                      className="cursor-pointer text-right"
                      onClick={() => handleSort('current_value')}
                    >
                      <div className="flex items-center justify-end gap-2">
                        Current Value
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
                        Return %
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
                      <TableCell className="text-right font-mono">
                        {formatNumber(holding.quantity, 4)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatCurrency(holding.average_cost, holding.currency)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatCurrency(holding.cost_basis, holding.currency)}
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
      </div>
    </div>
  );
}
