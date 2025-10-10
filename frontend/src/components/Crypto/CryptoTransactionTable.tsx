'use client';

import { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useCryptoTransactions, useUpdateCryptoTransaction, useDeleteCryptoTransaction } from '@/hooks/useCrypto';
import { formatCurrency, formatCryptoQuantity, formatDate, formatDateTime } from '@/lib/utils';
import { ArrowUpDown, Edit, Trash2, TrendingUp, TrendingDown, Bitcoin, ArrowDownUp, ArrowUpCircle, ArrowDownCircle } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import type { CryptoTransaction, CryptoTransactionUpdate } from '@/lib/types';

interface CryptoTransactionTableProps {
  portfolioId: number;
  searchTerm?: string;
  symbolFilter?: string;
  limit?: number;
}

const transactionTypeConfig = {
  BUY: {
    label: 'Buy',
    icon: ArrowUpCircle,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
  },
  SELL: {
    label: 'Sell',
    icon: ArrowDownCircle,
    color: 'text-red-600',
    bgColor: 'bg-red-50',
  },
  TRANSFER_IN: {
    label: 'Transfer In',
    icon: ArrowDownUp,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
  },
  TRANSFER_OUT: {
    label: 'Transfer Out',
    icon: ArrowDownUp,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
  },
};

export function CryptoTransactionTable({
  portfolioId,
  searchTerm = '',
  symbolFilter = '',
  limit,
}: CryptoTransactionTableProps) {
  const { data: transactionsData, isLoading } = useCryptoTransactions(portfolioId);
  const updateTransactionMutation = useUpdateCryptoTransaction();
  const deleteTransactionMutation = useDeleteCryptoTransaction();
  const { toast } = useToast();

  // State for editing
  const [editingTransaction, setEditingTransaction] = useState<CryptoTransaction | null>(null);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [sortField, setSortField] = useState<keyof CryptoTransaction>('date');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const handleSort = (field: keyof CryptoTransaction) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const handleEdit = (transaction: CryptoTransaction) => {
    setEditingTransaction(transaction);
    setShowEditDialog(true);
  };

  const handleDelete = (transaction: CryptoTransaction) => {
    setEditingTransaction(transaction);
    setShowDeleteDialog(true);
  };

  const handleUpdateTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTransaction) return;

    try {
      await updateTransactionMutation.mutateAsync({
        portfolioId,
        transactionId: editingTransaction.id,
        data: {
          transaction_type: editingTransaction.transaction_type,
          quantity: editingTransaction.quantity,
          price: editingTransaction.price,
          fees: editingTransaction.fees,
          currency: editingTransaction.currency,
          date: editingTransaction.date,
          exchange: editingTransaction.exchange,
          notes: editingTransaction.notes,
        },
      });

      toast({
        title: 'Transaction Updated',
        description: 'Transaction has been updated successfully',
      });

      setShowEditDialog(false);
      setEditingTransaction(null);
    } catch (error: any) {
      toast({
        title: 'Update Failed',
        description: error.message || 'Failed to update transaction',
        variant: 'destructive',
      });
    }
  };

  const handleDeleteTransaction = async () => {
    if (!editingTransaction) return;

    try {
      await deleteTransactionMutation.mutateAsync({
        portfolioId,
        transactionId: editingTransaction.id,
      });

      toast({
        title: 'Transaction Deleted',
        description: 'Transaction has been deleted successfully',
      });

      setShowDeleteDialog(false);
      setEditingTransaction(null);
    } catch (error: any) {
      toast({
        title: 'Deletion Failed',
        description: error.message || 'Failed to delete transaction',
        variant: 'destructive',
      });
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(limit || 10)].map((_, i) => (
          <div key={i} className="h-16 bg-gray-200 rounded animate-pulse"></div>
        ))}
      </div>
    );
  }

  if (!transactionsData || transactionsData.items.length === 0) {
    return (
      <div className="text-center py-8">
        <Bitcoin className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">No transactions found</h3>
        <p className="text-gray-600">
          Add your first transaction to start tracking your crypto portfolio
        </p>
      </div>
    );
  }

  let filteredTransactions = transactionsData.items.filter((transaction) => {
    const matchesSearch = searchTerm === '' ||
      transaction.symbol.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSymbol = symbolFilter === '' || transaction.symbol === symbolFilter;
    return matchesSearch && matchesSymbol;
  });

  // Apply limit if specified
  if (limit) {
    filteredTransactions = filteredTransactions.slice(0, limit);
  }

  const sortedTransactions = [...filteredTransactions].sort((a, b) => {
    const aValue = a[sortField];
    const bValue = b[sortField];

    if (typeof aValue === 'number' && typeof bValue === 'number') {
      return sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
    }

    if (typeof aValue === 'string' && typeof bValue === 'string') {
      return sortDirection === 'asc'
        ? aValue.localeCompare(bValue)
        : bValue.localeCompare(aValue);
    }

    return 0;
  });

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead
                className="cursor-pointer"
                onClick={() => handleSort('date')}
              >
                <div className="flex items-center gap-2">
                  Date
                  <ArrowUpDown className="h-4 w-4" />
                </div>
              </TableHead>
              <TableHead
                className="cursor-pointer"
                onClick={() => handleSort('transaction_type')}
              >
                <div className="flex items-center gap-2">
                  Type
                  <ArrowUpDown className="h-4 w-4" />
                </div>
              </TableHead>
              <TableHead
                className="cursor-pointer"
                onClick={() => handleSort('symbol')}
              >
                <div className="flex items-center gap-2">
                  Symbol
                  <ArrowUpDown className="h-4 w-4" />
                </div>
              </TableHead>
              <TableHead
                className="cursor-pointer text-right"
                onClick={() => handleSort('quantity')}
              >
                <div className="flex items-center justify-end gap-2">
                  Quantity
                  <ArrowUpDown className="h-4 w-4" />
                </div>
              </TableHead>
              <TableHead
                className="cursor-pointer text-right"
                onClick={() => handleSort('price')}
              >
                <div className="flex items-center justify-end gap-2">
                  Price
                  <ArrowUpDown className="h-4 w-4" />
                </div>
              </TableHead>
              <TableHead
                className="cursor-pointer text-right"
                onClick={() => handleSort('fees')}
              >
                <div className="flex items-center justify-end gap-2">
                  Fees
                  <ArrowUpDown className="h-4 w-4" />
                </div>
              </TableHead>
                <TableHead
                className="cursor-pointer text-right"
                onClick={() => handleSort('total')}
                >
                <div className="flex items-center justify-end gap-2">
                  Total
                  <ArrowUpDown className="h-4 w-4" />
                </div>
                </TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedTransactions.map((transaction) => {
              const typeConfig = transactionTypeConfig[transaction.transaction_type];
              const TypeIcon = typeConfig.icon;
              const total = transaction.quantity * transaction.price;

              return (
                <TableRow key={transaction.id}>
                  <TableCell>
                    <div>
                      <div className="font-medium">
                        {formatDate(transaction.date)}
                      </div>
                      <div className="text-xs text-gray-500">
                        {formatDateTime(transaction.date, 'HH:mm')}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={`${typeConfig.bgColor} ${typeConfig.color} border-current`}
                    >
                      <TypeIcon className="h-3 w-3 mr-1" />
                      {typeConfig.label}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <Bitcoin className="h-4 w-4 text-orange-500" />
                      {transaction.symbol}
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatCryptoQuantity(transaction.quantity)}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatCurrency(transaction.price, transaction.currency)}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatCurrency(transaction.fees, transaction.currency)}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatCurrency(total, transaction.currency)}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEdit(transaction)}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(transaction)}
                        className="text-red-600 hover:text-red-800"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Edit Transaction Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="max-w-md">
          <form onSubmit={handleUpdateTransaction}>
            <DialogHeader>
              <DialogTitle>Edit Transaction</DialogTitle>
              <DialogDescription>
                Update the transaction details
              </DialogDescription>
            </DialogHeader>
            {editingTransaction && (
              <div className="space-y-4">
                <div>
                  <Label htmlFor="edit-symbol">Symbol</Label>
                  <Input
                    id="edit-symbol"
                    value={editingTransaction.symbol}
                    onChange={(e) => setEditingTransaction({
                      ...editingTransaction,
                      symbol: e.target.value.toUpperCase(),
                    })}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="edit-type">Transaction Type</Label>
                  <Select
                    value={editingTransaction.transaction_type}
                    onValueChange={(value: any) =>
                      setEditingTransaction({ ...editingTransaction, transaction_type: value })
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
                  <Label htmlFor="edit-quantity">Quantity</Label>
                  <Input
                    id="edit-quantity"
                    type="number"
                    step="any"
                    value={editingTransaction.quantity}
                    onChange={(e) => setEditingTransaction({
                      ...editingTransaction,
                      quantity: parseFloat(e.target.value) || 0,
                    })}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="edit-price">Price per Unit</Label>
                  <Input
                    id="edit-price"
                    type="number"
                    step="any"
                    value={editingTransaction.price}
                    onChange={(e) => setEditingTransaction({
                      ...editingTransaction,
                      price: parseFloat(e.target.value) || 0,
                    })}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="edit-fees">Fees</Label>
                  <Input
                    id="edit-fees"
                    type="number"
                    step="any"
                    value={editingTransaction.fees}
                    onChange={(e) => setEditingTransaction({
                      ...editingTransaction,
                      fees: parseFloat(e.target.value) || 0,
                    })}
                  />
                </div>
                <div>
                  <Label htmlFor="edit-currency">Currency</Label>
                  <Select
                    value={editingTransaction.currency}
                    onValueChange={(value: 'USD' | 'EUR') =>
                      setEditingTransaction({ ...editingTransaction, currency: value })
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
                  <Label htmlFor="edit-date">Date</Label>
                  <Input
                    id="edit-date"
                    type="date"
                    value={editingTransaction.date}
                    onChange={(e) => setEditingTransaction({
                      ...editingTransaction,
                      date: e.target.value,
                    })}
                    required
                  />
                </div>
              </div>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowEditDialog(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateTransactionMutation.isPending}>
                {updateTransactionMutation.isPending ? 'Updating...' : 'Update'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Transaction</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this transaction? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {editingTransaction && (
            <div className="space-y-2">
              <p><strong>Symbol:</strong> {editingTransaction.symbol}</p>
              <p><strong>Type:</strong> {transactionTypeConfig[editingTransaction.transaction_type].label}</p>
              <p><strong>Quantity:</strong> {formatCryptoQuantity(editingTransaction.quantity)}</p>
              <p><strong>Date:</strong> {formatDate(editingTransaction.date)}</p>
            </div>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowDeleteDialog(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteTransaction}
              disabled={deleteTransactionMutation.isPending}
            >
              {deleteTransactionMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}