'use client';

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { useCryptoPerformanceData } from '@/hooks/useCrypto';
import { formatCurrency, formatDate } from '@/lib/utils';
// Simple loading state using div

interface CryptoPriceChartProps {
  portfolioId: number;
  timeRange: string;
  height?: number;
}

export function CryptoPriceChart({ portfolioId, timeRange, height = 400 }: CryptoPriceChartProps) {
  const { data: performanceData, isLoading } = useCryptoPerformanceData(portfolioId, timeRange);

  const chartData = useMemo(() => {
    if (!performanceData || performanceData.length === 0) return [];

    return performanceData.map((data) => ({
      date: new Date(data.date),
      displayDate: formatDate(data.date, timeRange === '1D' ? 'HH:mm' : 'MMM dd'),
      portfolio: data.portfolio_value,
      benchmark: data.benchmark_value,
    }));
  }, [performanceData, timeRange]);

  if (isLoading) {
    return <div className="w-full h-96 bg-gray-100 animate-pulse rounded-lg"></div>;
  }

  if (!chartData || chartData.length === 0) {
    return (
      <div className="h-96 flex items-center justify-center text-gray-500">
        <div className="text-center">
          <p className="text-lg font-medium">No performance data available</p>
          <p className="text-sm mt-1">Add transactions to see portfolio performance over time</p>
        </div>
      </div>
    );
  }

  // Format currency for tooltip
  const formatTooltipValue = (value: number) => {
    return formatCurrency(value, 'USD');
  };

  // X-axis uses preformatted displayDate strings directly

  return (
    <div className="w-full" style={{ height: `${height}px` }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={chartData}
          margin={{
            top: 5,
            right: 30,
            left: 20,
            bottom: 5,
          }}
        >
          <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
          <XAxis
            dataKey="displayDate"
            tickFormatter={formatXAxisTick}
            className="text-xs"
          />
          <YAxis
            tickFormatter={(value) => {
              if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`;
              if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`;
              return `$${value.toFixed(0)}`;
            }}
            className="text-xs"
          />
          <Tooltip
            formatter={formatTooltipValue}
            labelFormatter={(label) => `Date: ${label}`}
            contentStyle={{
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
            }}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="portfolio"
            stroke="#3B82F6"
            strokeWidth={2}
            dot={false}
            name="Portfolio Value"
            activeDot={{ r: 6, fill: '#3B82F6' }}
          />
          {chartData.some((data) => data.benchmark !== undefined) && (
            <Line
              type="monotone"
              dataKey="benchmark"
              stroke="#9CA3AF"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
              name="Benchmark"
              activeDot={{ r: 6, fill: '#9CA3AF' }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}