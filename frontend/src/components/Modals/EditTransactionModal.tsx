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
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
  // Initialize form state with current transaction values
  const [form, setForm] = useState({
    operationDate: transaction.operation_date.split('T')[0], // Format as YYYY-MM-DD for input[type="date"]
    ticker: transaction.ticker,
    type: transaction.type as 'buy' | 'sell',
    quantity: transaction.quantity.toString(),
    pricePerShare: transaction.price_per_share.toString(),
    fees: transaction.fees.toString(),
    currency: transaction.currency,
  });

  const handleFieldChange = (field: keyof typeof form, value: string) => {
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const updateMutation = useUpdateTransaction();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate all form fields
    const errors: string[] = [];

    if (!form.operationDate) {
      errors.push('Operation date is required');
    }

    if (!form.ticker || form.ticker.trim().length === 0) {
      errors.push('Ticker is required');
    } else if (!/^[A-Za-z0-9.-]+$/.test(form.ticker.trim())) {
      errors.push('Ticker contains invalid characters');
    }

    if (!form.type) {
      errors.push('Transaction type is required');
    }

    const quantityValue = parseFloat(form.quantity);
    if (isNaN(quantityValue) || quantityValue <= 0) {
      errors.push('Quantity must be a positive number');
    }

    const priceValue = parseFloat(form.pricePerShare);
    if (isNaN(priceValue) || priceValue <= 0) {
      errors.push('Price per share must be a positive number');
    }

    const feesValue = parseFloat(form.fees);
    if (isNaN(feesValue) || feesValue < 0) {
      errors.push('Fees must be a non-negative number');
    }

    if (!form.currency || form.currency.trim().length === 0) {
      errors.push('Currency is required');
    }

    if (errors.length > 0) {
      toast({
        title: 'Validation errors',
        description: errors.join(', '),
        variant: 'destructive',
      });
      return;
    }

    try {
      await updateMutation.mutateAsync({
        id: transaction.id,
        data: {
          operation_date: new Date(form.operationDate).toISOString(),
          ticker: form.ticker.trim().toUpperCase(),
          type: form.type,
          quantity: quantityValue,
          amount: priceValue,
          fees: feesValue,
          currency: form.currency.trim().toUpperCase(),
        },
      });
      toast({
        title: 'Transaction updated',
        description: 'Transaction has been updated successfully',
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
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Transaction</DialogTitle>
          <DialogDescription>
            Update all transaction details
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            {/* Operation Date */}
            <div className="space-y-2">
              <Label htmlFor="operation_date">
                Operation Date *
              </Label>
              <Input
                id="operation_date"
                type="date"
                value={form.operationDate}
                onChange={(e) => handleFieldChange('operationDate', e.target.value)}
                required
              />
            </div>

            {/* Ticker */}
            <div className="space-y-2">
              <Label htmlFor="ticker">
                Ticker *
              </Label>
              <Input
                id="ticker"
                type="text"
                value={form.ticker}
                onChange={(e) => handleFieldChange('ticker', e.target.value.toUpperCase())}
                placeholder="AAPL"
                required
              />
            </div>

            {/* Transaction Type */}
            <div className="space-y-2">
              <Label htmlFor="type">
                Transaction Type *
              </Label>
              <Select value={form.type} onValueChange={(value: 'buy' | 'sell') => handleFieldChange('type', value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="buy">Buy</SelectItem>
                  <SelectItem value="sell">Sell</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Quantity */}
            <div className="space-y-2">
              <Label htmlFor="quantity">
                Quantity *
              </Label>
              <Input
                id="quantity"
                type="number"
                step="0.000001"
                min="0.000001"
                value={form.quantity}
                onChange={(e) => handleFieldChange('quantity', e.target.value)}
                placeholder="0"
                required
              />
            </div>

            {/* Price per Share */}
            <div className="space-y-2">
              <Label htmlFor="price_per_share">
                Price per Share ({form.currency}) *
              </Label>
              <Input
                id="price_per_share"
                type="number"
                step="0.000001"
                min="0.000001"
                value={form.pricePerShare}
                onChange={(e) => handleFieldChange('pricePerShare', e.target.value)}
                placeholder="0.00"
                required
              />
            </div>

            {/* Fees */}
            <div className="space-y-2">
              <Label htmlFor="fees">
                Fees ({form.currency})
              </Label>
              <Input
                id="fees"
                type="number"
                step="0.01"
                min="0"
                value={form.fees}
                onChange={(e) => handleFieldChange('fees', e.target.value)}
                placeholder="0.00"
              />
            </div>

            {/* Currency */}
            <div className="space-y-2">
              <Label htmlFor="currency">
                Currency *
              </Label>
              <Select value={form.currency} onValueChange={(value) => handleFieldChange('currency', value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Select currency" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="EUR">EUR</SelectItem>
                  <SelectItem value="USD">USD</SelectItem>
                  <SelectItem value="GBP">GBP</SelectItem>
                </SelectContent>
              </Select>
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
