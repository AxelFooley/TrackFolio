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
import { TickerAutocomplete } from '@/components/TickerAutocomplete';
import { useCreateTransaction } from '@/hooks/useTransactions';
import { useToast } from '@/hooks/use-toast';
import type { TransactionCreate } from '@/lib/types';
import { Loader2 } from 'lucide-react';

interface AddTransactionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddTransactionModal({
  open,
  onOpenChange,
}: AddTransactionModalProps) {
  const [formData, setFormData] = useState<TransactionCreate>({
    operation_date: new Date().toISOString().split('T')[0],
    ticker: '',
    type: 'buy',
    quantity: 0,
    amount: 0,
    currency: 'EUR',
    fees: 0,
  });

  const createMutation = useCreateTransaction();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!formData.ticker) {
      toast({
        title: 'Validation error',
        description: 'Please select a ticker',
        variant: 'destructive',
      });
      return;
    }

    if (formData.quantity <= 0) {
      toast({
        title: 'Validation error',
        description: 'Quantity must be greater than 0',
        variant: 'destructive',
      });
      return;
    }

    if (formData.amount <= 0) {
      toast({
        title: 'Validation error',
        description: 'Price per share must be greater than 0',
        variant: 'destructive',
      });
      return;
    }

    if (formData.fees < 0) {
      toast({
        title: 'Validation error',
        description: 'Fees must be 0 or greater',
        variant: 'destructive',
      });
      return;
    }

    try {
      await createMutation.mutateAsync(formData);
      toast({
        title: 'Transaction created',
        description: `Successfully added ${formData.type} transaction for ${formData.ticker}`,
      });
      onOpenChange(false);
      // Reset form
      setFormData({
        operation_date: new Date().toISOString().split('T')[0],
        ticker: '',
        type: 'buy',
        quantity: 0,
        amount: 0,
        currency: 'EUR',
        fees: 0,
      });
    } catch (error: any) {
      toast({
        title: 'Creation failed',
        description: error.response?.data?.detail || 'Failed to create transaction',
        variant: 'destructive',
      });
    }
  };

  const handleFieldChange = (field: keyof TransactionCreate, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add Transaction</DialogTitle>
          <DialogDescription>
            Manually add a buy or sell transaction to your portfolio
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            {/* Transaction Type */}
            <div className="space-y-2">
              <Label htmlFor="type">Transaction Type</Label>
              <Select
                value={formData.type}
                onValueChange={(value) => handleFieldChange('type', value as 'buy' | 'sell')}
              >
                <SelectTrigger id="type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="buy">Buy</SelectItem>
                  <SelectItem value="sell">Sell</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Ticker */}
            <div className="space-y-2">
              <Label htmlFor="ticker">Ticker</Label>
              <TickerAutocomplete
                value={formData.ticker}
                onSelect={(ticker) => handleFieldChange('ticker', ticker)}
                placeholder="Select or search ticker..."
              />
            </div>

            {/* Date */}
            <div className="space-y-2">
              <Label htmlFor="operation_date">Date</Label>
              <Input
                id="operation_date"
                type="date"
                value={formData.operation_date}
                onChange={(e) => handleFieldChange('operation_date', e.target.value)}
                required
              />
            </div>

            {/* Quantity */}
            <div className="space-y-2">
              <Label htmlFor="quantity">Quantity</Label>
              <Input
                id="quantity"
                type="number"
                step="0.001"
                min="0.001"
                value={formData.quantity || ''}
                onChange={(e) => handleFieldChange('quantity', parseFloat(e.target.value) || 0)}
                placeholder="0.000"
                required
              />
            </div>

            {/* Price per Share */}
            <div className="space-y-2">
              <Label htmlFor="amount">Price per Share</Label>
              <Input
                id="amount"
                type="number"
                step="0.01"
                min="0.01"
                value={formData.amount || ''}
                onChange={(e) => handleFieldChange('amount', parseFloat(e.target.value) || 0)}
                placeholder="0.00"
                required
              />
            </div>

            {/* Currency */}
            <div className="space-y-2">
              <Label htmlFor="currency">Currency</Label>
              <Select
                value={formData.currency}
                onValueChange={(value) => handleFieldChange('currency', value)}
              >
                <SelectTrigger id="currency">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="EUR">EUR</SelectItem>
                  <SelectItem value="USD">USD</SelectItem>
                  <SelectItem value="GBP">GBP</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Fees */}
            <div className="space-y-2">
              <Label htmlFor="fees">Fees ({formData.currency})</Label>
              <Input
                id="fees"
                type="number"
                step="0.01"
                min="0"
                value={formData.fees || ''}
                onChange={(e) => handleFieldChange('fees', parseFloat(e.target.value) || 0)}
                placeholder="0.00"
              />
            </div>

            {/* Total Cost Preview */}
            <div className="rounded-lg bg-gray-50 p-3 space-y-1">
              <div className="text-sm font-medium text-gray-700">Transaction Summary</div>
              <div className="text-xs text-gray-600 space-y-0.5">
                <div className="flex justify-between">
                  <span>Subtotal:</span>
                  <span className="font-mono">
                    {(formData.quantity * formData.amount).toFixed(2)} {formData.currency}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Fees:</span>
                  <span className="font-mono">
                    {formData.fees.toFixed(2)} {formData.currency}
                  </span>
                </div>
                <div className="flex justify-between font-medium text-gray-900 pt-1 border-t">
                  <span>Total:</span>
                  <span className="font-mono">
                    {(formData.quantity * formData.amount + formData.fees).toFixed(2)} {formData.currency}
                  </span>
                </div>
              </div>
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
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                'Add Transaction'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
