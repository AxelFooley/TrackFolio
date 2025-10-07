'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { useToast } from '@/hooks/use-toast';
import { formatCurrency, formatPercentage, formatDate } from '@/lib/utils';
import { TrendingUp, TrendingDown, Wallet, ArrowRight, MoreVertical, Edit3, Trash2 } from 'lucide-react';
import type { CryptoPortfolio } from '@/types/crypto-paper';
import { EditPortfolioModal } from './EditPortfolioModal';
import { DeletePortfolioModal } from './DeletePortfolioModal';

interface CryptoPortfolioCardProps {
  portfolio: CryptoPortfolio;
  onPortfolioUpdated?: () => void;
  onPortfolioDeleted?: () => void;
}

export function CryptoPortfolioCard({
  portfolio,
  onPortfolioUpdated,
  onPortfolioDeleted
}: CryptoPortfolioCardProps) {
  const router = useRouter();
  const { toast } = useToast();
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [transactionCount, setTransactionCount] = useState(0);
  const [holdingCount, setHoldingCount] = useState(0);

  const isPositive = portfolio.total_profit_usd >= 0;
  const isPositiveIRR = portfolio.irr >= 0;

  const handlePortfolioUpdated = () => {
    toast({
      title: "Portfolio Updated",
      description: `"${portfolio.name}" has been successfully updated.`,
    });
    onPortfolioUpdated?.();
  };

  const handlePortfolioDeleted = () => {
    toast({
      title: "Portfolio Deleted",
      description: `"${portfolio.name}" has been permanently deleted.`,
      variant: "destructive",
    });
    onPortfolioDeleted?.();
  };

  const handleDeleteError = (error: string) => {
    toast({
      title: "Delete Failed",
      description: error,
      variant: "destructive",
    });
  };

  const handleCardClick = () => {
    router.push(`/crypto-paper/${portfolio.id}`);
  };

  return (
    <>
      <Card className="hover:shadow-lg transition-shadow cursor-pointer group">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div
              className="flex items-center gap-2 flex-1"
              onClick={handleCardClick}
            >
              <Wallet className="h-5 w-5 text-blue-500" />
              <CardTitle className="text-lg font-semibold group-hover:text-blue-600 transition-colors">
                {portfolio.name}
              </CardTitle>
            </div>

            {/* Action Dropdown Menu */}
            <div className="flex items-center gap-2">
              <ArrowRight className="h-4 w-4 text-gray-400 group-hover:text-blue-500 transition-colors" />

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0 hover:bg-gray-100"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <MoreVertical className="h-4 w-4 text-gray-500" />
                    <span className="sr-only">Open menu</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                    }}
                    className="cursor-pointer"
                  >
                    <EditPortfolioModal
                      portfolio={portfolio}
                      onPortfolioUpdated={handlePortfolioUpdated}
                      trigger={
                        <div className="flex items-center gap-2 w-full">
                          <Edit3 className="h-4 w-4" />
                          <span>Edit Portfolio</span>
                        </div>
                      }
                    />
                  </DropdownMenuItem>

                  <DropdownMenuSeparator />

                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      setIsDeleteModalOpen(true);
                    }}
                    className="cursor-pointer text-red-600 focus:text-red-600 focus:bg-red-50"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete Portfolio
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
            {portfolio.description && (
              <p
                className="text-sm text-gray-600 mt-1 line-clamp-2"
                onClick={handleCardClick}
              >
                {portfolio.description}
              </p>
            )}
          </CardHeader>

      <CardContent className="space-y-4" onClick={handleCardClick}>
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

      {/* Delete Portfolio Modal */}
      <DeletePortfolioModal
        isOpen={isDeleteModalOpen}
        onOpenChange={setIsDeleteModalOpen}
        portfolio={portfolio}
        transactionCount={transactionCount}
        holdingCount={holdingCount}
        onSuccess={handlePortfolioDeleted}
        onError={handleDeleteError}
      />
    </>
  );
}