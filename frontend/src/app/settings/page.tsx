'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useBenchmark, useSetBenchmark } from '@/hooks/useBenchmark';
import { useLastUpdate, useRefreshPrices } from '@/hooks/usePrices';
import { useToast } from '@/hooks/use-toast';
import { formatDateTime } from '@/lib/utils';
import { Loader2, RefreshCw } from 'lucide-react';
import { TickerAutocomplete } from '@/components/TickerAutocomplete';

export default function SettingsPage() {
  const { data: benchmark, isLoading: benchmarkLoading } = useBenchmark();
  const { data: lastUpdate, refetch: refetchLastUpdate } = useLastUpdate();
  const setBenchmarkMutation = useSetBenchmark();
  const refreshPricesMutation = useRefreshPrices();
  const { toast } = useToast();
  const [benchmarkTicker, setBenchmarkTicker] = useState('');

  const handleSetBenchmark = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!benchmarkTicker.trim()) {
      toast({
        title: 'Invalid input',
        description: 'Please enter a benchmark ticker',
        variant: 'destructive',
      });
      return;
    }

    try {
      await setBenchmarkMutation.mutateAsync({
        ticker: benchmarkTicker.toUpperCase(),
        description: `Benchmark: ${benchmarkTicker.toUpperCase()}`,
      });
      toast({
        title: 'Benchmark updated',
        description: `Benchmark set to ${benchmarkTicker.toUpperCase()}`,
      });
      setBenchmarkTicker('');
    } catch (error: any) {
      toast({
        title: 'Failed to update benchmark',
        description: error.response?.data?.detail || 'An error occurred',
        variant: 'destructive',
      });
    }
  };

  const handleRefreshPrices = async () => {
    try {
      await refreshPricesMutation.mutateAsync();
      // Refetch last update timestamp immediately
      await refetchLastUpdate();
      toast({
        title: 'Prices refreshed',
        description: 'All prices have been updated successfully',
      });
    } catch (error: any) {
      toast({
        title: 'Failed to refresh prices',
        description: error.response?.data?.detail || 'An error occurred',
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Settings</h1>
          <p className="text-gray-600">Manage your portfolio configuration</p>
        </div>

        {/* Benchmark Configuration */}
        <Card>
          <CardHeader>
            <CardTitle>Benchmark Configuration</CardTitle>
            <CardDescription>
              Set a benchmark index to compare your portfolio performance against
            </CardDescription>
          </CardHeader>
          <CardContent>
            {benchmarkLoading ? (
              <div className="animate-pulse space-y-4">
                <div className="h-10 bg-gray-200 rounded"></div>
                <div className="h-10 bg-gray-200 rounded w-32"></div>
              </div>
            ) : (
              <div className="space-y-4">
                {benchmark && (
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <div>
                      <p className="text-sm text-gray-600">Current Benchmark</p>
                      <p className="text-lg font-semibold">{benchmark.ticker}</p>
                      <p className="text-sm text-gray-600">
                        {benchmark.description || 'No description'}
                      </p>
                    </div>
                  </div>
                )}

                <form onSubmit={handleSetBenchmark} className="space-y-4">
                  <div>
                    <label htmlFor="benchmark" className="block text-sm font-medium mb-2">
                      Benchmark Ticker
                    </label>
                    <TickerAutocomplete
                      value={benchmarkTicker}
                      onSelect={setBenchmarkTicker}
                      placeholder="Search for a benchmark (e.g., S&P 500, CSSPX.MI)..."
                      disabled={setBenchmarkMutation.isPending}
                    />
                    <p className="text-sm text-gray-500 mt-1">
                      Search and select a ticker symbol. Popular benchmarks: ^GSPC (S&P 500), CSSPX.MI (iShares S&P 500)
                    </p>
                  </div>
                  <Button
                    type="submit"
                    disabled={setBenchmarkMutation.isPending || !benchmarkTicker.trim()}
                  >
                    {setBenchmarkMutation.isPending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Updating...
                      </>
                    ) : (
                      'Update Benchmark'
                    )}
                  </Button>
                </form>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Price Data Management */}
        <Card>
          <CardHeader>
            <CardTitle>Price Data Management</CardTitle>
            <CardDescription>
              Manually refresh price data for all assets in your portfolio
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {lastUpdate && (
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-600">Last Price Update</p>
                  <p className="text-lg font-semibold">
                    {lastUpdate.last_update
                      ? formatDateTime(lastUpdate.last_update)
                      : 'Never'}
                  </p>
                </div>
              )}

              <div>
                <Button
                  onClick={handleRefreshPrices}
                  disabled={refreshPricesMutation.isPending}
                >
                  {refreshPricesMutation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Refreshing...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Refresh Prices Now
                    </>
                  )}
                </Button>
                <p className="text-sm text-gray-500 mt-2">
                  This will fetch the latest prices for all assets in your portfolio.
                  Price data is also automatically updated daily.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* System Information */}
        <Card>
          <CardHeader>
            <CardTitle>System Information</CardTitle>
            <CardDescription>About this application</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Application</span>
                <span className="font-medium">Portfolio Tracker</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Version</span>
                <span className="font-medium">1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">API Endpoint</span>
                <span className="font-medium font-mono">
                  {process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
