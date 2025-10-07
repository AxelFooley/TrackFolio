'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Trash2 } from 'lucide-react';
import { DeletePortfolioModal } from './DeletePortfolioModal';
import type { CryptoPortfolio } from '@/types/crypto-paper';

interface DeletePortfolioExampleProps {
  portfolio: CryptoPortfolio;
  transactionCount?: number;
  holdingCount?: number;
  onPortfolioDeleted?: () => void;
}

export function DeletePortfolioExample({
  portfolio,
  transactionCount = 0,
  holdingCount = 0,
  onPortfolioDeleted,
}: DeletePortfolioExampleProps) {
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const handleDeleteSuccess = () => {
    onPortfolioDeleted?.();
    // You could also show a success toast here
    console.log('Portfolio deleted successfully');
  };

  const handleDeleteError = (error: string) => {
    // You could show an error toast here
    console.error('Delete portfolio error:', error);
  };

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setIsDeleteModalOpen(true)}
        className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
      >
        <Trash2 className="h-4 w-4 mr-1" />
        Delete
      </Button>

      <DeletePortfolioModal
        isOpen={isDeleteModalOpen}
        onOpenChange={setIsDeleteModalOpen}
        portfolio={portfolio}
        transactionCount={transactionCount}
        holdingCount={holdingCount}
        onSuccess={handleDeleteSuccess}
        onError={handleDeleteError}
      />
    </>
  );
}