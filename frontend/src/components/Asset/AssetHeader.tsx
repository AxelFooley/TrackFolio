'use client';

import { Card, CardContent } from '@/components/ui/card';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import { TrendingUp, TrendingDown } from 'lucide-react';
import type { Position } from '@/lib/types';

interface AssetHeaderProps {
  position: Position;
}

export function AssetHeader({ position }: AssetHeaderProps) {
  const isPositive = (position.today_change || 0) >= 0;

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2">{position.ticker}</h1>
            <p className="text-lg text-gray-600">
              {position.description || position.asset_type}
            </p>
            <p className="text-sm text-gray-500 mt-1">
              ISIN: {position.isin}
            </p>
          </div>

          <div className="text-right">
            <div className="text-3xl font-bold mb-1">
              {formatCurrency(position.current_price, position.currency)}
            </div>
            {position.today_change !== undefined && position.today_change_percent !== undefined && (
              <div
                className={`flex items-center justify-end gap-2 ${
                  isPositive ? 'text-success' : 'text-danger'
                }`}
              >
                {isPositive ? (
                  <TrendingUp className="h-5 w-5" />
                ) : (
                  <TrendingDown className="h-5 w-5" />
                )}
                <span className="text-lg font-medium">
                  {formatCurrency(position.today_change, position.currency)} (
                  {position.today_change_percent !== null && position.today_change_percent !== undefined
                    ? formatPercentage(position.today_change_percent * 100)
                    : '—'})
                </span>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
