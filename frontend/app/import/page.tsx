'use client';

import { useState } from 'react';
import { CSVUploader } from '@/components/Import/CSVUploader';
import { TransactionList } from '@/components/Import/TransactionList';
import { AddTransactionModal } from '@/components/Modals/AddTransactionModal';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';

export default function ImportPage() {
  const [showAddModal, setShowAddModal] = useState(false);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold mb-2">Import Transactions</h1>
            <p className="text-gray-600">
              Upload a CSV file with your transactions to add them to your portfolio
            </p>
          </div>
          <Button onClick={() => setShowAddModal(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Transaction
          </Button>
        </div>

        <CSVUploader />
        <TransactionList />
      </div>

      <AddTransactionModal
        open={showAddModal}
        onOpenChange={setShowAddModal}
      />
    </div>
  );
}
