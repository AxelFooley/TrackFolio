'use client';

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { usePortfolioOverview, useHoldings } from '@/hooks/usePortfolio';
import { useRealtimePrices } from '@/hooks/useRealtimePrices';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import { TrendingUp, TrendingDown, DollarSign, Target, Activity } from 'lucide-react';

/**
 * Renders a portfolio overview panel showing current value, total profit, average annual return, and today's change, and displays a live-price update indicator when real-time data is available.
 *
 * Shows loading skeletons while data is loading and an error message when the overview cannot be loaded.
 *
 * @returns The React element containing the portfolio overview UI.
 */
export function PortfolioOverview() {
  const { data: overview, isLoading, error } = usePortfolioOverview();
  const { data: holdings } = useHoldings();
  const symbols = (holdings && Array.isArray(holdings)) ? holdings.map(h => h.ticker) : [];
  const { realtimePrices, isLoading: pricesLoading, lastUpdate } = useRealtimePrices(symbols);

  // Calculate real-time portfolio metrics
  const realtimeMetrics = useMemo(() => {
    if (!holdings || !overview || !Array.isArray(holdings)) return null;

    let totalCurrentValue = 0;
    let totalPreviousValue = 0;
    let hasRealtimeData = false;

    // Use safer array iteration
    holdings.forEach((holding) => {
      if (!holding || typeof holding !== 'object') return;

      const realtimePrice = realtimePrices.get(holding.ticker);

      if (realtimePrice) {
        hasRealtimeData = true;
        const currentValue = holding.quantity * realtimePrice.current_price;
        const previousValue = holding.quantity * realtimePrice.previous_close;
        totalCurrentValue += currentValue;
        totalPreviousValue += previousValue;
      } else {
        // Fallbacks when no real-time data
        const curr = holding.current_value ?? 0;
        // Calculate previous value from today's change: previous = current - change
        const prev = holding.today_change != null ? curr - holding.today_change : curr;
        totalCurrentValue += curr;
        totalPreviousValue += prev;
      }
    });

    if (!hasRealtimeData) return null;

    const totalProfit = totalCurrentValue - overview.total_cost_basis;
    const profitPercent = overview.total_cost_basis > 0
      ? (totalProfit / overview.total_cost_basis) * 100
      : 0;

    const todayGainLoss = totalCurrentValue - totalPreviousValue;
    const todayGainLossPct = totalPreviousValue > 0
      ? (todayGainLoss / totalPreviousValue) * 100
      : 0;

    return {
      currentValue: totalCurrentValue,
      totalProfit,
      profitPercent,
      todayGainLoss,
      todayGainLossPct,
    };
  }, [holdings, realtimePrices, overview]);

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
        Failed to load portfolio overview
      </div>
    );
  }

  // Use real-time metrics if available, otherwise fall back to overview data
  const currentValue = realtimeMetrics?.currentValue ?? overview.current_value;
  const totalProfit = realtimeMetrics?.totalProfit ?? overview.total_profit;
  const profitPercent = realtimeMetrics?.profitPercent ?? (
    overview.total_cost_basis > 0
      ? ((overview.total_profit / overview.total_cost_basis) * 100)
      : 0
  );
  const todayGainLoss = realtimeMetrics?.todayGainLoss ?? overview.today_gain_loss;
  const todayGainLossPct = realtimeMetrics?.todayGainLossPct ?? overview.today_gain_loss_pct;

  const metrics = [
    {
      title: 'Current Value',
      value: formatCurrency(currentValue, overview.currency || 'EUR'),
      icon: DollarSign,
      color: 'text-blue-600',
      hasLiveData: !!realtimeMetrics,
    },
    {
      title: 'Total Profit',
      value: formatCurrency(totalProfit, overview.currency || 'EUR'),
      change: formatPercentage(profitPercent),
      icon: totalProfit >= 0 ? TrendingUp : TrendingDown,
      color: totalProfit >= 0 ? 'text-success' : 'text-danger',
      hasLiveData: !!realtimeMetrics,
    },
    {
      title: 'Avg Annual Return',
      value: overview.average_annual_return !== null && overview.average_annual_return !== undefined
        ? formatPercentage(overview.average_annual_return * 100)
        : '—',
      icon: Target,
      color: (overview.average_annual_return ?? 0) >= 0 ? 'text-success' : 'text-danger',
      hasLiveData: false,
    },
    {
      title: "Today's Change",
      value: todayGainLoss !== null && todayGainLoss !== undefined
        ? formatCurrency(todayGainLoss, overview.currency || 'EUR')
        : '—',
      change: todayGainLossPct !== null && todayGainLossPct !== undefined
        ? formatPercentage(todayGainLossPct)
        : undefined,
      icon: (todayGainLoss ?? 0) >= 0 ? TrendingUp : TrendingDown,
      color: (todayGainLoss ?? 0) >= 0 ? 'text-success' : 'text-danger',
      hasLiveData: !!realtimeMetrics,
    },
  ];

  return (
    <div className="space-y-4">
      {!pricesLoading && lastUpdate && realtimeMetrics && (
        <div className="flex items-center justify-end">
          <Badge variant="outline" className="gap-1.5">
            <Activity className="h-3 w-3 animate-pulse text-green-500" />
            <span className="text-xs text-gray-500">
              Live prices - Updated {lastUpdate.toLocaleTimeString()}
            </span>
          </Badge>
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <Card key={metric.title}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-gray-600 flex items-center gap-2">
                  {metric.title}
                  {metric.hasLiveData && (
                    <span className="inline-block h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                  )}
                </CardTitle>
                <Icon className={`h-4 w-4 ${metric.color}`} />
              </CardHeader>
              <CardContent>
                <div className={`text-2xl font-bold ${metric.color}`}>
                  {metric.value}
                </div>
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