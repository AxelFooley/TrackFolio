'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useUnifiedPerformance } from '@/hooks/usePortfolio';
import { useBenchmark } from '@/hooks/useBenchmark';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { formatCurrency, formatChartDate, formatDate } from '@/lib/utils';
import type { TimeRange } from '@/lib/types';
import { AlertCircle, RefreshCw } from 'lucide-react';

const timeRanges: TimeRange[] = ['1D', '1W', '1M', '3M', '6M', '1Y', 'YTD', 'ALL'];

/**
 * Render the unified portfolio performance chart showing combined traditional and crypto performance.
 * Displays range selection controls, handles loading, error, and no-data states,
 * and optionally overlays benchmark data.
 *
 * @returns A JSX element that displays the Performance card with range buttons, status UIs, and a responsive chart
 */
export function PerformanceChart() {
  const [selectedRange, setSelectedRange] = useState<TimeRange>('1Y');
  const { data: performanceData, isLoading, error, refetch } = useUnifiedPerformance(selectedRange);
  const { data: benchmark } = useBenchmark();

  // Error state
  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Performance</CardTitle>
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
                  There was an error loading the chart data. Please try again.
                </p>
                <div className="mt-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => refetch()}
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
            <CardTitle>Performance</CardTitle>
            <div className="flex gap-1">
              {timeRanges.map((range) => (
                <Button
                  key={range}
                  variant={selectedRange === range ? 'default' : 'outline'}
                  size="sm"
                  disabled
                >
                  {range}
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

  // No data state
  if (!performanceData || performanceData.length === 0) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Performance</CardTitle>
            <div className="flex gap-1">
              {timeRanges.map((range) => (
                <Button
                  key={range}
                  variant={selectedRange === range ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSelectedRange(range)}
                >
                  {range}
                </Button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <p className="text-gray-600 font-medium mb-2">No historical data available</p>
            <p className="text-sm text-gray-500 mb-1">
              Historical performance data will appear here after you:
            </p>
            <ol className="text-sm text-gray-500 list-decimal list-inside space-y-1 mt-3">
              <li>Import your transactions</li>
              <li>Run the price backfill script to populate historical snapshots</li>
              <li>Wait for daily snapshots to accumulate over time</li>
            </ol>
            <p className="text-xs text-gray-400 mt-4">
              Note: The backfill script creates historical snapshots based on your transaction history.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Transform data for Recharts
  const chartData = performanceData.map((point) => ({
    date: point.date,
    total: point.total,
    traditional: point.traditional,
    crypto: point.crypto,
    ...(point.benchmark != null && { benchmark: point.benchmark }),
  }));

  const hasBenchmarkData = chartData.some(point => point.benchmark != null);
  const isSinglePoint = chartData.length === 1;
  const portfolioCurrency = 'EUR';

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Performance (Combined)</CardTitle>
          <div className="flex gap-1">
            {timeRanges.map((range) => (
              <Button
                key={range}
                variant={selectedRange === range ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedRange(range)}
              >
                {range}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isSinglePoint ? (
          <div className="h-96 flex items-center justify-center">
            <div className="text-center">
              <p className="text-gray-600 font-medium mb-4">Single Data Point</p>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Total</p>
                  <p className="text-lg font-semibold text-blue-600">
                    {formatCurrency(chartData[0].total, portfolioCurrency)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Traditional</p>
                  <p className="text-lg font-semibold text-gray-600">
                    {formatCurrency(chartData[0].traditional, portfolioCurrency)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Crypto</p>
                  <p className="text-lg font-semibold text-orange-600">
                    {formatCurrency(chartData[0].crypto, portfolioCurrency)}
                  </p>
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-4">
                More data points will appear as your portfolio is tracked over time.
              </p>
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorTraditional" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorCrypto" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#F97316" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#F97316" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => formatChartDate(value, selectedRange)}
              />
              <YAxis
                yAxisId="left"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => formatCurrency(value, portfolioCurrency)}
                width={80}
              />
              {hasBenchmarkData && (
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fontSize: 12 }}
                  tickFormatter={(value) => formatCurrency(value, portfolioCurrency)}
                  width={80}
                />
              )}
              <Tooltip
                formatter={(value: number) => formatCurrency(value, portfolioCurrency)}
                labelFormatter={(label) => formatDate(label)}
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px',
                }}
              />
              <Legend />
              <Area
                type="monotone"
                dataKey="traditional"
                stroke="#3B82F6"
                fill="url(#colorTraditional)"
                name="Traditional"
                yAxisId="left"
                animationDuration={500}
              />
              <Area
                type="monotone"
                dataKey="crypto"
                stroke="#F97316"
                fill="url(#colorCrypto)"
                name="Crypto"
                yAxisId="left"
                animationDuration={500}
              />
              <Line
                type="monotone"
                dataKey="total"
                stroke="#1F2937"
                strokeWidth={3}
                dot={chartData.length <= 30}
                name="Total Portfolio"
                yAxisId="left"
                animationDuration={500}
              />
              {hasBenchmarkData && (
                <Line
                  type="monotone"
                  dataKey="benchmark"
                  stroke="#9CA3AF"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={chartData.length <= 30}
                  connectNulls={true}
                  name="Benchmark"
                  yAxisId="right"
                  animationDuration={500}
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
