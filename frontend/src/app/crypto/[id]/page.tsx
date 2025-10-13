'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useCryptoPortfolio, useCryptoPortfolioMetrics, useCryptoHoldings, useRefreshCryptoPrices } from '@/hooks/useCrypto';
import { formatCurrency, formatPercentage, formatDate } from '@/lib/utils';
import { Bitcoin, TrendingUp, TrendingDown, ArrowLeft, RefreshCw, Eye, Plus } from 'lucide-react';
import { CryptoHoldingsTable } from '@/components/Crypto/CryptoHoldingsTable';
import { CryptoPriceChart } from '@/components/Crypto/CryptoPriceChart';
import { WalletSync } from '@/components/Crypto/WalletSync';
import { useToast } from '@/hooks/use-toast';

/**
 * Render the detailed view for a cryptocurrency portfolio, including overview metrics, a performance chart with selectable time ranges, portfolio metrics (best/worst performer and largest position), optional wallet sync, and a holdings table.
 *
 * Fetches portfolio, metrics, and holdings data for the ID from route params; exposes a refresh action that updates live prices and shows success or error toasts, and provides navigation actions for adding transactions and viewing holdings.
 *
 * @returns The React element for the crypto portfolio detail page.
 */
export default function CryptoPortfolioDetailPage() {
  const params = useParams();
  const router = useRouter();
  const portfolioId = parseInt(params.id as string);

  const { data: portfolio, isLoading: portfolioLoading } = useCryptoPortfolio(portfolioId);
  const { data: metrics, isLoading: metricsLoading } = useCryptoPortfolioMetrics(portfolioId);
  const { data: holdings, isLoading: holdingsLoading } = useCryptoHoldings(portfolioId);
  const refreshPricesMutation = useRefreshCryptoPrices();
  const { toast } = useToast();

  const [selectedTimeRange, setSelectedTimeRange] = useState('1M');

  const handleRefreshPrices = async () => {
    try {
      await refreshPricesMutation.mutateAsync(portfolioId);
      toast({
        title: 'Prices Refreshed',
        description: 'All crypto prices have been updated',
      });
    } catch (error: any) {
      toast({
        title: 'Refresh Failed',
        description: error.message || 'Failed to refresh prices',
        variant: 'destructive',
      });
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

  const totalValue = portfolio.base_currency === 'USD' ? portfolio.total_value_usd : portfolio.total_value_eur;
  const totalProfit = portfolio.base_currency === 'USD' ? portfolio.total_profit_usd : portfolio.total_profit_eur;
  const profitPercentage = portfolio.base_currency === 'USD' ? portfolio.profit_percentage_usd : portfolio.profit_percentage_eur;

  const currency = portfolio.base_currency;
  const isPositive = (totalProfit || 0) >= 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => router.back()}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-3">
                <Bitcoin className="h-8 w-8 text-orange-500" />
                {portfolio.name}
              </h1>
              {portfolio.description && (
                <p className="text-gray-600 mt-1">{portfolio.description}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="text-sm">
              {currency} Portfolio
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefreshPrices}
              disabled={refreshPricesMutation.isPending}
            >
              {refreshPricesMutation.isPending ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Refreshing...
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Refresh Prices
                </>
              )}
            </Button>
            <Button onClick={() => router.push(`/crypto/${portfolioId}/transactions`)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Transaction
            </Button>
          </div>
        </div>

        {/* Portfolio Overview Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Total Value
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCurrency(totalValue, currency)}
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
              <div className={`text-2xl font-bold ${isPositive ? 'text-success' : 'text-danger'}`}>
                {formatCurrency(totalProfit, currency)}
              </div>
              {profitPercentage !== null && profitPercentage !== undefined && (
                <p className="text-xs text-gray-600 mt-1">
                  {formatPercentage(profitPercentage)}
                </p>
              )}
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

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                Last Updated
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-sm font-medium">
                {formatDate(portfolio.updated_at, 'MMM dd, HH:mm')}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Performance Chart */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Portfolio Performance</CardTitle>
                <CardDescription>
                  Portfolio value over time
                </CardDescription>
              </div>
              <div className="flex gap-1">
                {['1D', '1W', '1M', '3M', '6M', '1Y', 'ALL'].map((range) => (
                  <Button
                    key={range}
                    variant={selectedTimeRange === range ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setSelectedTimeRange(range)}
                  >
                    {range}
                  </Button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <CryptoPriceChart portfolioId={portfolioId} timeRange={selectedTimeRange} />
          </CardContent>
        </Card>

        {/* Portfolio Metrics */}
        {metrics && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-gray-600">
                  Best Performer
                </CardTitle>
              </CardHeader>
              <CardContent>
                {metrics.best_performer ? (
                  <div>
                    <p className="font-semibold">{metrics.best_performer.symbol}</p>
                    <p className="text-sm text-gray-600">{metrics.best_performer.asset_name}</p>
                    <p className="text-sm text-success">
                      {formatPercentage(metrics.best_performer.return_percentage)}
                    </p>
                  </div>
                ) : (
                  <p className="text-gray-500">No data available</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-gray-600">
                  Worst Performer
                </CardTitle>
              </CardHeader>
              <CardContent>
                {metrics.worst_performer ? (
                  <div>
                    <p className="font-semibold">{metrics.worst_performer.symbol}</p>
                    <p className="text-sm text-gray-600">{metrics.worst_performer.asset_name}</p>
                    <p className="text-sm text-danger">
                      {formatPercentage(metrics.worst_performer.return_percentage)}
                    </p>
                  </div>
                ) : (
                  <p className="text-gray-500">No data available</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-gray-600">
                  Largest Position
                </CardTitle>
              </CardHeader>
              <CardContent>
                {metrics.largest_position ? (
                  <div>
                    <p className="font-semibold">{metrics.largest_position.symbol}</p>
                    <p className="text-sm text-gray-600">{metrics.largest_position.asset_name}</p>
                    <p className="text-sm">
                      {formatCurrency(metrics.largest_position.current_value, currency)}
                    </p>
                  </div>
                ) : (
                  <p className="text-gray-500">No data available</p>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Wallet Sync Section */}
        {portfolio.wallet_address && (
          <WalletSync portfolioId={portfolioId} walletAddress={portfolio.wallet_address} />
        )}

        {/* Holdings Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Holdings</CardTitle>
                <CardDescription>
                  Your cryptocurrency positions
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push(`/crypto/${portfolioId}/holdings`)}
              >
                <Eye className="h-4 w-4 mr-2" />
                View Details
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <CryptoHoldingsTable portfolioId={portfolioId} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}