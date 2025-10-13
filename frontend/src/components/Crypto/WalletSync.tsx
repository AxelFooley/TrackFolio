'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useWalletSyncStatus, useSyncWallet } from '@/hooks/useCrypto';
import { formatDateTime, getWalletSyncStatusInfo } from '@/lib/utils';
import { Wallet, RefreshCw, AlertCircle, CheckCircle } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface WalletSyncProps {
  portfolioId: number;
  walletAddress: string;
}

/**
 * Renders a card UI that displays Bitcoin wallet synchronization status and actions for the given portfolio.
 *
 * Shows current sync state, last sync time, transaction count, error messages, and a control to initiate a wallet sync.
 *
 * @param portfolioId - The portfolio identifier used to fetch and trigger wallet sync operations.
 * @param walletAddress - The Bitcoin wallet address to display (truncated in the UI) or undefined if not configured.
 * @returns A React element rendering the wallet sync card with status details and sync controls.
 */
export function WalletSync({ portfolioId, walletAddress }: WalletSyncProps) {
  const { data: syncStatus, isLoading: statusLoading } = useWalletSyncStatus(portfolioId);
  const syncWalletMutation = useSyncWallet();
  const { toast } = useToast();

  const handleSync = async () => {
    try {
      await syncWalletMutation.mutateAsync(portfolioId);
      toast({
        title: 'Wallet Sync Started',
        description: 'Syncing your Bitcoin wallet transactions...',
      });
    } catch (error: any) {
      toast({
        title: 'Sync Failed',
        description: error.message || 'Failed to sync wallet',
        variant: 'destructive',
      });
    }
  };

  const statusInfo = syncStatus ? getWalletSyncStatusInfo(syncStatus.status) : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wallet className="h-5 w-5 text-orange-500" />
          Bitcoin Wallet Sync
        </CardTitle>
        <CardDescription>
          {walletAddress ? `Wallet: ${walletAddress.slice(0, 10)}...${walletAddress.slice(-4)}` : 'No wallet configured'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Sync Status */}
          {statusLoading ? (
            <div className="flex items-center gap-2 text-gray-500">
              <RefreshCw className="h-4 w-4 animate-spin" />
              <span>Loading sync status...</span>
            </div>
          ) : syncStatus ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {statusInfo && (
                    <Badge variant="secondary" className={`${statusInfo.bgColor} ${statusInfo.color}`}>
                      <span className="mr-1">{statusInfo.icon}</span>
                      {statusInfo.label}
                    </Badge>
                  )}
                  {syncStatus.status === 'syncing' && (
                    <RefreshCw className="h-4 w-4 animate-spin text-blue-500" />
                  )}
                </div>
                <Button
                  size="sm"
                  onClick={handleSync}
                  disabled={syncWalletMutation.isPending || syncStatus.status === 'syncing'}
                >
                  {syncWalletMutation.isPending || syncStatus.status === 'syncing' ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      Syncing...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Sync Now
                    </>
                  )}
                </Button>
              </div>

              {/* Status Details */}
              <div className="text-sm space-y-1">
                {syncStatus.last_sync && (
                  <div className="flex items-center gap-2 text-gray-600">
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    <span>Last sync: {formatDateTime(syncStatus.last_sync)}</span>
                  </div>
                )}

                {syncStatus.transaction_count !== null && syncStatus.transaction_count !== undefined && (
                  <div className="text-gray-600">
                    <span className="font-medium">{syncStatus.transaction_count}</span> transactions synced
                  </div>
                )}

                {syncStatus.error_message && (
                  <div className="flex items-start gap-2 text-red-600 bg-red-50 p-2 rounded">
                    <AlertCircle className="h-4 w-4 mt-0.5" />
                    <span className="text-xs">{syncStatus.error_message}</span>
                  </div>
                )}

                {syncStatus.status === 'never' && (
                  <div className="text-gray-500 text-xs">
                    This wallet has never been synced. Click &quot;Sync Now&quot; to import your Bitcoin transactions.
                  </div>
                )}

                {syncStatus.status === 'disabled' && (
                  <div className="text-gray-500 text-xs">
                    Wallet sync is disabled for this portfolio.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-gray-500 text-sm">
              Unable to fetch wallet sync status.
            </div>
          )}

          {/* Help Text */}
          <div className="text-xs text-gray-500 border-t pt-3">
            <p className="mb-1">
              <strong>Wallet Sync</strong> automatically imports your Bitcoin transaction history from the blockchain.
            </p>
            <p>
              This helps track your crypto holdings and calculate accurate profit/loss metrics.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}