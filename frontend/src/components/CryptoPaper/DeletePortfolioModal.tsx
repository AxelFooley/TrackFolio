'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import {
  AlertTriangle,
  X,
  Wallet,
  TrendingDown,
  FileText,
  Database,
  Loader2
} from 'lucide-react';
import { deleteCryptoPortfolio } from '@/lib/api/crypto-paper';
import type { CryptoPortfolio, CryptoTransaction, CryptoHolding } from '@/types/crypto-paper';

interface DeletePortfolioModalProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  portfolio: CryptoPortfolio | null;
  transactionCount?: number;
  holdingCount?: number;
  onSuccess?: () => void;
  onError?: (error: string) => void;
}

export function DeletePortfolioModal({
  isOpen,
  onOpenChange,
  portfolio,
  transactionCount = 0,
  holdingCount = 0,
  onSuccess,
  onError,
}: DeletePortfolioModalProps) {
  const [confirmationText, setConfirmationText] = useState('');
  const [isChecked, setIsChecked] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showFinalWarning, setShowFinalWarning] = useState(false);

  // Reset form state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setConfirmationText('');
      setIsChecked(false);
      setError(null);
      setShowFinalWarning(false);
    }
  }, [isOpen]);

  const handleDelete = async () => {
    if (!portfolio) return;

    // Double-check confirmation
    if (confirmationText !== portfolio.name || !isChecked) {
      setError('Please complete all confirmation steps');
      return;
    }

    try {
      setIsDeleting(true);
      setError(null);

      await deleteCryptoPortfolio(portfolio.id);

      // Close modal and call success callback
      onOpenChange(false);
      onSuccess?.();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete portfolio';
      setError(errorMessage);
      onError?.(errorMessage);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleProceedToDelete = () => {
    if (confirmationText === portfolio?.name && isChecked) {
      setShowFinalWarning(true);
    }
  };

  const handleCancel = () => {
    onOpenChange(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      handleCancel();
    }
  };

  if (!portfolio) return null;

  const canProceed = confirmationText === portfolio.name && isChecked && !isDeleting;
  const hasTransactions = transactionCount > 0;
  const hasHoldings = holdingCount > 0;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-2xl max-h-[90vh] overflow-y-auto"
        onKeyDown={handleKeyDown}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-600">
            <AlertTriangle className="h-5 w-5" />
            Delete Crypto Portfolio
          </DialogTitle>
          <DialogDescription className="text-left">
            This action will permanently delete the portfolio and all associated data.
          </DialogDescription>
        </DialogHeader>

        {!showFinalWarning ? (
          <div className="space-y-6">
            {/* Portfolio Information */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Wallet className="h-4 w-4" />
                Portfolio to be Deleted
              </h3>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-gray-600">Name:</span>
                  <span className="font-mono text-sm bg-red-50 text-red-700 px-2 py-1 rounded">
                    {portfolio.name}
                  </span>
                </div>
                {portfolio.description && (
                  <div className="flex justify-between items-start">
                    <span className="text-sm font-medium text-gray-600">Description:</span>
                    <span className="text-sm text-gray-900 max-w-xs text-right">
                      {portfolio.description}
                    </span>
                  </div>
                )}
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-gray-600">Current Value:</span>
                  <span className="font-semibold text-gray-900">
                    ${portfolio.total_value_usd.toLocaleString('en-US', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2
                    })}
                  </span>
                </div>
              </div>
            </div>

            {/* Data Loss Warning */}
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <h3 className="font-semibold text-red-800 mb-3 flex items-center gap-2">
                <TrendingDown className="h-4 w-4" />
                Data That Will Be Permanently Lost
              </h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-red-700">Portfolio information</span>
                  <Badge variant="destructive" className="text-xs">
                    Permanent
                  </Badge>
                </div>
                {hasTransactions && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-red-700">
                      {transactionCount} transaction{transactionCount !== 1 ? 's' : ''}
                    </span>
                    <Badge variant="destructive" className="text-xs">
                      Permanent
                    </Badge>
                  </div>
                )}
                {hasHoldings && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-red-700">
                      {holdingCount} holding{holdingCount !== 1 ? 's' : ''}
                    </span>
                    <Badge variant="destructive" className="text-xs">
                      Permanent
                    </Badge>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-red-700">Performance history</span>
                  <Badge variant="destructive" className="text-xs">
                    Permanent
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-red-700">All associated data</span>
                  <Badge variant="destructive" className="text-xs">
                    Permanent
                  </Badge>
                </div>
              </div>
            </div>

            {/* Critical Warning */}
            <Alert className="border-red-200 bg-red-50">
              <AlertTriangle className="h-4 w-4 text-red-600" />
              <AlertDescription className="text-red-800">
                <strong>Critical Warning:</strong> This action is irreversible.
                Once deleted, the portfolio and all its data cannot be recovered.
                There is no undo functionality.
              </AlertDescription>
            </Alert>

            {/* Confirmation Steps */}
            <div className="space-y-4">
              <h3 className="font-semibold text-gray-900">Confirmation Required</h3>

              {/* Step 1: Type portfolio name */}
              <div className="space-y-2">
                <Label htmlFor="confirmation-text" className="text-sm font-medium text-gray-700">
                  Step 1: Type the portfolio name to confirm deletion
                </Label>
                <Input
                  id="confirmation-text"
                  value={confirmationText}
                  onChange={(e) => setConfirmationText(e.target.value)}
                  placeholder={`Type "${portfolio.name}" to continue`}
                  className="font-mono"
                  autoComplete="off"
                />
                <p className="text-xs text-gray-500">
                  This ensures you understand which portfolio is being deleted.
                </p>
              </div>

              {/* Step 2: Acknowledge understanding */}
              <div className="flex items-start space-x-3">
                <Checkbox
                  id="acknowledge"
                  checked={isChecked}
                  onCheckedChange={(checked: boolean | string) => setIsChecked(checked as boolean)}
                />
                <div className="space-y-1">
                  <Label htmlFor="acknowledge" className="text-sm font-medium text-gray-700 cursor-pointer">
                    Step 2: I understand this action cannot be undone
                  </Label>
                  <p className="text-xs text-gray-500">
                    I acknowledge that I am permanently deleting this portfolio and all associated data,
                    and this action cannot be reversed.
                  </p>
                </div>
              </div>
            </div>

            {/* Error Display */}
            {error && (
              <Alert className="border-red-200 bg-red-50">
                <AlertTriangle className="h-4 w-4 text-red-600" />
                <AlertDescription className="text-red-800">
                  {error}
                </AlertDescription>
              </Alert>
            )}

            {/* Action Buttons */}
            <DialogFooter className="flex-col-reverse sm:flex-row gap-2">
              <Button
                variant="outline"
                onClick={handleCancel}
                disabled={isDeleting}
                className="w-full sm:w-auto"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleProceedToDelete}
                disabled={!canProceed}
                className="w-full sm:w-auto"
              >
                Review Final Warning
              </Button>
            </DialogFooter>
          </div>
        ) : (
          /* Final Warning Screen */
          <div className="space-y-6">
            <div className="text-center space-y-4">
              <div className="mx-auto w-16 h-16 bg-red-100 rounded-full flex items-center justify-center">
                <AlertTriangle className="h-8 w-8 text-red-600" />
              </div>

              <h3 className="text-xl font-bold text-red-800">
                Final Confirmation Required
              </h3>

              <p className="text-gray-700">
                You are about to permanently delete:
              </p>

              <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-left">
                <div className="space-y-1">
                  <p className="font-mono text-red-800 font-semibold">
                    &quot;{portfolio.name}&quot;
                  </p>
                  {portfolio.description && (
                    <p className="text-sm text-gray-600">
                      {portfolio.description}
                    </p>
                  )}
                  {hasTransactions && (
                    <p className="text-sm text-red-700">
                      • {transactionCount} transaction{transactionCount !== 1 ? 's' : ''}
                    </p>
                  )}
                  {hasHoldings && (
                    <p className="text-sm text-red-700">
                      • {holdingCount} holding{holdingCount !== 1 ? 's' : ''}
                    </p>
                  )}
                </div>
              </div>

              <div className="bg-gray-100 border border-gray-200 rounded-lg p-4">
                <p className="text-sm text-gray-800 font-medium">
                  This is your last chance to cancel.
                </p>
                <p className="text-xs text-gray-600 mt-1">
                  Click &quot;Cancel&quot; to keep this portfolio, or &quot;Delete Permanently&quot; to proceed.
                </p>
              </div>
            </div>

            {/* Final Action Buttons */}
            <DialogFooter className="flex-col-reverse sm:flex-row gap-2">
              <Button
                variant="outline"
                onClick={() => setShowFinalWarning(false)}
                disabled={isDeleting}
                className="w-full sm:w-auto"
              >
                Go Back
              </Button>
              <Button
                variant="outline"
                onClick={handleCancel}
                disabled={isDeleting}
                className="w-full sm:w-auto"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={isDeleting}
                className="w-full sm:w-auto min-w-[140px]"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  'Delete Permanently'
                )}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}