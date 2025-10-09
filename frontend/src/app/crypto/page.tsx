'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useCryptoPortfolios, useCreateCryptoPortfolio } from '@/hooks/useCrypto';
import { formatCurrency, formatPercentage, formatDate } from '@/lib/utils';
import { Plus, Search, Bitcoin, TrendingUp, TrendingDown, MoreHorizontal, Edit, Trash2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import type { CryptoPortfolio } from '@/lib/types';

export default function CryptoPortfoliosPage() {
  const router = useRouter();
  const { data: portfolios, isLoading } = useCryptoPortfolios();
  const createPortfolioMutation = useCreateCryptoPortfolio();
  const { toast } = useToast();

  // State for new portfolio form
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newPortfolio, setNewPortfolio] = useState({
    name: '',
    description: '',
    base_currency: 'USD' as 'USD' | 'EUR',
  });

  // Search state
  const [searchTerm, setSearchTerm] = useState('');

  const handleCreatePortfolio = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPortfolio.name.trim()) {
      toast({
        title: 'Validation Error',
        description: 'Portfolio name is required',
        variant: 'destructive',
      });
      return;
    }

    try {
      const createdPortfolio = await createPortfolioMutation.mutateAsync(newPortfolio);
      toast({
        title: 'Portfolio Created',
        description: `${createdPortfolio.name} has been created successfully`,
      });
      setShowCreateDialog(false);
      setNewPortfolio({ name: '', description: '', base_currency: 'USD' });
      // Navigate to the new portfolio
      router.push(`/crypto/${createdPortfolio.id}`);
    } catch (error: any) {
      toast({
        title: 'Creation Failed',
        description: error.message || 'Failed to create portfolio',
        variant: 'destructive',
      });
    }
  };

  const filteredPortfolios = portfolios?.filter((portfolio) =>
    portfolio.name.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          <div>
            <h1 className="text-3xl font-bold mb-2">Crypto Portfolios</h1>
            <p className="text-gray-600">Manage your cryptocurrency investment portfolios</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <Card key={i}>
                <CardHeader>
                  <div className="h-6 bg-gray-200 rounded animate-pulse w-32"></div>
                  <div className="h-4 bg-gray-200 rounded animate-pulse w-24"></div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="h-8 bg-gray-200 rounded animate-pulse"></div>
                    <div className="h-4 bg-gray-200 rounded animate-pulse w-20"></div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        {/* Header */}
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold mb-2">Crypto Portfolios</h1>
            <p className="text-gray-600">Manage your cryptocurrency investment portfolios</p>
          </div>
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                New Portfolio
              </Button>
            </DialogTrigger>
            <DialogContent>
              <form onSubmit={handleCreatePortfolio}>
                <DialogHeader>
                  <DialogTitle>Create New Crypto Portfolio</DialogTitle>
                  <DialogDescription>
                    Create a new portfolio to track your cryptocurrency investments
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="name">Portfolio Name</Label>
                    <Input
                      id="name"
                      value={newPortfolio.name}
                      onChange={(e) => setNewPortfolio({ ...newPortfolio, name: e.target.value })}
                      placeholder="My Crypto Portfolio"
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor="description">Description (optional)</Label>
                    <Input
                      id="description"
                      value={newPortfolio.description}
                      onChange={(e) => setNewPortfolio({ ...newPortfolio, description: e.target.value })}
                      placeholder="Long-term crypto investments"
                    />
                  </div>
                  <div>
                    <Label htmlFor="currency">Base Currency</Label>
                    <Select
                      value={newPortfolio.base_currency}
                      onValueChange={(value: 'USD' | 'EUR') =>
                        setNewPortfolio({ ...newPortfolio, base_currency: value })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select currency" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="USD">USD ($)</SelectItem>
                        <SelectItem value="EUR">EUR (€)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowCreateDialog(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={createPortfolioMutation.isPending}>
                    {createPortfolioMutation.isPending ? 'Creating...' : 'Create Portfolio'}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {/* Search */}
        <div className="relative w-96">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search portfolios..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* Portfolios Grid */}
        {filteredPortfolios.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-8">
                <Bitcoin className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {searchTerm ? 'No portfolios found' : 'No crypto portfolios yet'}
                </h3>
                <p className="text-gray-600 mb-4">
                  {searchTerm
                    ? 'Try adjusting your search terms'
                    : 'Create your first crypto portfolio to start tracking your investments'}
                </p>
                {!searchTerm && (
                  <Button onClick={() => setShowCreateDialog(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Create Portfolio
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredPortfolios.map((portfolio) => (
              <Card
                key={portfolio.id}
                className="cursor-pointer hover:shadow-lg transition-shadow"
                onClick={() => router.push(`/crypto/${portfolio.id}`)}
              >
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Bitcoin className="h-5 w-5 text-orange-500" />
                        {portfolio.name}
                      </CardTitle>
                      {portfolio.description && (
                        <CardDescription className="mt-1">
                          {portfolio.description}
                        </CardDescription>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      {portfolio.profit_percentage_usd !== undefined && portfolio.profit_percentage_usd !== null && (
                        <div className={`flex items-center text-sm ${
                          portfolio.profit_percentage_usd >= 0 ? 'text-success' : 'text-danger'
                        }`}>
                          {portfolio.profit_percentage_usd >= 0 ? (
                            <TrendingUp className="h-4 w-4" />
                          ) : (
                            <TrendingDown className="h-4 w-4" />
                          )}
                          {formatPercentage(portfolio.profit_percentage_usd)}
                        </div>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div>
                      <p className="text-sm text-gray-600">Total Value</p>
                      <p className="text-2xl font-bold">
                        {portfolio.base_currency === 'USD'
                          ? formatCurrency(portfolio.total_value_usd || 0, 'USD')
                          : formatCurrency(portfolio.total_value_eur || 0, 'EUR')}
                      </p>
                    </div>
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-sm text-gray-600">Total Profit</p>
                        <p className={`font-semibold ${
                          ((portfolio.base_currency === 'USD' ? portfolio.total_profit_usd : portfolio.total_profit_eur) || 0) >= 0
                            ? 'text-success'
                            : 'text-danger'
                        }`}>
                          {portfolio.base_currency === 'USD'
                            ? formatCurrency(portfolio.total_profit_usd || 0, 'USD')
                            : formatCurrency(portfolio.total_profit_eur || 0, 'EUR')}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-gray-500">
                          Created {formatDate(portfolio.created_at)}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}