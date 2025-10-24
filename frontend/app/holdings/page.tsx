'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
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
import { Search, ArrowUpDown, TrendingUp, TrendingDown } from 'lucide-react';
import type { UnifiedHolding } from '@/lib/types';

type SortField = 'ticker' | 'quantity' | 'current_price' | 'current_value' | 'profit_loss' | 'profit_loss_pct' | 'type';
type SortDirection = 'asc' | 'desc';

export default function HoldingsPage() {
  const router = useRouter();
  const { data: response, isLoading } = useUnifiedHoldings(0, 1000);
  const holdings = response?.items || [];
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
    holding.ticker.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (holding.name && holding.name.toLowerCase().includes(searchTerm.toLowerCase())) ||
    holding.type.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const sortedHoldings = [...filteredHoldings].sort((a, b) => {
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

  const totalValue = holdings.reduce((sum, h) => sum + (Number(h.current_value) || 0), 0);
  const totalProfit = holdings.reduce((sum, h) => sum + (Number(h.profit_loss) || 0), 0);
  const totalCostBasis = holdings.reduce((sum, h) => sum + (Number(h.total_cost) || 0), 0);
  const totalReturnPercent = totalCostBasis > 0 ? (totalProfit / totalCostBasis) * 100 : 0;
  const cryptoCount = holdings.filter(h => h.type === 'CRYPTO').length;
  const traditionalCount = holdings.filter(h => h.type !== 'CRYPTO').length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Holdings</h1>
          <p className="text-gray-600">Detailed view of all your positions</p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
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
              <p className="text-xs text-gray-600 mt-1">
                {traditionalCount} Traditional, {cryptoCount} Crypto
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Cost Basis
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold font-mono">
                {formatCurrency(totalCostBasis, 'EUR')}
              </div>
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
                        Current Value
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
                          <div className="flex items-center justify-end gap-1">
                            {profitLoss >= 0 ? (
                              <TrendingUp className="h-3 w-3" />
                            ) : (
                              <TrendingDown className="h-3 w-3" />
                            )}
                            {formatCurrency(profitLoss, holding.currency)}
                          </div>
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
      </div>
    </div>
  );
}
