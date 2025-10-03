import { CSVUploader } from '@/components/Import/CSVUploader';
import { TransactionList } from '@/components/Import/TransactionList';

export default function ImportPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Import Transactions</h1>
          <p className="text-gray-600">
            Upload a CSV file with your transactions to add them to your portfolio
          </p>
        </div>

        <CSVUploader />
        <TransactionList />
      </div>
    </div>
  );
}
