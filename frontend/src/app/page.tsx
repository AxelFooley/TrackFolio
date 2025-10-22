'use client';

import { useState, useEffect } from 'react';
import { PortfolioOverview } from '@/components/Dashboard/PortfolioOverview';
import { TodaysMovers } from '@/components/Dashboard/TodaysMovers';
import { PerformanceChart } from '@/components/Dashboard/PerformanceChart';
import { HoldingsTable } from '@/components/Dashboard/HoldingsTable';
import { NewsCards } from '@/components/Dashboard/NewsCards';
import { DashboardSkeleton } from '@/components/Dashboard/DashboardSkeleton';
import { AddTransactionModal } from '@/components/Modals/AddTransactionModal';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Plus, ChevronLeft, Loader2 } from 'lucide-react';
import { usePortfolioOverview, useHoldings } from '@/hooks/usePortfolio';
import { useNews } from '@/hooks/useNews';

export default function DashboardPage() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [newsOpen, setNewsOpen] = useState(false);
  const [isPageLoading, setIsPageLoading] = useState(true);

  // Check if all data is loading
  const { isLoading: overviewLoading, error: overviewError } = usePortfolioOverview();
  const { isLoading: holdingsLoading, error: holdingsError } = useHoldings();
  const { isLoading: newsLoading, error: newsError } = useNews({
    limit: 8
  });

  useEffect(() => {
    // Simulate initial loading
    const loadingTimer = setTimeout(() => {
      setIsPageLoading(false);
    }, 1000);

    return () => clearTimeout(loadingTimer);
  }, []);

  const isAnyDataLoading = overviewLoading || holdingsLoading || newsLoading || isPageLoading;
  const hasAnyError = overviewError || holdingsError || newsError;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        {/* Loading overlay */}
        {isAnyDataLoading && (
          <div className="fixed inset-0 bg-white bg-opacity-90 z-50 flex items-center justify-center">
            <div className="text-center">
              <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-blue-600" />
              <p className="text-gray-600">Loading dashboard...</p>
            </div>
          </div>
        )}

        {/* Error state */}
        {hasAnyError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-red-800 mb-2">Error Loading Dashboard</h3>
            <p className="text-red-700 mb-4">
              Unable to load dashboard data. Please try refreshing the page.
            </p>
            {(overviewError || holdingsError) && (
              <Button onClick={() => window.location.reload()} variant="destructive">
                Reload Page
              </Button>
            )}
          </div>
        )}

        {isAnyDataLoading ? (
          <DashboardSkeleton />
        ) : (
          <>
            {/* Header with Add Transaction Button and News Toggle */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
              <div>
                <h1 className="text-3xl font-bold mb-2">Dashboard</h1>
                <p className="text-gray-600">Overview of your portfolio performance</p>
              </div>
              <div className="flex items-center gap-2">
                {/* News Modal Button */}
                <Dialog open={newsOpen} onOpenChange={setNewsOpen}>
                  <DialogTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex items-center gap-2 border-gray-300 hover:border-gray-400"
                    >
                      <div className="flex items-center gap-1">
                        <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                        <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                      </div>
                      News
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                      <DialogTitle className="flex items-center justify-between">
                        <div>
                          <h2 className="text-2xl font-bold">Financial News</h2>
                          <p className="text-sm text-gray-600 mt-1">Stay updated with market news</p>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setNewsOpen(false)}
                          className="md:hidden"
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </Button>
                      </DialogTitle>
                    </DialogHeader>
                    <NewsCards
                      limit={15}
                      showTitle={true}
                      className="space-y-4"
                    />
                  </DialogContent>
                </Dialog>

                {/* Add Transaction Button */}
                <Button onClick={() => setShowAddModal(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Transaction
                </Button>
              </div>
            </div>

            {/* Main Dashboard Content */}
            <div className="space-y-12">
              {/* Portfolio Overview Section */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <PortfolioOverview />
              </div>

              {/* Today's Movers Section */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <TodaysMovers />
              </div>

              {/* Latest News - Horizontal Cards Below Today's Movers */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <div className="mb-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xl font-semibold text-gray-900 mb-1">Latest Market News</h2>
                      <p className="text-sm text-gray-600">Financial news affecting your portfolio</p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setNewsOpen(true)}
                    >
                      View All News
                    </Button>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  <NewsCards
                    limit={8}
                    showTitle={false}
                    className="space-y-0"
                  />
                </div>
              </div>

              {/* Performance Chart Section */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <PerformanceChart />
              </div>

              {/* Holdings Table Section */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <HoldingsTable />
              </div>
            </div>
          </>
        )}
      </div>

      <AddTransactionModal
        open={showAddModal}
        onOpenChange={setShowAddModal}
      />
    </div>
  );
}