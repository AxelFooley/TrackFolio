'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useUpdateTransaction } from '@/hooks/useTransactions';
import { useToast } from '@/hooks/use-toast';
import type { Transaction } from '@/lib/types';
import { Loader2 } from 'lucide-react';

interface EditTransactionModalProps {
  transaction: Transaction;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditTransactionModal({
  transaction,
  open,
  onOpenChange,
}: EditTransactionModalProps) {
  const [fees, setFees] = useState(transaction.fees.toString());
  const updateMutation = useUpdateTransaction();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const feesValue = parseFloat(fees);
    if (isNaN(feesValue) || feesValue < 0) {
      toast({
        title: 'Invalid value',
        description: 'Fees must be a positive number',
        variant: 'destructive',
      });
      return;
    }

    try {
      await updateMutation.mutateAsync({
        id: transaction.id,
        data: { fees: feesValue },
      });
      toast({
        title: 'Transaction updated',
        description: 'Fees have been updated successfully',
      });
      onOpenChange(false);
    } catch (error: any) {
      toast({
        title: 'Update failed',
        description: error.response?.data?.detail || 'Failed to update transaction',
        variant: 'destructive',
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Transaction Fees</DialogTitle>
          <DialogDescription>
            Update the transaction fees for {transaction.ticker} on{' '}
            {new Date(transaction.operation_date).toLocaleDateString()}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Transaction Details</label>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="text-gray-600">Type:</div>
                <div className="font-medium">{transaction.type?.toUpperCase() || 'N/A'}</div>
                <div className="text-gray-600">Quantity:</div>
                <div className="font-mono">{transaction.quantity || '-'}</div>
                <div className="text-gray-600">Amount:</div>
                <div className="font-mono">
                  {transaction.amount || '-'} {transaction.currency || ''}
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="fees" className="text-sm font-medium">
                Fees ({transaction.currency})
              </label>
              <Input
                id="fees"
                type="number"
                step="0.01"
                min="0"
                value={fees}
                onChange={(e) => setFees(e.target.value)}
                placeholder="0.00"
                required
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
