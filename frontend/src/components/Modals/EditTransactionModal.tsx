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
    date: transaction.date.split('T')[0], // Format as YYYY-MM-DD for input[type="date"]
    quantity: (transaction.quantity || 0).toString(),
    price: (transaction.price || 0).toString(),
    fees: transaction.fees.toString(),
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

    if (!form.date) {
      errors.push('Date is required');
    }

    const quantityValue = parseFloat(form.quantity);
    if (isNaN(quantityValue) || quantityValue <= 0) {
      errors.push('Quantity must be a positive number');
    }

    const priceValue = parseFloat(form.price);
    if (isNaN(priceValue) || priceValue <= 0) {
      errors.push('Price per share must be a positive number');
    }

    const feesValue = parseFloat(form.fees);
    if (isNaN(feesValue) || feesValue < 0) {
      errors.push('Fees must be a non-negative number');
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
          date: new Date(form.date).toISOString(),
          quantity: quantityValue,
          price: priceValue,
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
            Update transaction details. Note: Ticker, type, and currency cannot be changed.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            {/* Read-only Info */}
            <div className="grid grid-cols-2 gap-4 pb-4 border-b">
              <div>
                <Label className="text-sm font-medium text-gray-600">Ticker</Label>
                <p className="font-mono">{transaction.ticker}</p>
              </div>
              <div>
                <Label className="text-sm font-medium text-gray-600">Type</Label>
                <p className="font-mono">{transaction.transaction_type}</p>
              </div>
              <div>
                <Label className="text-sm font-medium text-gray-600">Currency</Label>
                <p className="font-mono">{transaction.currency}</p>
              </div>
            </div>

            {/* Date */}
            <div className="space-y-2">
              <Label htmlFor="date">
                Date *
              </Label>
              <Input
                id="date"
                type="date"
                value={form.date}
                onChange={(e) => handleFieldChange('date', e.target.value)}
                required
              />
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
              <Label htmlFor="price">
                Price per Share ({transaction.currency}) *
              </Label>
              <Input
                id="price"
                type="number"
                step="0.000001"
                min="0.000001"
                value={form.price}
                onChange={(e) => handleFieldChange('price', e.target.value)}
                placeholder="0.00"
                required
              />
            </div>

            {/* Fees */}
            <div className="space-y-2">
              <Label htmlFor="fees">
                Fees ({transaction.currency})
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
