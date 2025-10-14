'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  useCryptoPortfolio,
  useCryptoPosition,
  useCryptoTransactions
} from '@/hooks/useCrypto';
import { formatCurrency, formatCryptoQuantity, formatPercentage, formatDateTime } from '@/lib/utils';
import {
  ArrowLeft,
  Bitcoin,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  Calendar
} from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

/**
 * Render the detailed view for a single cryptocurrency holding within a portfolio.
 *
 * Displays position metrics, recent transactions, and navigation controls.
 *
 * @returns The React element for the crypto holding detail page.
 */
export default function CryptoHoldingDetailPage() {
  const params = useParams();
  const router = useRouter();
  const portfolioId = parseInt(params.id as string);
  const symbol = params.symbol as string;

  const { data: portfolio, isLoading: portfolioLoading } = useCryptoPortfolio(portfolioId);
  const { data: position, isLoading: positionLoading } = useCryptoPosition(portfolioId, symbol);
  const { data: transactionsData, isLoading: transactionsLoading } = useCryptoTransactions(
    portfolioId,
    { symbol, limit: 50 }
  );

  if (portfolioLoading || positionLoading || !portfolio || !position) {
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => (
              <Card key={i}>
                <CardHeader>
                  <div className="h-4 bg-gray-200 rounded animate-pulse w-24"></div>
                </CardHeader>
                <CardContent>
                  <div className="h-8 bg-gray-200 rounded animate-pulse w-32"></div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const isPositive = position.unrealized_gain >= 0;
  const returnPct = position.return_percentage !== null && position.return_percentage !== undefined
    ? position.return_percentage * 100
    : null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push(`/crypto/${portfolioId}/holdings`)}
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Holdings
            </Button>
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-3">
                <Bitcoin className="h-8 w-8 text-orange-500" />
                {position.symbol}
              </h1>
              <p className="text-gray-600 mt-1">{position.asset_name}</p>
            </div>
          </div>
          <Badge variant="outline" className="text-sm">
            {portfolio.base_currency} Portfolio
          </Badge>
        </div>

        {/* Position Overview Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Quantity
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold font-mono">
                {formatCryptoQuantity(position.quantity)}
              </div>
              <p className="text-xs text-gray-500 mt-1">{position.symbol}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
                <DollarSign className="h-4 w-4" />
                Average Cost
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCurrency(position.average_cost, position.currency)}
              </div>
              <p className="text-xs text-gray-500 mt-1">per {position.symbol}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
                <TrendingUp className="h-4 w-4" />
                Current Price
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCurrency(position.current_price, position.currency)}
              </div>
              <p className="text-xs text-gray-500 mt-1">per {position.symbol}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Current Value
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCurrency(position.current_value, position.currency)}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Profit/Loss Card */}
        <Card>
          <CardHeader>
            <CardTitle>Profit & Loss</CardTitle>
            <CardDescription>
              Unrealized gains or losses for this position
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <p className="text-sm font-medium text-gray-600 mb-2">Cost Basis</p>
                <div className="text-xl font-bold">
                  {formatCurrency(position.cost_basis, position.currency)}
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600 mb-2">Unrealized Profit</p>
                <div className={`text-xl font-bold flex items-center gap-2 ${
                  isPositive ? 'text-success' : 'text-danger'
                }`}>
                  {isPositive ? (
                    <TrendingUp className="h-5 w-5" />
                  ) : (
                    <TrendingDown className="h-5 w-5" />
                  )}
                  {formatCurrency(position.unrealized_gain, position.currency)}
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-600 mb-2">Return</p>
                {returnPct !== null ? (
                  <Badge
                    variant={returnPct >= 0 ? 'default' : 'destructive'}
                    className="text-lg px-3 py-1"
                  >
                    {formatPercentage(returnPct)}
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-lg px-3 py-1">—</Badge>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recent Transactions */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Recent Transactions</CardTitle>
                <CardDescription>
                  Transaction history for {position.symbol}
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push(`/crypto/${portfolioId}/transactions`)}
              >
                View All Transactions
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {transactionsLoading ? (
              <div className="space-y-3">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-16 bg-gray-200 rounded animate-pulse"></div>
                ))}
              </div>
            ) : !transactionsData || transactionsData.items.length === 0 ? (
              <div className="text-center py-8">
                <Calendar className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  No transactions found
                </h3>
                <p className="text-gray-600">
                  No transactions for {position.symbol} in this portfolio
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead className="text-right">Quantity</TableHead>
                      <TableHead className="text-right">Price</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                      <TableHead className="text-right">Fee</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {transactionsData.items.map((tx) => (
                      <TableRow key={tx.id}>
                        <TableCell className="text-sm">
                          {formatDateTime(tx.timestamp)}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              tx.transaction_type === 'buy' || tx.transaction_type === 'transfer_in'
                                ? 'default'
                                : 'secondary'
                            }
                            className="text-xs"
                          >
                            {tx.transaction_type.replace('_', ' ').toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {formatCryptoQuantity(tx.quantity)}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {formatCurrency(tx.price_at_execution, tx.currency)}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {formatCurrency(tx.total_amount, tx.currency)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-gray-600">
                          {tx.fee > 0 ? formatCryptoQuantity(tx.fee) : '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
