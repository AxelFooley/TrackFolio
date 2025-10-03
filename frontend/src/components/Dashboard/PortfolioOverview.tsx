'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { usePortfolioOverview } from '@/hooks/usePortfolio';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import { TrendingUp, TrendingDown, DollarSign, Target } from 'lucide-react';

export function PortfolioOverview() {
  const { data: overview, isLoading, error } = usePortfolioOverview();

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

  // Calculate profit percentage from values
  const profitPercent = overview.total_cost_basis > 0
    ? ((overview.total_profit / overview.total_cost_basis) * 100)
    : 0;

  const metrics = [
    {
      title: 'Current Value',
      value: formatCurrency(overview.current_value, overview.currency || 'EUR'),
      icon: DollarSign,
      color: 'text-blue-600',
    },
    {
      title: 'Total Profit',
      value: formatCurrency(overview.total_profit, overview.currency || 'EUR'),
      change: formatPercentage(profitPercent),
      icon: overview.total_profit >= 0 ? TrendingUp : TrendingDown,
      color: overview.total_profit >= 0 ? 'text-success' : 'text-danger',
    },
    {
      title: 'Avg Annual Return',
      value: overview.average_annual_return !== null && overview.average_annual_return !== undefined
        ? formatPercentage(overview.average_annual_return * 100)
        : '—',
      icon: Target,
      color: (overview.average_annual_return ?? 0) >= 0 ? 'text-success' : 'text-danger',
    },
    {
      title: "Today's Change",
      value: overview.today_gain_loss !== null && overview.today_gain_loss !== undefined
        ? formatCurrency(overview.today_gain_loss, overview.currency || 'EUR')
        : '—',
      change: overview.today_gain_loss_pct !== null && overview.today_gain_loss_pct !== undefined
        ? formatPercentage(overview.today_gain_loss_pct * 100)
        : undefined,
      icon: (overview.today_gain_loss ?? 0) >= 0 ? TrendingUp : TrendingDown,
      color: (overview.today_gain_loss ?? 0) >= 0 ? 'text-success' : 'text-danger',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <Card key={metric.title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                {metric.title}
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
  );
}
