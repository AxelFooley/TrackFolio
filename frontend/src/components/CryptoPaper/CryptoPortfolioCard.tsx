'use client';

import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatCurrency, formatPercentage, formatDate } from '@/lib/utils';
import { TrendingUp, TrendingDown, Wallet, ArrowRight } from 'lucide-react';
import type { CryptoPortfolio } from '@/types/crypto-paper';

interface CryptoPortfolioCardProps {
  portfolio: CryptoPortfolio;
}

export function CryptoPortfolioCard({ portfolio }: CryptoPortfolioCardProps) {
  const router = useRouter();

  const isPositive = portfolio.total_profit_usd >= 0;
  const isPositiveIRR = portfolio.irr >= 0;

  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer group">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Wallet className="h-5 w-5 text-blue-500" />
            <CardTitle className="text-lg font-semibold group-hover:text-blue-600 transition-colors">
              {portfolio.name}
            </CardTitle>
          </div>
          <ArrowRight className="h-4 w-4 text-gray-400 group-hover:text-blue-500 transition-colors" />
        </div>
        {portfolio.description && (
          <p className="text-sm text-gray-600 mt-1 line-clamp-2">
            {portfolio.description}
          </p>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Current Value */}
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">Current Value</span>
          <span className="text-lg font-bold">
            {formatCurrency(portfolio.total_value_usd, 'USD')}
          </span>
        </div>

        {/* Profit/Loss */}
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">Total P&L</span>
          <div className={`flex items-center gap-1 ${
            isPositive ? 'text-green-600' : 'text-red-600'
          }`}>
            {isPositive ? (
              <TrendingUp className="h-4 w-4" />
            ) : (
              <TrendingDown className="h-4 w-4" />
            )}
            <span className="font-semibold">
              {formatCurrency(Math.abs(portfolio.total_profit_usd), 'USD')}
            </span>
            <span className="text-sm">
              ({formatPercentage(portfolio.total_profit_pct)})
            </span>
          </div>
        </div>

        {/* IRR */}
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">IRR</span>
          <span className={`font-semibold ${
            isPositiveIRR ? 'text-green-600' : 'text-red-600'
          }`}>
            {formatPercentage(portfolio.irr)}
          </span>
        </div>

        {/* Last Updated */}
        <div className="pt-2 border-t border-gray-100">
          <div className="flex justify-between items-center text-xs text-gray-500">
            <span>Last updated</span>
            <span>{formatDate(portfolio.updated_at)}</span>
          </div>
        </div>

        {/* View Details Button */}
        <Button
          variant="outline"
          className="w-full mt-3"
          onClick={(e) => {
            e.stopPropagation();
            router.push(`/crypto-paper/${portfolio.id}`);
          }}
        >
          View Details
        </Button>
      </CardContent>
    </Card>
  );
}