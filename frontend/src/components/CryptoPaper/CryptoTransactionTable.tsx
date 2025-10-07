'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { formatCurrency, formatNumber, formatDateTime } from '@/lib/utils';
import { ArrowUpDown, MoreHorizontal, Edit, Trash2, Eye } from 'lucide-react';
import { CryptoTransactionTypeLabels, CryptoTransactionTypeColors } from '@/types/crypto-paper';
import type { CryptoTransaction } from '@/types/crypto-paper';

type SortField = keyof CryptoTransaction;
type SortDirection = 'asc' | 'desc';

interface CryptoTransactionTableProps {
  transactions: CryptoTransaction[];
  isLoading?: boolean;
  onEdit?: (transaction: CryptoTransaction) => void;
  onDelete?: (transactionId: number) => void;
  onView?: (transaction: CryptoTransaction) => void;
  onTransactionAdded?: () => void;
}

export function CryptoTransactionTable({
  transactions,
  isLoading,
  onEdit,
  onDelete,
  onView,
  onTransactionAdded
}: CryptoTransactionTableProps) {
  const [sortField, setSortField] = useState<SortField>('transaction_date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Transaction History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 rounded animate-pulse"></div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!transactions || !Array.isArray(transactions) || transactions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Transaction History</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">No transaction history available</p>
        </CardContent>
      </Card>
    );
  }

  // Ensure transactions is an array before sorting
  const sortedTransactions = Array.isArray(transactions) ? [...transactions].sort((a, b) => {
    const aValue = a[sortField];
    const bValue = b[sortField];

    if (typeof aValue === 'number' && typeof bValue === 'number') {
      return sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
    }

    if (typeof aValue === 'string' && typeof bValue === 'string') {
      // For date strings, compare them directly
      if (sortField === 'transaction_date' || sortField === 'created_at' || sortField === 'updated_at') {
        return sortDirection === 'asc'
          ? new Date(aValue).getTime() - new Date(bValue).getTime()
          : new Date(bValue).getTime() - new Date(aValue).getTime();
      }
      // For regular strings, use locale comparison
      return sortDirection === 'asc'
        ? aValue.localeCompare(bValue)
        : bValue.localeCompare(aValue);
    }

    return 0;
  }) : [];

  const handleDelete = async (transactionId: number) => {
    if (window.confirm('Are you sure you want to delete this transaction? This action cannot be undone.')) {
      onDelete?.(transactionId);
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Transaction History</CardTitle>
        <Badge variant="outline" className="font-mono">
          {transactions.length} transactions
        </Badge>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead
                  className="cursor-pointer"
                  onClick={() => handleSort('transaction_date')}
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
                  onClick={() => handleSort('price_usd')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Price
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('total_usd')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Total
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('fee_usd')}
                >
                  <div className="flex items-center justify-end gap-2">
                    Fee
                    <ArrowUpDown className="h-4 w-4" />
                  </div>
                </TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedTransactions.map((transaction) => (
                <TableRow key={transaction.id} className="hover:bg-gray-50">
                  <TableCell>
                    <div className="space-y-1">
                      <div className="text-sm font-medium">
                        {formatDateTime(transaction.transaction_date)}
                      </div>
                      <div className="text-xs text-gray-500">
                        Created: {formatDateTime(transaction.created_at)}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      className={CryptoTransactionTypeColors[transaction.transaction_type]}
                      variant="secondary"
                    >
                      {CryptoTransactionTypeLabels[transaction.transaction_type]}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono font-medium">
                    {transaction.symbol}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatNumber(transaction.quantity, 6)}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatCurrency(transaction.price_usd, 'USD')}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatCurrency(transaction.total_usd, 'USD')}
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {formatCurrency(transaction.fee_usd, 'USD')}
                  </TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" className="h-8 w-8 p-0">
                          <span className="sr-only">Open menu</span>
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {onView && (
                          <DropdownMenuItem onClick={() => onView(transaction)}>
                            <Eye className="mr-2 h-4 w-4" />
                            View Details
                          </DropdownMenuItem>
                        )}
                        {onEdit && (
                          <DropdownMenuItem onClick={() => onEdit(transaction)}>
                            <Edit className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                        )}
                        {onDelete && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onClick={() => handleDelete(transaction.id)}
                              className="text-red-600"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Transaction Summary */}
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-600">Total Volume:</span>
              <div className="font-semibold">
                {formatCurrency(
                  Array.isArray(transactions) ? transactions.reduce((sum, t) => sum + (t.total_usd || 0), 0) : 0,
                  'USD'
                )}
              </div>
            </div>
            <div>
              <span className="text-gray-600">Total Fees:</span>
              <div className="font-semibold">
                {formatCurrency(
                  Array.isArray(transactions) ? transactions.reduce((sum, t) => sum + (t.fee_usd || 0), 0) : 0,
                  'USD'
                )}
              </div>
            </div>
            <div>
              <span className="text-gray-600">Buy Transactions:</span>
              <div className="font-semibold">
                {Array.isArray(transactions) ? transactions.filter(t => t.transaction_type === 'buy').length : 0}
              </div>
            </div>
            <div>
              <span className="text-gray-600">Sell Transactions:</span>
              <div className="font-semibold">
                {Array.isArray(transactions) ? transactions.filter(t => t.transaction_type === 'sell').length : 0}
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}