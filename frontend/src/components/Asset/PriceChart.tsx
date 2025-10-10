'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAssetPrices } from '@/hooks/useAsset';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { formatCurrency } from '@/lib/utils';
import type { Position } from '@/lib/types';

const timeRanges = ['1D', '1W', '1M', '3M', '6M', '1Y', 'YTD', 'ALL'];

interface PriceChartProps {
  ticker: string;
  position: Position;
}

/**
 * Render a price history chart for a given ticker and position.
 *
 * Displays a selectable time-range toolbar, a responsive line chart of historical prices,
 * and a dashed reference line labeled "Avg Cost" when the position includes an average cost.
 *
 * @param ticker - The asset ticker symbol to fetch and display price data for.
 * @param position - The position object providing currency and optional average_cost used for formatting and the reference line.
 * @returns A React element containing the price history card and chart UI.
 */
export function PriceChart({ ticker, position }: PriceChartProps) {
  const [selectedRange, setSelectedRange] = useState('1Y');
  const { data: priceData, isLoading } = useAssetPrices(ticker, selectedRange);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Price History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-96 bg-gray-200 rounded animate-pulse"></div>
        </CardContent>
      </Card>
    );
  }

  if (!priceData || priceData.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Price History</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">No price data available</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Price History</CardTitle>
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
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={priceData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => {
                const date = new Date(value);
                return date.toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                });
              }}
            />
            <YAxis
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => formatCurrency(value, position.currency)}
            />
            <Tooltip
              formatter={(value: number) => formatCurrency(value, position.currency)}
              labelFormatter={(label) => new Date(label).toLocaleDateString()}
            />
            <Legend />
            {position.average_cost && (
              <ReferenceLine
                y={position.average_cost}
                stroke="#F59E0B"
                strokeDasharray="5 5"
                label="Avg Cost"
              />
            )}
            <Line
              type="monotone"
              dataKey="close"
              stroke="#3B82F6"
              strokeWidth={2}
              dot={false}
              name="Price"
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}