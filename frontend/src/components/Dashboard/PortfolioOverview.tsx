'use client';

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useUnifiedOverview } from '@/hooks/usePortfolio';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import { TrendingUp, TrendingDown, DollarSign, Activity, PieChart, RefreshCw } from 'lucide-react';

/**
 * Renders a unified portfolio overview panel showing current value, total profit, and today's change.
 * Includes combined metrics from traditional and crypto holdings.
 *
 * Shows loading skeletons while data is loading and an error message when the overview cannot be loaded.
 *
 * @returns The React element containing the portfolio overview UI.
 */
export function PortfolioOverview() {
  const { data: overview, isLoading, isFetching, error } = useUnifiedOverview();

  // Calculate allocation percentages
  const allocation = useMemo(() => {
    if (!overview) return null;

    const totalValue = overview.total_value;
    if (totalValue === 0) return null;

    return {
      traditionalpct: (overview.traditional_value / totalValue) * 100,
      cryptoPct: (overview.crypto_value / totalValue) * 100,
    };
  }, [overview]);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <div className="h-4 bg-gray-200 rounded animate-pulse w-24"></div>
            </CardHeader>
            <CardContent>
              <div className="h-8 bg-gray-200 rounded animate-pulse w-32 mb-2"></div>
              <div className="h-4 bg-gray-200 rounded animate-pulse w-16"></div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (error || !overview) {
    return (
      <div className="text-center py-8 text-red-600">
        {error?.message ? `Error: ${error.message}` : 'Failed to load portfolio overview'}
      </div>
    );
  }

  const metrics = [
    {
      title: 'Current Value',
      value: formatCurrency(overview.total_value, overview.currency || 'EUR'),
      subtitle: allocation ? `Traditional: ${formatCurrency(overview.traditional_value, overview.currency || 'EUR')} | Crypto: ${formatCurrency(overview.crypto_value, overview.currency || 'EUR')}` : undefined,
      icon: DollarSign,
      color: 'text-blue-600',
    },
    {
      title: 'Total Profit',
      value: formatCurrency(overview.total_profit, overview.currency || 'EUR'),
      change: formatPercentage(overview.total_profit_pct),
      icon: overview.total_profit >= 0 ? TrendingUp : TrendingDown,
      color: overview.total_profit >= 0 ? 'text-success' : 'text-danger',
    },
    {
      title: 'Asset Breakdown',
      value: allocation ? `${allocation.traditionalpct.toFixed(1)}% / ${allocation.cryptoPct.toFixed(1)}%` : '—',
      subtitle: allocation ? 'Traditional / Crypto' : undefined,
      icon: PieChart,
      color: 'text-purple-600',
    },
    {
      title: "Today's Change",
      value: overview.today_change !== null && overview.today_change !== undefined
        ? formatCurrency(overview.today_change, overview.currency || 'EUR')
        : '—',
      change: overview.today_change_pct !== null && overview.today_change_pct !== undefined
        ? formatPercentage(overview.today_change_pct)
        : undefined,
      icon: (overview.today_change ?? 0) >= 0 ? TrendingUp : TrendingDown,
      color: (overview.today_change ?? 0) >= 0 ? 'text-success' : 'text-danger',
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <Card
              key={metric.title}
              className={`relative transition-all ${
                isFetching && !isLoading ? 'border-blue-300 border-2' : ''
              }`}
            >
              {/* Subtle loading indicator when refetching cached data */}
              {isFetching && !isLoading && (
                <div className="absolute top-2 right-2 text-blue-400 animate-spin">
                  <RefreshCw className="h-4 w-4" />
                </div>
              )}
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
                  {metric.title}
                </CardTitle>
                <Icon className={`h-4 w-4 ${metric.color}`} />
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${metric.color}`}>
                  {metric.value}
                </div>
                {metric.subtitle && (
                  <p className="text-xs text-gray-500 mt-1">{metric.subtitle}</p>
                )}
                {metric.change && (
                  <p className="text-xs text-gray-600 mt-1">{metric.change}</p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
