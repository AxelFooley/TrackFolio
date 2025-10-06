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
  const [operationDate, setOperationDate] = useState(
    transaction.operation_date.split('T')[0] // Format as YYYY-MM-DD for input[type="date"]
  );
  const [ticker, setTicker] = useState(transaction.ticker);
  const [type, setType] = useState<'buy' | 'sell'>(transaction.type);
  const [quantity, setQuantity] = useState(transaction.quantity.toString());
  const [pricePerShare, setPricePerShare] = useState(transaction.price_per_share.toString());
  const [fees, setFees] = useState(transaction.fees.toString());
  const [currency, setCurrency] = useState(transaction.currency);

  const updateMutation = useUpdateTransaction();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate all form fields
    const errors: string[] = [];

    if (!operationDate) {
      errors.push('Operation date is required');
    }

    if (!ticker || ticker.trim().length === 0) {
      errors.push('Ticker is required');
    } else if (!/^[A-Za-z0-9.-]+$/.test(ticker.trim())) {
      errors.push('Ticker contains invalid characters');
    }

    if (!type) {
      errors.push('Transaction type is required');
    }

    const quantityValue = parseFloat(quantity);
    if (isNaN(quantityValue) || quantityValue <= 0) {
      errors.push('Quantity must be a positive number');
    }

    const priceValue = parseFloat(pricePerShare);
    if (isNaN(priceValue) || priceValue <= 0) {
      errors.push('Price per share must be a positive number');
    }

    const feesValue = parseFloat(fees);
    if (isNaN(feesValue) || feesValue < 0) {
      errors.push('Fees must be a positive number or zero');
    }

    if (!currency || currency.trim().length === 0) {
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
          operation_date: new Date(operationDate).toISOString(),
          ticker: ticker.trim().toUpperCase(),
          type,
          quantity: quantityValue,
          amount: priceValue,
          fees: feesValue,
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
                value={operationDate}
                onChange={(e) => setOperationDate(e.target.value)}
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
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="AAPL"
                required
              />
            </div>

            {/* Transaction Type */}
            <div className="space-y-2">
              <Label htmlFor="type">
                Transaction Type *
              </Label>
              <Select value={type} onValueChange={(value: 'buy' | 'sell') => setType(value)}>
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
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="0"
                required
              />
            </div>

            {/* Price per Share */}
            <div className="space-y-2">
              <Label htmlFor="price_per_share">
                Price per Share ({currency}) *
              </Label>
              <Input
                id="price_per_share"
                type="number"
                step="0.000001"
                min="0.000001"
                value={pricePerShare}
                onChange={(e) => setPricePerShare(e.target.value)}
                placeholder="0.00"
                required
              />
            </div>

            {/* Fees */}
            <div className="space-y-2">
              <Label htmlFor="fees">
                Fees ({currency})
              </Label>
              <Input
                id="fees"
                type="number"
                step="0.01"
                min="0"
                value={fees}
                onChange={(e) => setFees(e.target.value)}
                placeholder="0.00"
              />
            </div>

            {/* Currency */}
            <div className="space-y-2">
              <Label htmlFor="currency">
                Currency *
              </Label>
              <Input
                id="currency"
                type="text"
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                placeholder="USD"
                maxLength={3}
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
