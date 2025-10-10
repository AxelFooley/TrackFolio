'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useCryptoPortfolio, useCryptoHoldings, useCryptoPortfolioMetrics } from '@/hooks/useCrypto';
import { formatCurrency, formatCryptoQuantity, formatPercentage, formatDate } from '@/lib/utils';
import { ArrowLeft, Search, Bitcoin, TrendingUp, TrendingDown, ArrowUpDown, Eye } from 'lucide-react';
import { CryptoHoldingsTable } from '@/components/Crypto/CryptoHoldingsTable';
import type { CryptoPosition } from '@/lib/types';

export default function CryptoHoldingsPage() {
  const params = useParams();
  const router = useRouter();
  const portfolioId = parseInt(params.id as string);

  const { data: portfolio, isLoading: portfolioLoading } = useCryptoPortfolio(portfolioId);
  const { data: holdings, isLoading: holdingsLoading } = useCryptoHoldings(portfolioId);
  const { data: metrics, isLoading: metricsLoading } = useCryptoPortfolioMetrics(portfolioId);

  // Search state
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

  if (portfolioLoading || !portfolio) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => router.back()}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <div className="h-8 bg-gray-200 rounded animate-pulse w-48"></div>
          </div>
          <div className="h-96 bg-gray-200 rounded animate-pulse"></div>
        </div>
      </div>
    );
  }

  // Filter and sort holdings
  let filteredHoldings = holdings?.filter((holding) =>
    holding.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
    holding.asset_name.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

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

  // Calculate totals
  const totalValue = holdings?.reduce((sum, h) => sum + h.current_value, 0) || 0;
  const totalCostBasis = holdings?.reduce((sum, h) => sum + h.cost_basis, 0) || 0;
  const totalProfit = holdings?.reduce((sum, h) => sum + h.unrealized_gain, 0) || 0;
  const totalReturnPercent = totalCostBasis > 0 ? (totalProfit / totalCostBasis) * 100 : 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => router.push(`/crypto/${portfolioId}`)}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Portfolio
            </Button>
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-3">
                <Bitcoin className="h-8 w-8 text-orange-500" />
                {portfolio.name} - Holdings
              </h1>
              <p className="text-gray-600 mt-1">Detailed view of your cryptocurrency positions</p>
            </div>
          </div>
          <Badge variant="outline" className="text-sm">
            {portfolio.base_currency} Portfolio
          </Badge>
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
              <div className="text-2xl font-bold">
                {formatCurrency(totalValue, portfolio.base_currency)}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Total Cost Basis
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCurrency(totalCostBasis, portfolio.base_currency)}
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
              <div className={`text-2xl font-bold ${totalProfit >= 0 ? 'text-success' : 'text-danger'}`}>
                {formatCurrency(totalProfit, portfolio.base_currency)}
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
              <div className="text-2xl font-bold">
                {holdings?.length || 0}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Asset Allocation Chart */}
        {metrics && metrics.asset_allocation && metrics.asset_allocation.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Asset Allocation</CardTitle>
              <CardDescription>
                Portfolio distribution by asset
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {metrics.asset_allocation
                  .sort((a, b) => b.value - a.value)
                  .slice(0, 9)
                  .map((asset, index) => {
                    const percentage = asset.percentage || 0;
                    const barWidth = Math.max(percentage, 5); // Minimum width for visibility
                    return (
                      <div key={asset.symbol} className="space-y-2">
                        <div className="flex justify-between items-center">
                          <div className="flex items-center gap-2">
                            <Bitcoin className="h-4 w-4 text-orange-500" />
                            <span className="font-medium">{asset.symbol}</span>
                          </div>
                          <div className="text-right">
                            <div className="font-semibold">
                              {formatCurrency(asset.value, portfolio.base_currency)}
                            </div>
                            <div className="text-xs text-gray-600">
                              {formatPercentage(percentage)}
                            </div>
                          </div>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${barWidth}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Holdings Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>All Holdings</CardTitle>
                <CardDescription>
                  Your cryptocurrency positions sorted by value
                </CardDescription>
              </div>
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search by symbol or name..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {sortedHoldings.length === 0 ? (
              <div className="text-center py-8">
                <Bitcoin className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {searchTerm ? 'No holdings found' : 'No holdings yet'}
                </h3>
                <p className="text-gray-600 mb-4">
                  {searchTerm
                    ? 'Try adjusting your search terms'
                    : 'Add transactions to start building your crypto portfolio'}
                </p>
                {!searchTerm && (
                  <Button onClick={() => router.push(`/crypto/${portfolioId}/transactions`)}>
                    Add Transaction
                  </Button>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th
                        className="text-left py-3 px-4 cursor-pointer"
                        onClick={() => handleSort('symbol')}
                      >
                        <div className="flex items-center gap-2">
                          Symbol
                          <ArrowUpDown className="h-4 w-4" />
                        </div>
                      </th>
                      <th className="text-left py-3 px-4">Asset Name</th>
                      <th
                        className="text-right py-3 px-4 cursor-pointer"
                        onClick={() => handleSort('quantity')}
                      >
                        <div className="flex items-center justify-end gap-2">
                          Quantity
                          <ArrowUpDown className="h-4 w-4" />
                        </div>
                      </th>
                      <th
                        className="text-right py-3 px-4 cursor-pointer"
                        onClick={() => handleSort('average_cost')}
                      >
                        <div className="flex items-center justify-end gap-2">
                          Avg Cost
                          <ArrowUpDown className="h-4 w-4" />
                        </div>
                      </th>
                      <th
                        className="text-right py-3 px-4 cursor-pointer"
                        onClick={() => handleSort('current_price')}
                      >
                        <div className="flex items-center justify-end gap-2">
                          Current Price
                          <ArrowUpDown className="h-4 w-4" />
                        </div>
                      </th>
                      <th
                        className="text-right py-3 px-4 cursor-pointer"
                        onClick={() => handleSort('current_value')}
                      >
                        <div className="flex items-center justify-end gap-2">
                          Current Value
                          <ArrowUpDown className="h-4 w-4" />
                        </div>
                      </th>
                      <th
                        className="text-right py-3 px-4 cursor-pointer"
                        onClick={() => handleSort('unrealized_gain')}
                      >
                        <div className="flex items-center justify-end gap-2">
                          Profit
                          <ArrowUpDown className="h-4 w-4" />
                        </div>
                      </th>
                      <th
                        className="text-right py-3 px-4 cursor-pointer"
                        onClick={() => handleSort('return_percentage')}
                      >
                        <div className="flex items-center justify-end gap-2">
                          Return %
                          <ArrowUpDown className="h-4 w-4" />
                        </div>
                      </th>
                      <th className="text-right py-3 px-4">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedHoldings.map((holding) => {
                      const isPositive = holding.unrealized_gain >= 0;
                      const returnPercentage = holding.return_percentage;

                      return (
                        <tr
                          key={holding.symbol}
                          className="border-b hover:bg-gray-50"
                        >
                          <td className="py-4 px-4 font-medium">
                            <div className="flex items-center gap-2">
                              <Bitcoin className="h-5 w-5 text-orange-500" />
                              {holding.symbol}
                            </div>
                          </td>
                          <td className="py-4 px-4 text-gray-600">
                            {holding.asset_name}
                          </td>
                          <td className="py-4 px-4 text-right font-mono">
                            {formatCryptoQuantity(holding.quantity)}
                          </td>
                          <td className="py-4 px-4 text-right font-mono">
                            {formatCurrency(holding.average_cost, holding.currency)}
                          </td>
                          <td className="py-4 px-4 text-right font-mono">
                            {formatCurrency(holding.current_price, holding.currency)}
                          </td>
                          <td className="py-4 px-4 text-right font-mono">
                            {formatCurrency(holding.current_value, holding.currency)}
                          </td>
                          <td className="py-4 px-4 text-right font-mono">
                            <div className={`flex items-center justify-end gap-1 ${
                              isPositive ? 'text-success' : 'text-danger'
                            }`}>
                              {isPositive ? (
                                <TrendingUp className="h-4 w-4" />
                              ) : (
                                <TrendingDown className="h-4 w-4" />
                              )}
                              {formatCurrency(holding.unrealized_gain, holding.currency)}
                            </div>
                          </td>
                          <td className="py-4 px-4 text-right font-mono">
                            {holding.return_percentage === null || holding.return_percentage === undefined ? (
                              <Badge variant="outline" className="text-xs">—</Badge>
                            ) : (
                              <Badge
                                variant={holding.return_percentage >= 0 ? 'default' : 'destructive'}
                                className="text-xs"
                              >
                                {formatPercentage(holding.return_percentage * 100)}
                              </Badge>
                            )}
                          </td>
                          <td className="py-4 px-4 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => router.push(`/crypto/${portfolioId}/holdings/${holding.symbol}`)}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}