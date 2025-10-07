'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { formatCurrency, formatChartDate, formatDate, formatPercentage } from '@/lib/utils';
import { TrendingUp, TrendingDown, AlertCircle, RefreshCw } from 'lucide-react';
import type { CryptoPortfolioPerformance } from '@/types/crypto-paper';

interface CryptoPriceChartProps {
  portfolioId: number;
  data: CryptoPortfolioPerformance | null;
  isLoading: boolean;
  error: Error | null;
  onRefresh?: () => void;
  onRangeChange?: (days: number) => void;
}

const timeRanges = [
  { label: '1D', days: 1 },
  { label: '1W', days: 7 },
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
  { label: 'ALL', days: 0 }, // 0 means all available data
];

export function CryptoPriceChart({
  portfolioId,
  data,
  isLoading,
  error,
  onRefresh,
  onRangeChange
}: CryptoPriceChartProps) {
  const [selectedRange, setSelectedRange] = useState(timeRanges[5]); // Default to 1Y

  const handleRangeChange = (range: typeof timeRanges[0]) => {
    setSelectedRange(range);
    onRangeChange?.(range.days);
  };

  // Error state
  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Portfolio Performance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-start">
              <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
              <div className="ml-3 flex-1">
                <h3 className="text-sm font-medium text-red-800">
                  Failed to load performance data
                </h3>
                <p className="mt-1 text-sm text-red-700">
                  {error.message || 'There was an error loading the chart data. Please try again.'}
                </p>
                <div className="mt-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onRefresh?.()}
                    className="text-red-700 border-red-300 hover:bg-red-100"
                  >
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Retry
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Portfolio Performance</CardTitle>
            <div className="flex gap-1">
              {timeRanges.map((range) => (
                <Button
                  key={range.label}
                  variant={selectedRange.label === range.label ? 'default' : 'outline'}
                  size="sm"
                  disabled
                >
                  {range.label}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-96 bg-gray-100 rounded animate-pulse"></div>
        </CardContent>
      </Card>
    );
  }

  // Check if we have performance data
  const hasData = data?.portfolio_data && data.portfolio_data.length > 0;

  if (!hasData) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Portfolio Performance</CardTitle>
            <div className="flex gap-1">
              {timeRanges.map((range) => (
                <Button
                  key={range.label}
                  variant={selectedRange.label === range.label ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => handleRangeChange(range)}
                >
                  {range.label}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <p className="text-gray-600 font-medium mb-2">No historical data available</p>
            <p className="text-sm text-gray-500">
              Historical performance data will appear here after you add transactions and they are processed.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Transform data for Recharts with safety checks
  const chartData = (data?.portfolio_data || []).map((point) => ({
    date: point.date,
    value: Number(point.value_usd || 0),
  }));

  // Determine if we have a single data point
  const isSinglePoint = chartData.length === 1;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            Portfolio Performance
            {data?.change_pct !== 0 && data?.change_pct !== undefined && (
              <div className={`flex items-center gap-1 text-sm font-normal ${
                (data?.change_pct || 0) > 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {(data?.change_pct || 0) > 0 ? (
                  <TrendingUp className="h-4 w-4" />
                ) : (
                  <TrendingDown className="h-4 w-4" />
                )}
                {formatPercentage(data?.change_pct)}
              </div>
            )}
          </CardTitle>
          <div className="flex gap-1">
            {timeRanges.map((range) => (
              <Button
                key={range.label}
                variant={selectedRange.label === range.label ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleRangeChange(range)}
              >
                {range.label}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Performance Metrics Display */}
        {data?.start_value !== undefined && data?.end_value !== undefined && (
          <div className="mb-6 flex flex-wrap gap-4 pb-4 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-600">Portfolio Value:</span>
              <span className="text-sm font-mono">
                {formatCurrency(data.start_value, 'USD')}
              </span>
              <span className="text-gray-400">→</span>
              <span className="text-sm font-mono">
                {formatCurrency(data.end_value, 'USD')}
              </span>
              <span
                className={`text-sm font-semibold ml-1 ${
                  (data?.change_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                }`}
              >
                ({(data?.change_pct || 0) >= 0 ? '+' : ''}{formatCurrency(data?.change_amount, 'USD')} | {formatPercentage(data?.change_pct)})
              </span>
            </div>
          </div>
        )}

        {isSinglePoint ? (
          <div className="h-96 flex items-center justify-center">
            <div className="text-center">
              <p className="text-gray-600 font-medium mb-2">Single Data Point</p>
              <p className="text-sm text-gray-500">
                Portfolio Value: {formatCurrency(chartData[0].value, 'USD')}
              </p>
              <p className="text-xs text-gray-400 mt-2">
                More data points will appear as your portfolio is tracked over time.
              </p>
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => formatChartDate(value, selectedRange.label as any)}
              />
              <YAxis
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => formatCurrency(value, 'USD')}
                width={80}
              />
              <Tooltip
                formatter={(value: number) => formatCurrency(value, 'USD')}
                labelFormatter={(label) => formatDate(label)}
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px',
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#3B82F6"
                strokeWidth={2}
                dot={chartData.length <= 30}
                name="Portfolio Value"
                animationDuration={500}
              />
            </LineChart>
          </ResponsiveContainer>
        )}

        {/* Chart Footer */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="flex justify-between items-center text-xs text-gray-500">
            <span>
              {chartData.length} data points
            </span>
            <span>
              {chartData.length > 0 && (
                <>
                  From: {formatDate(chartData[0].date)} - To: {formatDate(chartData[chartData.length - 1].date)}
                </>
              )}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}