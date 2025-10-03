import { PortfolioOverview } from '@/components/Dashboard/PortfolioOverview';
import { TodaysMovers } from '@/components/Dashboard/TodaysMovers';
import { PerformanceChart } from '@/components/Dashboard/PerformanceChart';
import { HoldingsTable } from '@/components/Dashboard/HoldingsTable';

export default function DashboardPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Dashboard</h1>
          <p className="text-gray-600">Overview of your portfolio performance</p>
        </div>

        <PortfolioOverview />
        <TodaysMovers />
        <PerformanceChart />
        <HoldingsTable />
      </div>
    </div>
  );
}
