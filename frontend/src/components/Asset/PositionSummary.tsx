'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatCurrency, formatPercentage, formatNumber } from '@/lib/utils';
import type { Position } from '@/lib/types';

interface PositionSummaryProps {
  position: Position;
}

export function PositionSummary({ position }: PositionSummaryProps) {
  const currency = position.currency || 'EUR';

  const metrics = [
    {
      title: 'Shares',
      value: formatNumber(position.quantity, 4),
      mono: true,
    },
    {
      title: 'Average Cost',
      value: formatCurrency(position.average_cost, currency),
      mono: true,
    },
    {
      title: 'Cost Basis',
      value: formatCurrency(position.cost_basis, currency),
      mono: true,
    },
    {
      title: 'Current Value',
      value: formatCurrency(position.current_value, currency),
      mono: true,
    },
    {
      title: 'Total Profit',
      value: formatCurrency(position.unrealized_gain, currency),
      change: position.return_percentage !== null && position.return_percentage !== undefined
        ? formatPercentage(position.return_percentage * 100)
        : undefined,
      color: (position.unrealized_gain ?? 0) >= 0 ? 'text-success' : 'text-danger',
      mono: true,
    },
    {
      title: 'IRR (Annual)',
      value: position.irr !== null && position.irr !== undefined
        ? formatPercentage(position.irr * 100)
        : '—',
      color: (position.irr ?? 0) >= 0 ? 'text-success' : 'text-danger',
      mono: true,
    },
  ];

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {metrics.map((metric) => (
          <Card key={metric.title}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">
                {metric.title}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div
                className={`text-2xl font-bold ${metric.color || ''} ${
                  metric.mono ? 'font-mono' : ''
                }`}
              >
                {metric.value}
              </div>
              {metric.change && (
                <p className="text-xs text-gray-600 mt-1">{metric.change}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {position.splits && position.splits.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-lg font-semibold">Split History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {position.splits.map((split, idx) => (
                <div key={idx} className="flex items-center justify-between text-sm border-b pb-2 last:border-b-0 last:pb-0">
                  <div className="flex items-center gap-3">
                    <span className="text-gray-500 font-medium">{split.date}</span>
                    <span className="text-gray-900 font-mono font-semibold">{split.ratio}</span>
                    <span className="text-gray-600">
                      {split.old_ticker} → {split.new_ticker}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}
