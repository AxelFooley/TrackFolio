'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
import { Textarea } from '@/components/ui/textarea';
import { Plus, AlertCircle } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';
import { isValidCryptoSymbol, formatCryptoSymbol } from '@/lib/api/crypto-paper';
import type { CreateCryptoTransaction } from '@/types/crypto-paper';

interface AddTransactionModalProps {
  portfolioId: number;
  onTransactionAdded: () => void;
  trigger?: React.ReactNode;
}

export function AddTransactionModal({
  portfolioId,
  onTransactionAdded,
  trigger
}: AddTransactionModalProps) {
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [formData, setFormData] = useState<Omit<CreateCryptoTransaction, 'portfolio_id'>>({
    transaction_type: 'buy',
    symbol: '',
    quantity: 0,
    price_usd: 0,
    fee_usd: 0,
    transaction_date: new Date().toISOString().split('T')[0],
    notes: '',
  });

  const resetForm = () => {
    setFormData({
      transaction_type: 'buy',
      symbol: '',
      quantity: 0,
      price_usd: 0,
      fee_usd: 0,
      transaction_date: new Date().toISOString().split('T')[0],
      notes: '',
    });
    setErrors({});
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.symbol.trim()) {
      newErrors.symbol = 'Symbol is required';
    } else if (!isValidCryptoSymbol(formData.symbol)) {
      newErrors.symbol = 'Invalid crypto symbol format';
    }

    if (formData.quantity <= 0) {
      newErrors.quantity = 'Quantity must be greater than 0';
    }

    if (formData.price_usd <= 0) {
      newErrors.price_usd = 'Price must be greater than 0';
    }

    if (formData.fee_usd < 0) {
      newErrors.fee_usd = 'Fee cannot be negative';
    }

    if (!formData.transaction_date) {
      newErrors.transaction_date = 'Transaction date is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);
    try {
      const transactionData: CreateCryptoTransaction = {
        ...formData,
        portfolio_id: portfolioId,
        symbol: formatCryptoSymbol(formData.symbol),
      };

      const response = await fetch(`/api/crypto-paper/portfolios/${portfolioId}/transactions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(transactionData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create transaction');
      }

      onTransactionAdded();
      setOpen(false);
      resetForm();
    } catch (error) {
      console.error('Error creating transaction:', error);
      setErrors({
        submit: error instanceof Error ? error.message : 'Failed to create transaction'
      });
    } finally {
      setIsLoading(false);
    }
  };

  const totalAmount = formData.quantity * formData.price_usd;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Add Transaction
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Add Crypto Transaction</DialogTitle>
          <DialogDescription>
            Add a new buy, sell, or transfer transaction to your crypto portfolio.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Transaction Type */}
          <div className="space-y-2">
            <Label htmlFor="transaction_type">Transaction Type</Label>
            <Select
              value={formData.transaction_type}
              onValueChange={(value: any) =>
                setFormData({ ...formData, transaction_type: value })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select transaction type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="buy">Buy</SelectItem>
                <SelectItem value="sell">Sell</SelectItem>
                <SelectItem value="transfer_in">Transfer In</SelectItem>
                <SelectItem value="transfer_out">Transfer Out</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Symbol */}
          <div className="space-y-2">
            <Label htmlFor="symbol">Crypto Symbol</Label>
            <Input
              id="symbol"
              placeholder="BTC, ETH, etc."
              value={formData.symbol}
              onChange={(e) => setFormData({ ...formData, symbol: e.target.value.toUpperCase() })}
              className="font-mono"
            />
            {errors.symbol && (
              <p className="text-sm text-red-600 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {errors.symbol}
              </p>
            )}
          </div>

          {/* Quantity and Price */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="quantity">Quantity</Label>
              <Input
                id="quantity"
                type="number"
                step="any"
                min="0"
                placeholder="0.00"
                value={formData.quantity || ''}
                onChange={(e) => setFormData({ ...formData, quantity: parseFloat(e.target.value) || 0 })}
                className="font-mono"
              />
              {errors.quantity && (
                <p className="text-sm text-red-600 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  {errors.quantity}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="price_usd">Price (USD)</Label>
              <Input
                id="price_usd"
                type="number"
                step="any"
                min="0"
                placeholder="0.00"
                value={formData.price_usd || ''}
                onChange={(e) => setFormData({ ...formData, price_usd: parseFloat(e.target.value) || 0 })}
                className="font-mono"
              />
              {errors.price_usd && (
                <p className="text-sm text-red-600 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  {errors.price_usd}
                </p>
              )}
            </div>
          </div>

          {/* Total Amount Display */}
          {totalAmount > 0 && (
            <div className="p-3 bg-gray-50 rounded-md">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium">Total Amount:</span>
                <span className="text-lg font-semibold">
                  {formatCurrency(totalAmount, 'USD')}
                </span>
              </div>
            </div>
          )}

          {/* Fee */}
          <div className="space-y-2">
            <Label htmlFor="fee_usd">Fee (USD)</Label>
            <Input
              id="fee_usd"
              type="number"
              step="any"
              min="0"
              placeholder="0.00"
              value={formData.fee_usd || ''}
              onChange={(e) => setFormData({ ...formData, fee_usd: parseFloat(e.target.value) || 0 })}
              className="font-mono"
            />
            {errors.fee_usd && (
              <p className="text-sm text-red-600 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {errors.fee_usd}
              </p>
            )}
          </div>

          {/* Transaction Date */}
          <div className="space-y-2">
            <Label htmlFor="transaction_date">Transaction Date</Label>
            <Input
              id="transaction_date"
              type="date"
              value={formData.transaction_date}
              onChange={(e) => setFormData({ ...formData, transaction_date: e.target.value })}
              max={new Date().toISOString().split('T')[0]}
            />
            {errors.transaction_date && (
              <p className="text-sm text-red-600 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {errors.transaction_date}
              </p>
            )}
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label htmlFor="notes">Notes (Optional)</Label>
            <Textarea
              id="notes"
              placeholder="Add any notes about this transaction..."
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              rows={3}
            />
          </div>

          {/* Error Message */}
          {errors.submit && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-600 flex items-center gap-2">
                <AlertCircle className="h-4 w-4" />
                {errors.submit}
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setOpen(false);
                resetForm();
              }}
              disabled={isLoading}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isLoading}
              className="flex-1"
            >
              {isLoading ? 'Adding...' : 'Add Transaction'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}