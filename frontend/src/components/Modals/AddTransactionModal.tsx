'use client';

import { useState, useEffect, useRef } from 'react';
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
import { getHistoricalPrice } from '@/lib/api';
import type { TransactionCreate } from '@/lib/types';
import { Loader2, CheckCircle, AlertCircle, Info } from 'lucide-react';

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

  // Price fetching state
  const [isFetchingPrice, setIsFetchingPrice] = useState(false);
  const [priceFetchError, setPriceFetchError] = useState<string | null>(null);
  const [priceAutoFetched, setPriceAutoFetched] = useState(false);
  const [manuallyModifiedPrice, setManuallyModifiedPrice] = useState(false);
  const lastAutoFetchedPrice = useRef<number | null>(null);

  const createMutation = useCreateTransaction();
  const { toast } = useToast();

  // Effect to fetch historical price when ticker and date are selected
  useEffect(() => {
    const fetchHistoricalPrice = async () => {
      // Only fetch if both ticker and date are available, and price hasn't been manually modified
      if (
        formData.ticker &&
        formData.operation_date &&
        !manuallyModifiedPrice &&
        !isFetchingPrice
      ) {
        // Create AbortController for cancellation
        const abortController = new AbortController();

        // Capture ticker and date at the start to prevent stale closures
        const localTicker = formData.ticker;
        const localDate = formData.operation_date;

        setIsFetchingPrice(true);
        setPriceFetchError(null);
        setPriceAutoFetched(false);

        try {
          const priceData = await getHistoricalPrice(localTicker, localDate, abortController.signal);

          // Verify component is still interested in this ticker/date before updating state
          if (formData.ticker === localTicker && formData.operation_date === localDate) {
            // Check if we have a valid price and no error
            if (priceData && priceData.price !== null && priceData.price > 0 && !priceData.error) {
              setFormData(prev => ({
                ...prev,
                amount: priceData.price as number
              }));
              lastAutoFetchedPrice.current = priceData.price as number;
              setPriceAutoFetched(true);
            } else if (priceData?.error) {
              // Handle API error response
              console.error('API returned error:', priceData.error);
              setPriceFetchError(priceData.error);
            }
          }
        } catch (error: any) {
          // Don't show toast if request was aborted
          if (error.name === 'AbortError') {
            console.log('Historical price fetch aborted');
            return;
          }

          console.error('Failed to fetch historical price:', error);
          const errorMessage = error.response?.data?.detail || 'Failed to fetch price';

          // Only update error state if component is still interested in this ticker/date
          if (formData.ticker === localTicker && formData.operation_date === localDate) {
            setPriceFetchError(errorMessage);

            // Show a subtle toast notification for price fetching errors
            toast({
              title: 'Price fetch failed',
              description: `Could not fetch historical price for ${localTicker}. You can enter the price manually.`,
              variant: 'destructive',
              duration: 3000, // Short duration to not be too disruptive
            });
          }
        } finally {
          // Only update loading state if component is still interested in this ticker/date
          if (formData.ticker === localTicker && formData.operation_date === localDate) {
            setIsFetchingPrice(false);
          }
        }

        // Cleanup function to abort request if dependencies change
        return () => {
          abortController.abort();
        };
      }
    };

    const cleanup = fetchHistoricalPrice();
    return cleanup;
  }, [formData.ticker, formData.operation_date, manuallyModifiedPrice]); // Removed isFetchingPrice from dependencies

  // Reset price modification state when form is reset or modal opens
  useEffect(() => {
    if (open) {
      setManuallyModifiedPrice(false);
      setPriceAutoFetched(false);
      setPriceFetchError(null);
      lastAutoFetchedPrice.current = null;
    }
  }, [open]);

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
      // Reset price fetching state
      setManuallyModifiedPrice(false);
      setPriceAutoFetched(false);
      setPriceFetchError(null);
      lastAutoFetchedPrice.current = null;
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

    // Detect manual price modification
    if (field === 'amount') {
      const newPrice = parseFloat(value) || 0;

      // If user entered a price different from the last auto-fetched price, mark as manually modified
      if (
        lastAutoFetchedPrice.current !== null &&
        newPrice !== lastAutoFetchedPrice.current &&
        newPrice > 0
      ) {
        setManuallyModifiedPrice(true);
        setPriceAutoFetched(false);
      }
    }
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
                placeholder="Search by company name or ticker..."
              />
              <p className="text-sm text-gray-500">
                Search by company name (e.g., Apple, Vanguard) or ticker symbol (e.g., AAPL, VOO)
              </p>
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
              <div className="flex items-center gap-2">
                <Label htmlFor="amount">Price per Share</Label>
                {isFetchingPrice && (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                )}
                {priceAutoFetched && (
                  <div className="flex items-center gap-1 text-green-600" title="Price automatically fetched">
                    <CheckCircle className="h-4 w-4" />
                    <span className="text-xs">Auto-fetched</span>
                  </div>
                )}
                {priceFetchError && (
                  <div className="flex items-center gap-1 text-amber-600" title={priceFetchError}>
                    <AlertCircle className="h-4 w-4" />
                    <span className="text-xs">Manual entry</span>
                  </div>
                )}
              </div>
              <div className="relative">
                <Input
                  id="amount"
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={formData.amount || ''}
                  onChange={(e) => handleFieldChange('amount', parseFloat(e.target.value) || 0)}
                  placeholder="0.00"
                  required
                  className={priceAutoFetched ? "pr-20" : "pr-8"}
                />
                {priceAutoFetched && (
                  <div className="absolute right-2 top-1/2 transform -translate-y-1/2 flex items-center gap-1">
                    <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                    <span className="text-xs text-green-600">Auto</span>
                  </div>
                )}
              </div>
              {formData.ticker && formData.operation_date && !isFetchingPrice && (
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  <Info className="h-3 w-3" />
                  Price fetched automatically for {formData.ticker} on {formData.operation_date}
                  {manuallyModifiedPrice && " (manually modified)"}
                </p>
              )}
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
