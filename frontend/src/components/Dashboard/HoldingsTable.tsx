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
import { useUnifiedHoldings } from '@/hooks/usePortfolio';
import { formatCurrency, formatPercentage, formatNumber } from '@/lib/utils';
import { ArrowUpDown, TrendingUp, TrendingDown } from 'lucide-react';
import type { UnifiedHolding } from '@/lib/types';

type SortField = 'ticker' | 'quantity' | 'current_price' | 'current_value' | 'profit_loss' | 'profit_loss_pct' | 'type';
type SortDirection = 'asc' | 'desc';

/**
 * Render a sortable unified holdings table that displays both traditional and crypto positions.
 *
 * The component shows loading skeletons while holdings load, an empty state when there are no holdings,
 * and a table of positions when data is available. Each row shows asset type indicator and is clickable
 * to navigate to the appropriate detail page based on asset type.
 *
 * @returns The rendered unified holdings table React element
 */
export function HoldingsTable() {
  const router = useRouter();
  const { data: response, isLoading } = useUnifiedHoldings(0, 100);
  const holdings = response?.items || [];
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

  const getAssetTypeBadge = (type: string) => {
    switch (type) {
      case 'STOCK':
        return <Badge variant="secondary">Stock</Badge>;
      case 'ETF':
        return <Badge variant="secondary">ETF</Badge>;
      case 'CRYPTO':
        return <Badge className="bg-orange-100 text-orange-800">Crypto</Badge>;
      default:
        return <Badge variant="outline">{type}</Badge>;
    }
  };

  const handleRowClick = (holding: UnifiedHolding) => {
    if (holding.type === 'CRYPTO') {
      // For crypto, navigate to crypto portfolio holdings
      if (holding.portfolio_id) {
        router.push(`/crypto/${holding.portfolio_id}/holdings/${holding.ticker}`);
      }
    } else {
      // For traditional assets, navigate to asset detail page
      router.push(`/asset/${holding.ticker}`);
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
    let aValue: number | string;
    let bValue: number | string;

    switch (sortField) {
      case 'ticker':
        aValue = a.ticker.toUpperCase();
        bValue = b.ticker.toUpperCase();
        break;
      case 'quantity':
        aValue = a.quantity;
        bValue = b.quantity;
        break;
      case 'current_price':
        aValue = a.current_price;
        bValue = b.current_price;
        break;
      case 'current_value':
        aValue = a.current_value;
        bValue = b.current_value;
        break;
      case 'profit_loss':
        aValue = a.profit_loss;
        bValue = b.profit_loss;
        break;
      case 'profit_loss_pct':
        aValue = a.profit_loss_pct;
        bValue = b.profit_loss_pct;
        break;
      case 'type':
        aValue = a.type;
        bValue = b.type;
        break;
      default:
        aValue = 0;
        bValue = 0;
    }

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
        <CardTitle>Holdings ({holdings.length})</CardTitle>
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
                  onClick={() => handleSort('type')}
                >
                  <div className="flex items-center gap-2">
                    Type
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
                  onClick={() => handleSort('current_price')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Price
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
                  onClick={() => handleSort('profit_loss')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Profit/Loss
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('profit_loss_pct')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Return %
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedHoldings.map((holding) => {
                const profitLoss = holding.profit_loss ?? 0;
                const profitLossPct = holding.profit_loss_pct ?? 0;

                return (
                  <TableRow
                    key={`${holding.type}-${holding.ticker}-${holding.portfolio_id || 'main'}`}
                    className="cursor-pointer hover:bg-gray-50"
                    onClick={() => handleRowClick(holding)}
                  >
                    <TableCell className="font-medium">{holding.ticker}</TableCell>
                    <TableCell>{getAssetTypeBadge(holding.type)}</TableCell>
                    <TableCell className="text-right font-mono">
                      {formatNumber(holding.quantity, 8)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(holding.current_price, holding.currency)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(holding.current_value, holding.currency)}
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${
                        profitLoss >= 0 ? 'text-success' : 'text-danger'
                      }`}
                    >
<<<<<<< HEAD
                      <div className="flex items-center justify-end gap-1">
                        {profitLoss >= 0 ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : (
                          <TrendingDown className="h-3 w-3" />
                        )}
                        {formatCurrency(profitLoss, holding.currency)}
                      </div>
=======
                      {formatCurrency(holding.unrealized_gain, holding.currency || 'EUR')}
>>>>>>> main
                    </TableCell>
                    <TableCell
                      className={`text-right font-mono ${
                        profitLossPct >= 0 ? 'text-success' : 'text-danger'
                      }`}
                    >
                      {formatPercentage(profitLossPct)}
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
