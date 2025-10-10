'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { useCryptoHoldings } from '@/hooks/useCrypto';
import { formatCurrency, formatCryptoQuantity, formatPercentage } from '@/lib/utils';
import { TrendingUp, TrendingDown, ArrowUpDown, Search, Bitcoin } from 'lucide-react';
import { Input } from '@/components/ui/input';
import type { CryptoPosition } from '@/lib/types';

interface CryptoHoldingsTableProps {
  portfolioId: number;
  limit?: number;
  showSearch?: boolean;
}

export function CryptoHoldingsTable({ portfolioId, limit, showSearch = true }: CryptoHoldingsTableProps) {
  const router = useRouter();
  const { data: holdings, isLoading } = useCryptoHoldings(portfolioId);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState<keyof CryptoPosition>('current_value');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const handleSort = (field: keyof CryptoPosition) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {showSearch && (
          <div className="h-10 bg-gray-200 rounded animate-pulse w-64"></div>
        )}
        <div className="space-y-3">
          {[...Array(limit || 5)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-200 rounded animate-pulse"></div>
          ))}
        </div>
      </div>
    );
  }

  if (!holdings || holdings.length === 0) {
    return (
      <div className="text-center py-8">
        <Bitcoin className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">No holdings found</h3>
        <p className="text-gray-600">
          Add transactions to start building your crypto portfolio
        </p>
      </div>
    );
  }

  let filteredHoldings = holdings.filter((holding) =>
    holding.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
    holding.asset_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Apply limit if specified
  if (limit) {
    filteredHoldings = filteredHoldings.slice(0, limit);
  }

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

  return (
    <div className="space-y-4">
      {showSearch && (
        <div className="relative w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search by symbol or name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>
      )}

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
              <TableHead>Asset Name</TableHead>
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
            </TableRow>
          </TableHeader>
          <TableBody>
          <TableBody>
            {sortedHoldings.map((holding) => {
              const isPositive = holding.unrealized_gain >= 0;
              const rawPct = holding.return_percentage;
              const hasPct = rawPct !== null && rawPct !== undefined;
              const returnPercentage = hasPct ? rawPct * 100 : null;
              return (
                <TableRow
                  key={holding.symbol}
                  className="cursor-pointer hover:bg-gray-50"
                  onClick={() => router.push(`/crypto/${portfolioId}/holdings/${holding.symbol}`)}
                >
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <Bitcoin className="h-4 w-4 text-orange-500" />
                      {holding.symbol}
                    </div>
                  </TableCell>
                  <TableCell className="text-gray-600">
                    {holding.asset_name}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatCryptoQuantity(holding.quantity)}
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
                      isPositive ? 'text-success' : 'text-danger'
                    }`}
                  >
                    <div className="flex items-center justify-end gap-1">
                      {isPositive ? (
                        <TrendingUp className="h-4 w-4" />
                      ) : (
                        <TrendingDown className="h-4 w-4" />
                      )}
                      {formatCurrency(holding.unrealized_gain, holding.currency)}
                    </div>
                  </TableCell>
                  <TableCell
                    className={`text-right font-mono ${
                      hasPct ? (returnPercentage! >= 0 ? 'text-success' : 'text-danger') : ''
                    }`}
                  >
                    <Badge
                      variant={!hasPct ? 'outline' : (returnPercentage! >= 0 ? 'default' : 'destructive')}
                      className="text-xs"
                    >
                      {hasPct ? formatPercentage(returnPercentage!) : '—'}
                    </Badge>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {limit && holdings.length > limit && (
        <div className="text-center">
          <button
            onClick={() => router.push(`/crypto/${portfolioId}/holdings`)}
            className="text-sm text-blue-600 hover:text-blue-800 underline"
          >
            View all {holdings.length} holdings
          </button>
        </div>
      )}
    </div>
  );
}