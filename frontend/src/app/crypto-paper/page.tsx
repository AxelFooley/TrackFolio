'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { CryptoPortfolioCard } from '@/components/CryptoPaper/CryptoPortfolioCard';
import { Plus, Wallet, TrendingUp, TrendingDown, AlertCircle, RefreshCw } from 'lucide-react';
import { getCryptoPortfolios, createCryptoPortfolio } from '@/lib/api/crypto-paper';
import type { CryptoPortfolio } from '@/types/crypto-paper';

export default function CryptoPaperPage() {
  const router = useRouter();
  const [portfolios, setPortfolios] = useState<CryptoPortfolio[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  // Load portfolios on component mount
  useEffect(() => {
    loadPortfolios();
  }, []);

  const loadPortfolios = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await getCryptoPortfolios();
      setPortfolios(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load portfolios');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreatePortfolio = async (name: string, description: string) => {
    try {
      setIsCreating(true);
      const newPortfolio = await createCryptoPortfolio({
        name,
        description: description || undefined,
      });
      setPortfolios([...portfolios, newPortfolio]);
      setIsCreateModalOpen(false);
      // Navigate to the new portfolio
      router.push(`/crypto-paper/${newPortfolio.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create portfolio');
    } finally {
      setIsCreating(false);
    }
  };

  const handlePortfolioUpdated = async () => {
    // Refresh the portfolio list after a successful update
    await refreshPortfolios();
  };

  const handlePortfolioDeleted = async () => {
    // Refresh the portfolio list after a successful deletion
    await refreshPortfolios();
  };

  const refreshPortfolios = async () => {
    try {
      setIsRefreshing(true);
      setError(null);
      const data = await getCryptoPortfolios();
      setPortfolios(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh portfolios');
    } finally {
      setIsRefreshing(false);
    }
  };

  const dismissError = () => {
    setError(null);
  };

  // Calculate totals across all portfolios (with safety checks)
  const totalValue = (portfolios || []).reduce((sum, p) => sum + (p.total_value_usd || 0), 0);
  const totalCost = (portfolios || []).reduce((sum, p) => sum + (p.total_cost_usd || 0), 0);
  const totalProfit = (portfolios || []).reduce((sum, p) => sum + (p.total_profit_usd || 0), 0);
  const isPositiveProfit = totalProfit >= 0;

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Crypto Portfolios</h1>
          <p className="text-gray-600 mt-2">Track your cryptocurrency portfolio performance</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {[...Array(3)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-20 bg-gray-200 rounded animate-pulse"></div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-48 bg-gray-200 rounded animate-pulse"></div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Crypto Portfolios</h1>
          <p className="text-gray-600 mt-2">Track your cryptocurrency portfolio performance</p>
        </div>

        <Card>
          <CardContent className="p-6">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start">
                <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                <div className="ml-3 flex-1">
                  <h3 className="text-sm font-medium text-red-800">
                    Failed to load portfolios
                  </h3>
                  <p className="mt-1 text-sm text-red-700">
                    {error}
                  </p>
                  <div className="mt-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={loadPortfolios}
                      className="text-red-700 border-red-300 hover:bg-red-100"
                    >
                      Retry
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 relative">
      {/* Loading Overlay for Refresh Operations */}
      {isRefreshing && (
        <div className="absolute inset-0 bg-white bg-opacity-50 flex items-center justify-center z-10 rounded-lg">
          <div className="flex items-center gap-2 text-blue-600">
            <RefreshCw className="h-5 w-5 animate-spin" />
            <span className="font-medium">Updating portfolios...</span>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Crypto Portfolios</h1>
          <p className="text-gray-600 mt-2">Track your cryptocurrency portfolio performance</p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshPortfolios}
            disabled={isRefreshing}
            className="flex items-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </Button>

          <CreatePortfolioDialog
            isOpen={isCreateModalOpen}
            onOpenChange={setIsCreateModalOpen}
            onCreate={handleCreatePortfolio}
            isCreating={isCreating}
          />
        </div>
      </div>

      {/* Summary Cards */}
      {portfolios.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Value</p>
                  <p className="text-2xl font-bold text-gray-900">
                    ${totalValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
                <Wallet className="h-8 w-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Cost</p>
                  <p className="text-2xl font-bold text-gray-900">
                    ${totalCost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
                <div className="h-8 w-8 bg-gray-100 rounded-full flex items-center justify-center">
                  <span className="text-sm font-bold text-gray-600">$</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total P&L</p>
                  <p className={`text-2xl font-bold ${isPositiveProfit ? 'text-green-600' : 'text-red-600'}`}>
                    {isPositiveProfit ? '+' : ''}${Math.abs(totalProfit).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
                {isPositiveProfit ? (
                  <TrendingUp className="h-8 w-8 text-green-500" />
                ) : (
                  <TrendingDown className="h-8 w-8 text-red-500" />
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <Card className="mb-6 border-red-200 bg-red-50">
          <CardContent className="p-4">
            <div className="flex items-start justify-between">
              <div className="flex items-start">
                <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 mr-3 flex-shrink-0" />
                <div>
                  <h3 className="text-sm font-medium text-red-800">
                    Error
                  </h3>
                  <p className="mt-1 text-sm text-red-700">
                    {error}
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={dismissError}
                className="text-red-600 hover:text-red-800 hover:bg-red-100"
              >
                ×
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Portfolios Grid */}
      {portfolios.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {portfolios.map((portfolio) => (
            <CryptoPortfolioCard
              key={portfolio.id}
              portfolio={portfolio}
              onPortfolioUpdated={handlePortfolioUpdated}
              onPortfolioDeleted={handlePortfolioDeleted}
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="p-12 text-center">
            <Wallet className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No crypto portfolios yet</h3>
            <p className="text-gray-600 mb-6">
              Create your first crypto paper wallet to start tracking your cryptocurrency investments.
            </p>
            <CreatePortfolioDialog
              isOpen={isCreateModalOpen}
              onOpenChange={setIsCreateModalOpen}
              onCreate={handleCreatePortfolio}
              isCreating={isCreating}
              trigger={
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Your First Portfolio
                </Button>
              }
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// Create Portfolio Dialog Component
interface CreatePortfolioDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (name: string, description: string) => void;
  isCreating: boolean;
  trigger?: React.ReactNode;
}

function CreatePortfolioDialog({ isOpen, onOpenChange, onCreate, isCreating, trigger }: CreatePortfolioDialogProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim()) {
      onCreate(name.trim(), description.trim());
      setName('');
      setDescription('');
    }
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setName('');
      setDescription('');
    }
    onOpenChange(open);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        {trigger || (
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Portfolio
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Create Crypto Portfolio</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Portfolio Name</Label>
            <Input
              id="name"
              placeholder="My Crypto Portfolio"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description (Optional)</Label>
            <Textarea
              id="description"
              placeholder="A brief description of your crypto portfolio..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>
          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isCreating}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!name.trim() || isCreating}
              className="flex-1"
            >
              {isCreating ? 'Creating...' : 'Create Portfolio'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}