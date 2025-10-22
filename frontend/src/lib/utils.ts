import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { format } from 'date-fns'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(
  amount: number | null | undefined,
  currency: string = 'EUR'
): string {
  if (amount === null || amount === undefined) return '—'

  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
}

export function formatPercentage(
  value: number | null | undefined,
  decimals: number = 2
): string {
  if (value === null || value === undefined) return '—'

  return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`
}

export function formatDate(
  date: string | Date,
  formatStr: string = 'MMM dd, yyyy'
): string {
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date
    return format(dateObj, formatStr)
  } catch {
    return '—'
  }
}

export function formatDateTime(
  date: string | Date,
  formatStr: string = 'MMM dd, yyyy HH:mm'
): string {
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date
    return format(dateObj, formatStr)
  } catch {
    return '—'
  }
}

export function formatNumber(
  value: number | null | undefined,
  decimals: number = 2
): string {
  if (value === null || value === undefined) return '—'

  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

export function formatCryptoQuantity(
  amount: number | null | undefined,
  decimals: number = 8
): string {
  if (amount === null || amount === undefined) return '—'

  // For very small amounts, show more decimals
  if (amount < 0.001) {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 8,
    }).format(amount)
  }

  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(amount)
}

export function formatChartDate(date: string | Date, timeRange: string = '1M'): string {
  try {
    const dateObj = typeof date === 'string' ? new Date(date) : date;

    // Format based on time range
    if (timeRange === '1D') {
      return format(dateObj, 'HH:mm');
    } else if (timeRange === '1W' || timeRange === '1M') {
      return format(dateObj, 'MMM dd');
    } else {
      return format(dateObj, 'MMM yyyy');
    }
  } catch {
    return '—';
  }
}

/**
 * Validates a Bitcoin address format
 * Supports Legacy (1), SegWit (3), and Bech32 (bc1) addresses
 */
export function validateBitcoinAddress(address: string): { isValid: boolean; type?: string; error?: string } {
  if (!address || typeof address !== 'string') {
    return { isValid: false, error: 'Address is required' };
  }

  const trimmed = address.trim();

  if (!trimmed) {
    return { isValid: false, error: 'Address is required' };
  }

  // Legacy addresses start with '1'
  if (trimmed.startsWith('1')) {
    // Legacy addresses are 26-35 characters long
    if (trimmed.length < 26 || trimmed.length > 35) {
      return { isValid: false, error: 'Invalid legacy address length' };
    }

    // Basic Base58 check for legacy addresses
    const base58Regex = /^[1-9A-HJ-NP-Za-km-z]+$/;
    if (!base58Regex.test(trimmed)) {
      return { isValid: false, error: 'Invalid legacy address format' };
    }

    return { isValid: true, type: 'Legacy (P2PKH)' };
  }

  // SegWit addresses start with '3'
  if (trimmed.startsWith('3')) {
    // SegWit addresses are 26-35 characters long
    if (trimmed.length < 26 || trimmed.length > 35) {
      return { isValid: false, error: 'Invalid SegWit address length' };
    }

    // Basic Base58 check for SegWit addresses
    const base58Regex = /^[1-9A-HJ-NP-Za-km-z]+$/;
    if (!base58Regex.test(trimmed)) {
      return { isValid: false, error: 'Invalid SegWit address format' };
    }

    return { isValid: true, type: 'SegWit (P2SH)' };
  }

  // Bech32 addresses start with 'bc1'
  if (trimmed.startsWith('bc1')) {
    // Bech32 addresses are 42-90 characters long
    if (trimmed.length < 42 || trimmed.length > 90) {
      return { isValid: false, error: 'Invalid Bech32 address length' };
    }

    // Basic Bech32 check
    const bech32Regex = /^bc1[ac-hj-np-z02-9]{8,87}$/;
    if (!bech32Regex.test(trimmed.toLowerCase())) {
      return { isValid: false, error: 'Invalid Bech32 address format' };
    }

    return { isValid: true, type: 'Bech32 (P2WPKH)' };
  }

  return { isValid: false, error: 'Address must start with 1, 3, or bc1' };
}

/**
 * Format Bitcoin address for display (show first 6 and last 4 characters)
 */
export function formatBitcoinAddress(address: string): string {
  if (!address || address.length < 10) {
    return address;
  }

  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

/**
 * Get wallet sync status display information
 */
export function getWalletSyncStatusInfo(status: string | null | undefined) {
  switch (status) {
    case 'synced':
      return {
        label: 'Synced',
        color: 'text-green-600',
        bgColor: 'bg-green-100',
        icon: '✓'
      };
    case 'syncing':
      return {
        label: 'Syncing',
        color: 'text-blue-600',
        bgColor: 'bg-blue-100',
        icon: '⟳'
      };
    case 'error':
      return {
        label: 'Error',
        color: 'text-red-600',
        bgColor: 'bg-red-100',
        icon: '✗'
      };
    case 'never':
      return {
        label: 'Never synced',
        color: 'text-gray-600',
        bgColor: 'bg-gray-100',
        icon: '○'
      };
    case 'disabled':
      return {
        label: 'Disabled',
        color: 'text-gray-500',
        bgColor: 'bg-gray-50',
        icon: '—'
      };
    default:
      return {
        label: 'Unknown',
        color: 'text-gray-500',
        bgColor: 'bg-gray-50',
        icon: '?'
      };
  }
}

// News utility functions
export function getSentimentInfo(sentiment: 'positive' | 'negative' | 'neutral') {
  switch (sentiment) {
    case 'positive':
      return {
        label: 'Positive',
        color: 'text-green-600',
        bgColor: 'bg-green-100',
        borderColor: 'border-green-200',
        icon: '▲'
      };
    case 'negative':
      return {
        label: 'Negative',
        color: 'text-red-600',
        bgColor: 'bg-red-100',
        borderColor: 'border-red-200',
        icon: '▼'
      };
    case 'neutral':
      return {
        label: 'Neutral',
        color: 'text-gray-600',
        bgColor: 'bg-gray-100',
        borderColor: 'border-gray-200',
        icon: '●'
      };
  }
}

export function formatRelevanceScore(score: number): string {
  if (score >= 0.8) return 'High';
  if (score >= 0.5) return 'Medium';
  return 'Low';
}

export function getRelevanceColor(score: number): string {
  if (score >= 0.8) return 'text-green-600';
  if (score >= 0.5) return 'text-yellow-600';
  return 'text-gray-600';
}

export function formatRelativeDate(date: string): string {
  const now = new Date();
  const publishDate = new Date(date);
  const diffMs = now.getTime() - publishDate.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffHours < 1) return 'Just now';
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return `${Math.floor(diffDays / 30)}mo ago`;
}

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength).trim() + '...';
}