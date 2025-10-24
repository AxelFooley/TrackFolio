'use client';

import { useState } from 'react';
import { PortfolioOverview } from '@/components/Dashboard/PortfolioOverview';
import { TodaysMovers } from '@/components/Dashboard/TodaysMovers';
import { PerformanceChart } from '@/components/Dashboard/PerformanceChart';
import { HoldingsTable } from '@/components/Dashboard/HoldingsTable';
import { AddTransactionModal } from '@/components/Modals/AddTransactionModal';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';

export default function DashboardPage() {
  const [showAddModal, setShowAddModal] = useState(false);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold mb-2">Dashboard</h1>
            <p className="text-gray-600">Overview of your portfolio performance</p>
          </div>
          <Button onClick={() => setShowAddModal(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Transaction
          </Button>
        </div>

        <PortfolioOverview />
        <TodaysMovers />
        <PerformanceChart />
        <HoldingsTable />
      </div>

      <AddTransactionModal
        open={showAddModal}
        onOpenChange={setShowAddModal}
      />
    </div>
  );
}
