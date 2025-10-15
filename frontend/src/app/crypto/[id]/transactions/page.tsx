'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { useCryptoPortfolio, useCryptoTransactions, useCreateCryptoTransaction } from '@/hooks/useCrypto';
import { CryptoTransactionTable } from '@/components/Crypto/CryptoTransactionTable';
import { formatCurrency, formatCryptoQuantity, formatDate } from '@/lib/utils';
import { ArrowLeft, Plus, Upload, Search, Bitcoin } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import type { CryptoTransactionCreate } from '@/lib/types';

/**
 * Renders the crypto transactions management page for a portfolio, including transaction list, filters, summary cards, and a dialog-driven form to add new transactions.
 *
 * The page fetches portfolio and transaction data, provides search and symbol filtering, shows transaction statistics, and lets the user create a transaction with client-side validation and toast feedback.
 *
 * @returns The page UI for managing cryptocurrency transactions for the current portfolio.
 */
export default function CryptoTransactionsPage() {
  const params = useParams();
  const router = useRouter();
  const portfolioId = parseInt(params.id as string);

  const { data: portfolio, isLoading: portfolioLoading } = useCryptoPortfolio(portfolioId);
  const { data: transactionsData, isLoading: transactionsLoading } = useCryptoTransactions(portfolioId);
  const createTransactionMutation = useCreateCryptoTransaction();
  const { toast } = useToast();

  // State for new transaction form
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [newTransaction, setNewTransaction] = useState({
    symbol: '',
    transaction_type: 'BUY' as 'BUY' | 'SELL' | 'TRANSFER_IN' | 'TRANSFER_OUT',
    quantity: 0,
    price_at_execution: 0,
    fee: 0,
    currency: 'USD' as 'USD' | 'EUR',
    timestamp: new Date().toISOString().split('T')[0],
  });

  // Search and filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [symbolFilter, setSymbolFilter] = useState('');

  const handleCreateTransaction = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!newTransaction.symbol.trim()) {
      toast({
        title: 'Validation Error',
        description: 'Symbol is required',
        variant: 'destructive',
      });
      return;
    }

    if (newTransaction.quantity <= 0) {
      toast({
        title: 'Validation Error',
        description: 'Quantity must be greater than 0',
        variant: 'destructive',
      });
      return;
    }

    if (newTransaction.price_at_execution <= 0) {
      toast({
        title: 'Validation Error',
        description: 'Price must be greater than 0',
        variant: 'destructive',
      });
      return;
    }

    try {
      // Convert timestamp to ISO string
      const timestamp = newTransaction.timestamp
        ? new Date(newTransaction.timestamp).toISOString()
        : new Date().toISOString();

      await createTransactionMutation.mutateAsync({
        portfolioId,
        data: {
          symbol: newTransaction.symbol,
          transaction_type: newTransaction.transaction_type,
          quantity: newTransaction.quantity,
          price_at_execution: newTransaction.price_at_execution,
          fee: newTransaction.fee,
          currency: newTransaction.currency,
          timestamp: timestamp,
        },
      });

      toast({
        title: 'Transaction Added',
        description: 'Transaction has been added successfully',
      });

      setShowAddDialog(false);
      setNewTransaction({
        symbol: '',
        transaction_type: 'BUY',
        quantity: 0,
        price_at_execution: 0,
        fee: 0,
        currency: portfolio?.base_currency || 'USD',
        timestamp: new Date().toISOString().split('T')[0],
      });
    } catch (error: any) {
      toast({
        title: 'Addition Failed',
        description: error.message || 'Failed to add transaction',
        variant: 'destructive',
      });
    }
  };

  if (portfolioLoading || !portfolio) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => router.back()}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
            <div className="h-8 bg-gray-200 rounded animate-pulse w-48"></div>
          </div>
          <div className="h-96 bg-gray-200 rounded animate-pulse"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => router.push(`/crypto/${portfolioId}`)}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Portfolio
            </Button>
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-3">
                <Bitcoin className="h-8 w-8 text-orange-500" />
                {portfolio.name} - Transactions
              </h1>
              <p className="text-gray-600 mt-1">Manage your cryptocurrency transactions</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="text-sm">
              {portfolio.base_currency} Portfolio
            </Badge>
            <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Transaction
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <form onSubmit={handleCreateTransaction}>
                  <DialogHeader>
                    <DialogTitle>Add Crypto Transaction</DialogTitle>
                    <DialogDescription>
                      Add a new buy, sell, or transfer transaction
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div>
                      <Label htmlFor="symbol">Symbol</Label>
                      <Input
                        id="symbol"
                        value={newTransaction.symbol}
                        onChange={(e) => setNewTransaction({ ...newTransaction, symbol: e.target.value.toUpperCase() })}
                        placeholder="BTC, ETH, etc."
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="type">Transaction Type</Label>
                      <Select
                        value={newTransaction.transaction_type}
                        onValueChange={(value: any) =>
                          setNewTransaction({ ...newTransaction, transaction_type: value })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="BUY">Buy</SelectItem>
                          <SelectItem value="SELL">Sell</SelectItem>
                          <SelectItem value="TRANSFER_IN">Transfer In</SelectItem>
                          <SelectItem value="TRANSFER_OUT">Transfer Out</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="quantity">Quantity</Label>
                      <Input
                        id="quantity"
                        type="number"
                        step="any"
                        value={newTransaction.quantity}
                        onChange={(e) => setNewTransaction({ ...newTransaction, quantity: parseFloat(e.target.value) || 0 })}
                        placeholder="0.00"
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="price">Price per Unit</Label>
                      <Input
                        id="price"
                        type="number"
                        step="any"
                        value={newTransaction.price_at_execution}
                        onChange={(e) => setNewTransaction({ ...newTransaction, price_at_execution: parseFloat(e.target.value) || 0 })}
                        placeholder="0.00"
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="fees">Fees</Label>
                      <Input
                        id="fees"
                        type="number"
                        step="any"
                        value={newTransaction.fee}
                        onChange={(e) => setNewTransaction({ ...newTransaction, fee: parseFloat(e.target.value) || 0 })}
                        placeholder="0.00"
                      />
                    </div>
                    <div>
                      <Label htmlFor="currency">Currency</Label>
                      <Select
                        value={newTransaction.currency}
                        onValueChange={(value: 'USD' | 'EUR') =>
                          setNewTransaction({ ...newTransaction, currency: value })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="USD">USD</SelectItem>
                          <SelectItem value="EUR">EUR</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="date">Date</Label>
                      <Input
                        id="date"
                        type="date"
                        value={newTransaction.timestamp}
                        onChange={(e) => setNewTransaction({ ...newTransaction, timestamp: e.target.value })}
                        required
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setShowAddDialog(false)}
                    >
                      Cancel
                    </Button>
                    <Button type="submit" disabled={createTransactionMutation.isPending}>
                      {createTransactionMutation.isPending ? 'Adding...' : 'Add Transaction'}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
            <Button variant="outline" onClick={() => router.push(`/crypto/${portfolioId}/import`)}>
              <Upload className="mr-2 h-4 w-4" />
              Import CSV
            </Button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4">
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search by symbol..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={symbolFilter} onValueChange={setSymbolFilter}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All symbols" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All symbols</SelectItem>
              {/* Generate unique symbols from transactions */}
              {transactionsData?.items
                ?.map((t) => t.symbol)
                .filter((symbol, index, arr) => arr.indexOf(symbol) === index)
                .map((symbol) => (
                  <SelectItem key={symbol} value={symbol}>
                    {symbol}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>

        {/* Transaction Summary */}
        {transactionsData && transactionsData.items && transactionsData.items.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">
                  Total Transactions
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {transactionsData.items.length}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">
                  Unique Assets
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {new Set(transactionsData.items.map((t) => t.symbol)).size}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-gray-600">
                  Last Transaction
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm font-medium">
                  {transactionsData.items.length > 0
                    ? formatDate(transactionsData.items[0].timestamp)
                    : 'No transactions'}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Transactions Table */}
        <Card>
          <CardHeader>
            <CardTitle>Transaction History</CardTitle>
            <CardDescription>
              All your cryptocurrency transactions
            </CardDescription>
          </CardHeader>
          <CardContent>
            <CryptoTransactionTable
              portfolioId={portfolioId}
              searchTerm={searchTerm}
              symbolFilter={symbolFilter}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}