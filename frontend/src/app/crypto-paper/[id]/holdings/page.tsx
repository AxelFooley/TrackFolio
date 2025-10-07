'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { CryptoHoldingsTable } from '@/components/CryptoPaper/CryptoHoldingsTable';
import { AddTransactionModal } from '@/components/CryptoPaper/AddTransactionModal';
import {
  ArrowLeft,
  Plus,
  RefreshCw,
  PieChart,
  TrendingUp,
  TrendingDown,
  ExternalLink,
  Wallet
} from 'lucide-react';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import {
  getCryptoPortfolio,
  getCryptoHoldings,
  getCryptoAssetAllocation,
  refreshCryptoPrices,
} from '@/lib/api/crypto-paper';
import type {
  CryptoPortfolio,
  CryptoHolding,
  CryptoAssetAllocation
} from '@/types/crypto-paper';

export default function CryptoHoldingsPage() {
  const params = useParams();
  const router = useRouter();
  const portfolioId = parseInt(params.id as string);

  const [portfolio, setPortfolio] = useState<CryptoPortfolio | null>(null);
  const [holdings, setHoldings] = useState<CryptoHolding[]>([]);
  const [assetAllocation, setAssetAllocation] = useState<CryptoAssetAllocation[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshingPrices, setIsRefreshingPrices] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load portfolio and holdings data on component mount
  useEffect(() => {
    if (!isNaN(portfolioId)) {
      loadData();
    }
  }, [portfolioId]);

  const loadData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const [portfolioData, holdingsData, allocationData] = await Promise.all([
        getCryptoPortfolio(portfolioId),
        getCryptoHoldings(portfolioId),
        getCryptoAssetAllocation(portfolioId),
      ]);

      setPortfolio(portfolioData);
      setHoldings(holdingsData);
      setAssetAllocation(allocationData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefreshPrices = async () => {
    try {
      setIsRefreshingPrices(true);
      await refreshCryptoPrices(portfolioId);
      // Reload all data after refresh
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh prices');
    } finally {
      setIsRefreshingPrices(false);
    }
  };

  const handleTransactionAdded = () => {
    // Reload data when a transaction is added
    loadData();
  };

  const openExternalLink = (symbol: string) => {
    // Open CoinGecko page for the crypto asset
    const url = `https://www.coingecko.com/en/coins/${symbol.toLowerCase()}`;
    window.open(url, '_blank');
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Button variant="outline" size="sm" disabled>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div className="h-8 w-64 bg-gray-200 rounded animate-pulse"></div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2">
            <Card>
              <CardContent className="p-6">
                <div className="h-96 bg-gray-200 rounded animate-pulse"></div>
              </CardContent>
            </Card>
          </div>
          <div>
            <Card>
              <CardContent className="p-6">
                <div className="h-96 bg-gray-200 rounded animate-pulse"></div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (error || !portfolio) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Button variant="outline" size="sm" onClick={() => router.push(`/crypto-paper/${portfolioId}`)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Portfolio
          </Button>
        </div>

        <Card>
          <CardContent className="p-6">
            <div className="text-center">
              <p className="text-red-600 font-medium">
                {error || 'Portfolio not found'}
              </p>
              <Button
                variant="outline"
                onClick={loadData}
                className="mt-4"
              >
                Retry
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const totalValue = portfolio.total_value_usd;
  const totalCost = portfolio.total_cost_usd;
  const totalProfit = portfolio.total_profit_usd;
  const isPositiveProfit = totalProfit >= 0;

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="sm" onClick={() => router.push(`/crypto-paper/${portfolioId}`)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Portfolio
          </Button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Holdings</h1>
            <p className="text-gray-600 mt-1">{portfolio.name}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <AddTransactionModal
            portfolioId={portfolio.id}
            onTransactionAdded={handleTransactionAdded}
          />
          <Button
            variant="outline"
            onClick={handleRefreshPrices}
            disabled={isRefreshingPrices}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshingPrices ? 'animate-spin' : ''}`} />
            {isRefreshingPrices ? 'Refreshing...' : 'Refresh Prices'}
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Value</p>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(totalValue, 'USD')}
                </p>
              </div>
              <Wallet className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Cost</p>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(totalCost, 'USD')}
                </p>
              </div>
              <div className="h-8 w-8 bg-gray-100 rounded-full flex items-center justify-center">
                <span className="text-sm font-bold text-gray-600">$</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total P&L</p>
                <p className={`text-2xl font-bold ${isPositiveProfit ? 'text-green-600' : 'text-red-600'}`}>
                  {isPositiveProfit ? '+' : ''}{formatCurrency(totalProfit, 'USD')}
                </p>
                <p className={`text-sm ${isPositiveProfit ? 'text-green-600' : 'text-red-600'}`}>
                  ({formatPercentage(portfolio.total_profit_pct)})
                </p>
              </div>
              {isPositiveProfit ? (
                <TrendingUp className="h-8 w-8 text-green-500" />
              ) : (
                <TrendingDown className="h-8 w-8 text-red-500" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Assets</p>
                <p className="text-2xl font-bold text-gray-900">
                  {holdings.length}
                </p>
              </div>
              <PieChart className="h-8 w-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Holdings Table */}
        <div className="lg:col-span-2">
          <CryptoHoldingsTable
            holdings={holdings}
            totalValue={totalValue}
          />
        </div>

        {/* Asset Allocation */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PieChart className="h-5 w-5" />
                Asset Allocation
              </CardTitle>
            </CardHeader>
            <CardContent>
              {assetAllocation.length > 0 ? (
                <div className="space-y-4">
                  {assetAllocation.map((asset, index) => (
                    <div key={asset.symbol} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{asset.symbol}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 w-6 p-0 hover:bg-blue-50"
                            onClick={() => openExternalLink(asset.symbol)}
                          >
                            <ExternalLink className="h-3 w-3" />
                          </Button>
                        </div>
                        <div className="text-right">
                          <div className="font-medium">{formatPercentage(asset.allocation_pct)}</div>
                          <div className="text-sm text-gray-600">
                            {formatCurrency(asset.value_usd, 'USD')}
                          </div>
                        </div>
                      </div>
                      <Progress value={asset.allocation_pct} className="h-2" />
                    </div>
                  ))}

                  {/* Summary */}
                  <div className="pt-4 border-t border-gray-200">
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Total Value:</span>
                        <span className="font-medium">
                          {formatCurrency(
                            assetAllocation.reduce((sum, asset) => sum + asset.value_usd, 0),
                            'USD'
                          )}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Assets:</span>
                        <span className="font-medium">{assetAllocation.length}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Largest Position:</span>
                        <span className="font-medium">
                          {assetAllocation.length > 0 && (
                            <>
                              {assetAllocation[0].symbol} ({formatPercentage(assetAllocation[0].allocation_pct)})
                            </>
                          )}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8">
                  <PieChart className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-500 mb-4">No holdings to display</p>
                  <AddTransactionModal
                    portfolioId={portfolio.id}
                    onTransactionAdded={handleTransactionAdded}
                    trigger={
                      <Button size="sm">
                        <Plus className="h-4 w-4 mr-2" />
                        Add First Transaction
                      </Button>
                    }
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Performance Summary */}
      {holdings.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Performance Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <h4 className="font-medium text-gray-900 mb-3">Best Performers</h4>
                <div className="space-y-2">
                  {holdings
                    .filter(h => h.unrealized_profit_pct > 0)
                    .sort((a, b) => b.unrealized_profit_pct - a.unrealized_profit_pct)
                    .slice(0, 3)
                    .map((holding) => (
                      <div key={holding.symbol} className="flex justify-between items-center">
                        <span className="text-sm font-medium">{holding.symbol}</span>
                        <span className="text-sm text-green-600 font-medium">
                          {formatPercentage(holding.unrealized_profit_pct)}
                        </span>
                      </div>
                    ))}
                  {holdings.filter(h => h.unrealized_profit_pct > 0).length === 0 && (
                    <p className="text-sm text-gray-500">No profitable holdings</p>
                  )}
                </div>
              </div>

              <div>
                <h4 className="font-medium text-gray-900 mb-3">Worst Performers</h4>
                <div className="space-y-2">
                  {holdings
                    .filter(h => h.unrealized_profit_pct < 0)
                    .sort((a, b) => a.unrealized_profit_pct - b.unrealized_profit_pct)
                    .slice(0, 3)
                    .map((holding) => (
                      <div key={holding.symbol} className="flex justify-between items-center">
                        <span className="text-sm font-medium">{holding.symbol}</span>
                        <span className="text-sm text-red-600 font-medium">
                          {formatPercentage(holding.unrealized_profit_pct)}
                        </span>
                      </div>
                    ))}
                  {holdings.filter(h => h.unrealized_profit_pct < 0).length === 0 && (
                    <p className="text-sm text-gray-500">No losing holdings</p>
                  )}
                </div>
              </div>

              <div>
                <h4 className="font-medium text-gray-900 mb-3">Largest Positions</h4>
                <div className="space-y-2">
                  {holdings
                    .sort((a, b) => b.current_value_usd - a.current_value_usd)
                    .slice(0, 3)
                    .map((holding) => (
                      <div key={holding.symbol} className="flex justify-between items-center">
                        <span className="text-sm font-medium">{holding.symbol}</span>
                        <span className="text-sm font-medium">
                          {formatCurrency(holding.current_value_usd, 'USD')}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}