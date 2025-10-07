'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CryptoHoldingsTable } from '@/components/CryptoPaper/CryptoHoldingsTable';
import { CryptoTransactionTable } from '@/components/CryptoPaper/CryptoTransactionTable';
import { CryptoPriceChart } from '@/components/CryptoPaper/CryptoPriceChart';
import { AddTransactionModal } from '@/components/CryptoPaper/AddTransactionModal';
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  ArrowLeft,
  Plus,
  RefreshCw,
  Activity,
  PieChart,
  History,
  Eye
} from 'lucide-react';
import { formatCurrency, formatPercentage, formatDate } from '@/lib/utils';
import {
  getCryptoPortfolio,
  getCryptoHoldings,
  getCryptoTransactions,
  getCryptoPortfolioPerformance,
  refreshCryptoPrices,
} from '@/lib/api/crypto-paper';
import type {
  CryptoPortfolio,
  CryptoHolding,
  CryptoTransaction,
  CryptoPortfolioPerformance
} from '@/types/crypto-paper';

export default function CryptoPortfolioDetailPage() {
  const params = useParams();
  const router = useRouter();
  const portfolioId = parseInt(params.id as string);

  const [portfolio, setPortfolio] = useState<CryptoPortfolio | null>(null);
  const [holdings, setHoldings] = useState<CryptoHolding[]>([]);
  const [transactions, setTransactions] = useState<CryptoTransaction[]>([]);
  const [performanceData, setPerformanceData] = useState<CryptoPortfolioPerformance | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshingPrices, setIsRefreshingPrices] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState('overview');
  const [performanceDays, setPerformanceDays] = useState(365); // Default to 1 year

  // Load portfolio data on component mount
  useEffect(() => {
    if (!isNaN(portfolioId)) {
      loadPortfolioData();
    }
  }, [portfolioId]);

  const loadPortfolioData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Load all data in parallel
      const [portfolioData, holdingsData, transactionsData, performanceData] = await Promise.all([
        getCryptoPortfolio(portfolioId),
        getCryptoHoldings(portfolioId),
        getCryptoTransactions(portfolioId),
        getCryptoPortfolioPerformance(portfolioId, { days: performanceDays }),
      ]);

      setPortfolio(portfolioData);
      setHoldings(holdingsData);
      setTransactions(transactionsData);
      setPerformanceData(performanceData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load portfolio data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefreshPrices = async () => {
    try {
      setIsRefreshingPrices(true);
      await refreshCryptoPrices(portfolioId);
      // Reload all data after refresh
      await loadPortfolioData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh prices');
    } finally {
      setIsRefreshingPrices(false);
    }
  };

  const handleTransactionAdded = () => {
    // Reload data when a transaction is added
    loadPortfolioData();
  };

  const handlePerformanceRangeChange = (days: number) => {
    setPerformanceDays(days);
    // Reload performance data with new range
    getCryptoPortfolioPerformance(portfolioId, { days })
      .then(setPerformanceData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load performance data'));
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

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-20 bg-gray-200 rounded animate-pulse"></div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card>
          <CardContent className="p-6">
            <div className="h-96 bg-gray-200 rounded animate-pulse"></div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error || !portfolio) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Button variant="outline" size="sm" onClick={() => router.push('/crypto-paper')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Portfolios
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
                onClick={loadPortfolioData}
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

  const isPositiveProfit = portfolio.total_profit_usd >= 0;
  const isPositiveIRR = portfolio.irr >= 0;

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="sm" onClick={() => router.push('/crypto-paper')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{portfolio.name}</h1>
            {portfolio.description && (
              <p className="text-gray-600 mt-1">{portfolio.description}</p>
            )}
            <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
              <span>Created: {formatDate(portfolio.created_at)}</span>
              <span>Updated: {formatDate(portfolio.updated_at)}</span>
            </div>
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
                <p className="text-sm font-medium text-gray-600">Current Value</p>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(portfolio.total_value_usd, 'USD')}
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
                  {formatCurrency(portfolio.total_cost_usd, 'USD')}
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
                  {isPositiveProfit ? '+' : ''}{formatCurrency(portfolio.total_profit_usd, 'USD')}
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
                <p className="text-sm font-medium text-gray-600">IRR</p>
                <p className={`text-2xl font-bold ${isPositiveIRR ? 'text-green-600' : 'text-red-600'}`}>
                  {formatPercentage(portfolio.irr)}
                </p>
              </div>
              <Activity className="h-8 w-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <Eye className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="holdings" className="flex items-center gap-2">
            <PieChart className="h-4 w-4" />
            Holdings
          </TabsTrigger>
          <TabsTrigger value="transactions" className="flex items-center gap-2">
            <History className="h-4 w-4" />
            Transactions
          </TabsTrigger>
          <TabsTrigger value="performance" className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Performance
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Holdings */}
            <Card>
              <CardHeader>
                <CardTitle>Top Holdings</CardTitle>
              </CardHeader>
              <CardContent>
                {holdings.length > 0 ? (
                  <div className="space-y-4">
                    {holdings.slice(0, 5).map((holding) => (
                      <div key={holding.symbol} className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">{holding.symbol}</p>
                          <p className="text-sm text-gray-600">
                            {holding.quantity} @ {formatCurrency(holding.current_price_usd, 'USD')}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="font-medium">{formatCurrency(holding.current_value_usd, 'USD')}</p>
                          <p className={`text-sm ${
                            holding.unrealized_profit_usd >= 0 ? 'text-green-600' : 'text-red-600'
                          }`}>
                            {formatPercentage(holding.unrealized_profit_pct)}
                          </p>
                        </div>
                      </div>
                    ))}
                    {holdings.length > 5 && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setActiveTab('holdings')}
                        className="w-full mt-2"
                      >
                        View All Holdings ({holdings.length})
                      </Button>
                    )}
                  </div>
                ) : (
                  <p className="text-gray-500 text-center py-4">No holdings yet</p>
                )}
              </CardContent>
            </Card>

            {/* Recent Transactions */}
            <Card>
              <CardHeader>
                <CardTitle>Recent Transactions</CardTitle>
              </CardHeader>
              <CardContent>
                {transactions.length > 0 ? (
                  <div className="space-y-4">
                    {transactions.slice(0, 5).map((transaction) => (
                      <div key={transaction.id} className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">{transaction.symbol}</p>
                          <p className="text-sm text-gray-600">
                            {transaction.transaction_type} • {formatDate(transaction.transaction_date)}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="font-medium">{formatCurrency(transaction.total_usd, 'USD')}</p>
                          <p className="text-sm text-gray-600">
                            {transaction.quantity} @ {formatCurrency(transaction.price_usd, 'USD')}
                          </p>
                        </div>
                      </div>
                    ))}
                    {transactions.length > 5 && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setActiveTab('transactions')}
                        className="w-full mt-2"
                      >
                        View All Transactions ({transactions.length})
                      </Button>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <p className="text-gray-500 mb-2">No transactions yet</p>
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
        </TabsContent>

        <TabsContent value="holdings" className="mt-6">
          <CryptoHoldingsTable
            holdings={holdings}
            totalValue={portfolio.total_value_usd}
          />
        </TabsContent>

        <TabsContent value="transactions" className="mt-6">
          <CryptoTransactionTable
            transactions={transactions || []}
            onTransactionAdded={handleTransactionAdded}
          />
        </TabsContent>

        <TabsContent value="performance" className="mt-6">
          <CryptoPriceChart
            portfolioId={portfolio.id}
            data={performanceData}
            isLoading={false}
            error={error ? new Error(error) : null}
            onRefresh={loadPortfolioData}
            onRangeChange={handlePerformanceRangeChange}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}