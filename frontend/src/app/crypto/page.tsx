'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useCryptoPortfolios, useCreateCryptoPortfolio, useUpdateCryptoPortfolio, useDeleteCryptoPortfolio } from '@/hooks/useCrypto';
import { formatCurrency, formatPercentage, formatDate, validateBitcoinAddress, formatBitcoinAddress, getWalletSyncStatusInfo } from '@/lib/utils';
import { Plus, Search, Bitcoin, TrendingUp, TrendingDown, Edit, Trash2, Wallet, RefreshCw } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import type { CryptoPortfolio } from '@/lib/types';

/**
 * Render the Crypto Portfolios management page with listing, search, create/edit/delete dialogs, and real-time Bitcoin wallet validation.
 *
 * Renders a responsive UI that fetches and displays crypto portfolios, supports filtering by name, creating new portfolios, editing existing ones, deleting portfolios with confirmation, and shows portfolio metrics and wallet status. Form submissions and wallet-address validation surface success and error feedback via toasts.
 *
 * @returns The rendered crypto portfolios page element
 */
export default function CryptoPortfoliosPage() {
  const router = useRouter();
  const { data: portfolios, isLoading } = useCryptoPortfolios();
  const createPortfolioMutation = useCreateCryptoPortfolio();
  const updatePortfolioMutation = useUpdateCryptoPortfolio();
  const deletePortfolioMutation = useDeleteCryptoPortfolio();
  const { toast } = useToast();

  // State for new portfolio form
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newPortfolio, setNewPortfolio] = useState({
    name: '',
    description: '',
    base_currency: 'USD' as 'USD' | 'EUR',
    wallet_address: '',
  });
  const [walletAddressValidation, setWalletAddressValidation] = useState<{ isValid: boolean; type?: string; error?: string } | null>(null);

  // State for edit portfolio form
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingPortfolio, setEditingPortfolio] = useState<CryptoPortfolio | null>(null);
  const [editFormData, setEditFormData] = useState({
    name: '',
    description: '',
    base_currency: 'USD' as 'USD' | 'EUR',
    wallet_address: '',
  });
  const [editWalletAddressValidation, setEditWalletAddressValidation] = useState<{ isValid: boolean; type?: string; error?: string } | null>(null);

  // State for delete confirmation
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deletingPortfolio, setDeletingPortfolio] = useState<CryptoPortfolio | null>(null);

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

    // Validate wallet address if provided
    if (newPortfolio.wallet_address.trim()) {
      const validation = validateBitcoinAddress(newPortfolio.wallet_address.trim());
      if (!validation.isValid) {
        toast({
          title: 'Invalid Bitcoin Address',
          description: validation.error || 'Please enter a valid Bitcoin address',
          variant: 'destructive',
        });
        return;
      }
    }

    try {
      const portfolioData = {
        name: newPortfolio.name,
        description: newPortfolio.description || null,
        base_currency: newPortfolio.base_currency,
        wallet_address: newPortfolio.wallet_address.trim() || null,
      };

      const createdPortfolio = await createPortfolioMutation.mutateAsync(portfolioData);
      toast({
        title: 'Portfolio Created',
        description: `${createdPortfolio.name} has been created successfully`,
      });
      setShowCreateDialog(false);
      setNewPortfolio({ name: '', description: '', base_currency: 'USD', wallet_address: '' });
      setWalletAddressValidation(null);
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

  const handleEditPortfolio = (portfolio: CryptoPortfolio) => {
    setEditingPortfolio(portfolio);
    setEditFormData({
      name: portfolio.name,
      description: portfolio.description || '',
      base_currency: portfolio.base_currency,
      wallet_address: portfolio.wallet_address || '',
    });
    setEditWalletAddressValidation(null);
    setShowEditDialog(true);
  };

  const handleUpdatePortfolio = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editFormData.name.trim() || !editingPortfolio) {
      toast({
        title: 'Validation Error',
        description: 'Portfolio name is required',
        variant: 'destructive',
      });
      return;
    }

    // Validate wallet address if provided
    if (editFormData.wallet_address.trim()) {
      const validation = validateBitcoinAddress(editFormData.wallet_address.trim());
      if (!validation.isValid) {
        toast({
          title: 'Invalid Bitcoin Address',
          description: validation.error || 'Please enter a valid Bitcoin address',
          variant: 'destructive',
        });
        return;
      }
    }

    try {
      const portfolioData = {
        name: editFormData.name,
        description: editFormData.description || null,
        base_currency: editFormData.base_currency,
        wallet_address: editFormData.wallet_address.trim() || null,
      };

      const updatedPortfolio = await updatePortfolioMutation.mutateAsync({
        id: editingPortfolio.id,
        data: portfolioData,
      });
      toast({
        title: 'Portfolio Updated',
        description: `${updatedPortfolio.name} has been updated successfully`,
      });
      setShowEditDialog(false);
      setEditingPortfolio(null);
      setEditFormData({ name: '', description: '', base_currency: 'USD', wallet_address: '' });
      setEditWalletAddressValidation(null);
    } catch (error: any) {
      toast({
        title: 'Update Failed',
        description: error.message || 'Failed to update portfolio',
        variant: 'destructive',
      });
    }
  };

  const handleDeleteClick = (portfolio: CryptoPortfolio) => {
    setDeletingPortfolio(portfolio);
    setShowDeleteDialog(true);
  };

  const handleDeletePortfolio = async () => {
    if (!deletingPortfolio) return;

    try {
      await deletePortfolioMutation.mutateAsync(deletingPortfolio.id);
      toast({
        title: 'Portfolio Deleted',
        description: `${deletingPortfolio.name} has been deleted successfully`,
      });
      setShowDeleteDialog(false);
      setDeletingPortfolio(null);
    } catch (error: any) {
      toast({
        title: 'Delete Failed',
        description: error.message || 'Failed to delete portfolio',
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
                  <div>
                    <Label htmlFor="wallet-address">Bitcoin Wallet Address (optional)</Label>
                    <Input
                      id="wallet-address"
                      value={newPortfolio.wallet_address}
                      onChange={(e) => {
                        const address = e.target.value;
                        setNewPortfolio({ ...newPortfolio, wallet_address: address });

                        // Validate address in real-time
                        if (address.trim()) {
                          const validation = validateBitcoinAddress(address.trim());
                          setWalletAddressValidation(validation);
                        } else {
                          setWalletAddressValidation(null);
                        }
                      }}
                      placeholder="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
                      className={walletAddressValidation && !walletAddressValidation.isValid ? 'border-red-500' : ''}
                    />
                    {walletAddressValidation && (
                      <p className={`text-xs mt-1 ${walletAddressValidation.isValid ? 'text-green-600' : 'text-red-600'}`}>
                        {walletAddressValidation.isValid
                          ? `Valid ${walletAddressValidation.type} address`
                          : walletAddressValidation.error
                        }
                      </p>
                    )}
                    <p className="text-xs text-gray-500 mt-1">
                      Supports Legacy (1), SegWit (3), and Bech32 (bc1) addresses
                    </p>
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
                    <div className="flex items-center gap-2">
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
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEditPortfolio(portfolio);
                          }}
                          title="Edit portfolio"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteClick(portfolio);
                          }}
                          title="Delete portfolio"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
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
                    {portfolio.wallet_address && (
                      <div className="border-t pt-3 mt-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Wallet className="h-4 w-4 text-orange-500" />
                            <span className="text-sm text-gray-600">Wallet:</span>
                            <span className="text-xs font-mono text-gray-700">
                              {formatBitcoinAddress(portfolio.wallet_address)}
                            </span>
                          </div>
                          {portfolio.wallet_sync_status && (
                            <div className="flex items-center gap-1">
                              {(() => {
                                const statusInfo = getWalletSyncStatusInfo(portfolio.wallet_sync_status);
                                return (
                                  <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs ${statusInfo.bgColor} ${statusInfo.color}`}>
                                    <span>{statusInfo.icon}</span>
                                    {statusInfo.label}
                                  </span>
                                );
                              })()}
                            </div>
                          )}
                        </div>
                        {portfolio.wallet_transaction_count !== null && portfolio.wallet_transaction_count !== undefined && (
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-xs text-gray-500">
                              {portfolio.wallet_transaction_count} transactions
                            </span>
                            {portfolio.last_wallet_sync && (
                              <span className="text-xs text-gray-500">
                                • Synced {formatDate(portfolio.last_wallet_sync, 'MMM dd')}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Edit Portfolio Dialog */}
        <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
          <DialogContent>
            <form onSubmit={handleUpdatePortfolio}>
              <DialogHeader>
                <DialogTitle>Edit Crypto Portfolio</DialogTitle>
                <DialogDescription>
                  Update your portfolio information
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="edit-name">Portfolio Name</Label>
                  <Input
                    id="edit-name"
                    value={editFormData.name}
                    onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                    placeholder="My Crypto Portfolio"
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="edit-description">Description (optional)</Label>
                  <Input
                    id="edit-description"
                    value={editFormData.description}
                    onChange={(e) => setEditFormData({ ...editFormData, description: e.target.value })}
                    placeholder="Long-term crypto investments"
                  />
                </div>
                <div>
                  <Label htmlFor="edit-currency">Base Currency</Label>
                  <Select
                    value={editFormData.base_currency}
                    onValueChange={(value: 'USD' | 'EUR') =>
                      setEditFormData({ ...editFormData, base_currency: value })
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
                <div>
                  <Label htmlFor="edit-wallet-address">Bitcoin Wallet Address (optional)</Label>
                  <Input
                    id="edit-wallet-address"
                    value={editFormData.wallet_address}
                    onChange={(e) => {
                      const address = e.target.value;
                      setEditFormData({ ...editFormData, wallet_address: address });

                      // Validate address in real-time
                      if (address.trim()) {
                        const validation = validateBitcoinAddress(address.trim());
                        setEditWalletAddressValidation(validation);
                      } else {
                        setEditWalletAddressValidation(null);
                      }
                    }}
                    placeholder="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
                    className={editWalletAddressValidation && !editWalletAddressValidation.isValid ? 'border-red-500' : ''}
                  />
                  {editWalletAddressValidation && (
                    <p className={`text-xs mt-1 ${editWalletAddressValidation.isValid ? 'text-green-600' : 'text-red-600'}`}>
                      {editWalletAddressValidation.isValid
                        ? `Valid ${editWalletAddressValidation.type} address`
                        : editWalletAddressValidation.error
                      }
                    </p>
                  )}
                  <p className="text-xs text-gray-500 mt-1">
                    Supports Legacy (1), SegWit (3), and Bech32 (bc1) addresses
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowEditDialog(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={updatePortfolioMutation.isPending}>
                  {updatePortfolioMutation.isPending ? 'Updating...' : 'Update Portfolio'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete Portfolio</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete "{deletingPortfolio?.name}"? This action cannot be undone and will permanently delete all transactions and data associated with this portfolio.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowDeleteDialog(false)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="destructive"
                onClick={handleDeletePortfolio}
                disabled={deletePortfolioMutation.isPending}
              >
                {deletePortfolioMutation.isPending ? 'Deleting...' : 'Delete Portfolio'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}