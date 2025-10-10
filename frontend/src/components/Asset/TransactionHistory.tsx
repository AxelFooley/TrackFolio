'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAssetTransactions } from '@/hooks/useAsset';
import { formatCurrency, formatDate } from '@/lib/utils';

interface TransactionHistoryProps {
  ticker: string;
}

/**
 * Render a transaction history card for the provided asset ticker.
 *
 * Shows loading skeletons while transactions are being fetched, displays a "No transactions found"
 * message when there are no entries, and otherwise presents a horizontally scrollable table of
 * transactions with columns: Date, Type, Quantity, Price, Amount, Fees, and Currency.
 * Numeric cells are right-aligned and use a monospaced font; dates and monetary values are formatted.
 *
 * @param ticker - The asset ticker symbol whose transactions should be displayed.
 * @returns A React element containing the transaction history card with loading, empty, and populated states.
 */
export function TransactionHistory({ ticker }: TransactionHistoryProps) {
  const { data: transactions, isLoading } = useAssetTransactions(ticker);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Transaction History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
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
          <CardTitle>Transaction History</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">No transactions found</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Transaction History</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Quantity</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead className="text-right">Fees</TableHead>
                <TableHead>Currency</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.map((transaction) => {
                const price = Number(transaction.price ?? 0);
                const qty = Number(transaction.quantity ?? 0);
                const amount = price * qty;
                return (
                  <TableRow key={transaction.id}>
                    <TableCell>{formatDate(transaction.date)}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                          transaction.transaction_type?.toUpperCase() === 'BUY'
                            ? 'bg-success/10 text-success'
                            : 'bg-danger/10 text-danger'
                        }`}
                      >
                        {transaction.transaction_type ?? 'N/A'}
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {transaction.quantity || '-'}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(price, transaction.currency)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(amount, transaction.currency)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(Number(transaction.fees ?? 0), transaction.currency)}
                    </TableCell>
                    <TableCell>{transaction.currency}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}