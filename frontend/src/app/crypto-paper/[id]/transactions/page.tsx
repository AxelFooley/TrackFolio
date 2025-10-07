'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CryptoTransactionTable } from '@/components/CryptoPaper/CryptoTransactionTable';
import { AddTransactionModal } from '@/components/CryptoPaper/AddTransactionModal';
import {
  ArrowLeft,
  Plus,
  Search,
  Filter,
  Download,
  RefreshCw,
  Eye
} from 'lucide-react';
import { getCryptoPortfolio, getCryptoTransactions } from '@/lib/api/crypto-paper';
import type { CryptoPortfolio, CryptoTransaction } from '@/types/crypto-paper';

export default function CryptoTransactionsPage() {
  const params = useParams();
  const router = useRouter();
  const portfolioId = parseInt(params.id as string);

  const [portfolio, setPortfolio] = useState<CryptoPortfolio | null>(null);
  const [transactions, setTransactions] = useState<CryptoTransaction[]>([]);
  const [filteredTransactions, setFilteredTransactions] = useState<CryptoTransaction[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter states
  const [searchTerm, setSearchTerm] = useState('');
  const [transactionTypeFilter, setTransactionTypeFilter] = useState<string>('all');
  const [symbolFilter, setSymbolFilter] = useState<string>('all');

  // Load portfolio and transactions on component mount
  useEffect(() => {
    if (!isNaN(portfolioId)) {
      loadData();
    }
  }, [portfolioId]);

  // Apply filters when transactions or filter states change
  useEffect(() => {
    applyFilters();
  }, [transactions, searchTerm, transactionTypeFilter, symbolFilter]);

  const loadData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const [portfolioData, transactionsData] = await Promise.all([
        getCryptoPortfolio(portfolioId),
        getCryptoTransactions(portfolioId),
      ]);

      setPortfolio(portfolioData);
      setTransactions(transactionsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = [...transactions];

    // Apply search filter
    if (searchTerm) {
      filtered = filtered.filter(transaction =>
        transaction.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
        transaction.notes?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Apply transaction type filter
    if (transactionTypeFilter !== 'all') {
      filtered = filtered.filter(transaction =>
        transaction.transaction_type === transactionTypeFilter
      );
    }

    // Apply symbol filter
    if (symbolFilter !== 'all') {
      filtered = filtered.filter(transaction =>
        transaction.symbol === symbolFilter
      );
    }

    setFilteredTransactions(filtered);
  };

  const handleTransactionAdded = () => {
    // Reload transactions when a new transaction is added
    loadData();
  };

  const handleEditTransaction = (transaction: CryptoTransaction) => {
    // TODO: Implement edit transaction modal
    console.log('Edit transaction:', transaction);
  };

  const handleDeleteTransaction = async (transactionId: number) => {
    try {
      const response = await fetch(`/api/crypto-paper/portfolios/${portfolioId}/transactions/${transactionId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete transaction');
      }

      // Reload transactions
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete transaction');
    }
  };

  const handleViewTransaction = (transaction: CryptoTransaction) => {
    // TODO: Implement view transaction details modal
    console.log('View transaction:', transaction);
  };

  const handleExportTransactions = () => {
    // Create CSV content
    const headers = ['Date', 'Type', 'Symbol', 'Quantity', 'Price', 'Total', 'Fee', 'Notes'];
    const csvContent = [
      headers.join(','),
      ...filteredTransactions.map(t => [
        t.transaction_date,
        t.transaction_type,
        t.symbol,
        t.quantity,
        t.price_usd,
        t.total_usd,
        t.fee_usd,
        `"${t.notes || ''}"`,
      ].join(','))
    ].join('\n');

    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${portfolio?.name || 'portfolio'}_transactions_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  // Get unique symbols for filter dropdown
  const uniqueSymbols = Array.from(new Set(transactions.map(t => t.symbol))).sort();

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Button variant="outline" size="sm" disabled>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div className="h-8 w-64 bg-gray-200 rounded animate-pulse"></div>
        </div>

        <Card>
          <CardContent className="p-6">
            <div className="h-96 bg-gray-200 rounded animate-pulse"></div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error || !portfolio) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Button variant="outline" size="sm" onClick={() => router.push(`/crypto-paper/${portfolioId}`)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Portfolio
          </Button>
        </div>

        <Card>
          <CardContent className="p-6">
            <div className="text-center">
              <p className="text-red-600 font-medium">
                {error || 'Portfolio not found'}
              </p>
              <Button
                variant="outline"
                onClick={loadData}
                className="mt-4"
              >
                Retry
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="sm" onClick={() => router.push(`/crypto-paper/${portfolioId}`)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Portfolio
          </Button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Transaction History</h1>
            <p className="text-gray-600 mt-1">{portfolio.name}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <AddTransactionModal
            portfolioId={portfolio.id}
            onTransactionAdded={handleTransactionAdded}
          />
          <Button
            variant="outline"
            onClick={handleExportTransactions}
            disabled={filteredTransactions.length === 0}
          >
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search */}
            <div className="space-y-2">
              <Label htmlFor="search">Search</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  id="search"
                  placeholder="Symbol or notes..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Transaction Type Filter */}
            <div className="space-y-2">
              <Label htmlFor="transaction-type">Transaction Type</Label>
              <Select value={transactionTypeFilter} onValueChange={setTransactionTypeFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All types" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="buy">Buy</SelectItem>
                  <SelectItem value="sell">Sell</SelectItem>
                  <SelectItem value="transfer_in">Transfer In</SelectItem>
                  <SelectItem value="transfer_out">Transfer Out</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Symbol Filter */}
            <div className="space-y-2">
              <Label htmlFor="symbol">Symbol</Label>
              <Select value={symbolFilter} onValueChange={setSymbolFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All symbols" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Symbols</SelectItem>
                  {uniqueSymbols.map((symbol) => (
                    <SelectItem key={symbol} value={symbol}>
                      {symbol}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Results Count */}
            <div className="space-y-2">
              <Label>Results</Label>
              <div className="flex items-center h-10 px-3 bg-gray-50 rounded-md border">
                <Badge variant="outline">
                  {filteredTransactions.length} of {transactions.length}
                </Badge>
              </div>
            </div>
          </div>

          {/* Clear Filters */}
          {(searchTerm || transactionTypeFilter !== 'all' || symbolFilter !== 'all') && (
            <div className="mt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSearchTerm('');
                  setTransactionTypeFilter('all');
                  setSymbolFilter('all');
                }}
              >
                Clear Filters
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Transaction Summary */}
      {filteredTransactions.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-gray-600">Total Volume</div>
              <div className="text-lg font-semibold">
                ${filteredTransactions.reduce((sum, t) => sum + t.total_usd, 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-gray-600">Total Fees</div>
              <div className="text-lg font-semibold">
                ${filteredTransactions.reduce((sum, t) => sum + t.fee_usd, 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-gray-600">Buy Transactions</div>
              <div className="text-lg font-semibold">
                {filteredTransactions.filter(t => t.transaction_type === 'buy').length}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-gray-600">Sell Transactions</div>
              <div className="text-lg font-semibold">
                {filteredTransactions.filter(t => t.transaction_type === 'sell').length}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Transactions Table */}
      <CryptoTransactionTable
        transactions={filteredTransactions}
        onEdit={handleEditTransaction}
        onDelete={handleDeleteTransaction}
        onView={handleViewTransaction}
      />
    </div>
  );
}