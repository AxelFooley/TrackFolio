'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { AlertCircle, Edit3 } from 'lucide-react';
import { updateCryptoPortfolio, validateCryptoPortfolioUpdate } from '@/lib/api/crypto-paper';
import type { CryptoPortfolio, UpdateCryptoPortfolio } from '@/types/crypto-paper';

interface EditPortfolioModalProps {
  portfolio: CryptoPortfolio;
  onPortfolioUpdated: () => void;
  trigger?: React.ReactNode;
}

export function EditPortfolioModal({
  portfolio,
  onPortfolioUpdated,
  trigger
}: EditPortfolioModalProps) {
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const [formData, setFormData] = useState<UpdateCryptoPortfolio>({
    name: portfolio.name,
    description: portfolio.description || '',
  });

  // Reset form when portfolio changes or dialog opens
  useEffect(() => {
    if (open) {
      setFormData({
        name: portfolio.name,
        description: portfolio.description || '',
      });
      setErrors({});
    }
  }, [open, portfolio]);

  const resetForm = () => {
    setFormData({
      name: portfolio.name,
      description: portfolio.description || '',
    });
    setErrors({});
  };

  const validateForm = (): boolean => {
    const validation = validateCryptoPortfolioUpdate(formData);

    if (!validation.is_valid) {
      const newErrors: Record<string, string> = {};
      validation.errors.forEach(error => {
        newErrors[error.field] = error.message;
      });
      setErrors(newErrors);
      return false;
    }

    setErrors({});
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);
    try {
      // Only include fields that have actually changed
      const updateData: UpdateCryptoPortfolio = {};

      if (formData.name !== portfolio.name) {
        updateData.name = formData.name?.trim();
      }

      if (formData.description !== portfolio.description) {
        updateData.description = formData.description?.trim() || undefined;
      }

      // Check if anything actually changed
      if (Object.keys(updateData).length === 0) {
        setErrors({ submit: 'No changes detected' });
        return;
      }

      await updateCryptoPortfolio(portfolio.id, updateData);

      onPortfolioUpdated();
      setOpen(false);
      resetForm();
    } catch (error) {
      console.error('Error updating portfolio:', error);
      setErrors({
        submit: error instanceof Error ? error.message : 'Failed to update portfolio'
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (field: keyof UpdateCryptoPortfolio, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));

    // Clear field-specific error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const hasChanges = () => {
    return formData.name?.trim() !== portfolio.name ||
           formData.description?.trim() !== (portfolio.description || '');
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm">
            <Edit3 className="h-4 w-4 mr-2" />
            Edit
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Edit Portfolio</DialogTitle>
          <DialogDescription>
            Update your portfolio name and description.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Portfolio Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Portfolio Name *</Label>
            <Input
              id="name"
              placeholder="Enter portfolio name"
              value={formData.name || ''}
              onChange={(e) => handleInputChange('name', e.target.value)}
              maxLength={100}
              className={errors.name ? 'border-red-500' : ''}
              aria-invalid={!!errors.name}
              aria-describedby={errors.name ? 'name-error' : undefined}
            />
            <div className="flex justify-between items-center">
              {errors.name && (
                <p id="name-error" className="text-sm text-red-600 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  {errors.name}
                </p>
              )}
              <span className="text-xs text-muted-foreground ml-auto">
                {formData.name?.length || 0}/100
              </span>
            </div>
          </div>

          {/* Portfolio Description */}
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              placeholder="Add a description for your portfolio (optional)"
              value={formData.description || ''}
              onChange={(e) => handleInputChange('description', e.target.value)}
              maxLength={500}
              rows={3}
              className={errors.description ? 'border-red-500' : ''}
              aria-invalid={!!errors.description}
              aria-describedby={errors.description ? 'description-error' : undefined}
            />
            <div className="flex justify-between items-center">
              {errors.description && (
                <p id="description-error" className="text-sm text-red-600 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  {errors.description}
                </p>
              )}
              <span className="text-xs text-muted-foreground ml-auto">
                {formData.description?.length || 0}/500
              </span>
            </div>
          </div>

          {/* Error Message */}
          {errors.submit && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-600 flex items-center gap-2">
                <AlertCircle className="h-4 w-4" />
                {errors.submit}
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setOpen(false);
                resetForm();
              }}
              disabled={isLoading}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isLoading || !hasChanges()}
              className="flex-1"
            >
              {isLoading ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}