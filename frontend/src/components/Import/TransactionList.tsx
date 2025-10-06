'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { useTransactions } from '@/hooks/useTransactions';
import { formatCurrency, formatDate } from '@/lib/utils';
import { AlertTriangle, Pencil } from 'lucide-react';
import { EditTransactionModal } from '@/components/Modals/EditTransactionModal';
import type { Transaction } from '@/lib/types';

export function TransactionList() {
  const { data: transactions, isLoading } = useTransactions(0, 50);
  const [selectedTransaction, setSelectedTransaction] = useState<Transaction | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleEdit = (transaction: Transaction) => {
    setSelectedTransaction(transaction);
    setIsModalOpen(true);
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent Transactions</CardTitle>
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

  if (!transactions || transactions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent Transactions</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">No transactions found. Import a CSV file to get started.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Recent Transactions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Ticker</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Quantity</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead className="text-right">Fees</TableHead>
                  <TableHead>Currency</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactions.map((transaction) => (
                  <TableRow key={transaction.id}>
                    <TableCell>{formatDate(transaction.operation_date)}</TableCell>
                    <TableCell className="font-medium">{transaction.ticker || '-'}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                          transaction.type === 'buy'
                            ? 'bg-success/10 text-success'
                            : 'bg-danger/10 text-danger'
                        }`}
                      >
                        {transaction.type?.toUpperCase() || 'N/A'}
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {transaction.quantity || '-'}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(transaction.price_per_share * transaction.quantity, transaction.currency)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      <div className="flex items-center justify-end gap-2">
                        {transaction.fees === 0 && (
                          <span title="Fee missing">
                            <AlertTriangle className="h-4 w-4 text-warning" />
                          </span>
                        )}
                        {formatCurrency(transaction.fees, transaction.currency)}
                      </div>
                    </TableCell>
                    <TableCell>{transaction.currency || '-'}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEdit(transaction)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {selectedTransaction && (
        <EditTransactionModal
          transaction={selectedTransaction}
          open={isModalOpen}
          onOpenChange={setIsModalOpen}
        />
      )}
    </>
  );
}
