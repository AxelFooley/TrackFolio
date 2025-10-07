// Crypto Paper Wallet Types

export interface CryptoPortfolio {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  total_value_usd: number;
  total_cost_usd: number;
  total_profit_usd: number;
  total_profit_pct: number;
  irr: number;
  currency: string;
}

export interface CryptoHolding {
  id: number;
  portfolio_id: number;
  symbol: string;
  name: string | null;
  quantity: number;
  average_cost_usd: number;
  cost_basis_usd: number;
  current_price_usd: number;
  current_value_usd: number;
  unrealized_profit_usd: number;
  unrealized_profit_pct: number;
  last_updated: string;
}

export interface CryptoTransaction {
  id: number;
  portfolio_id: number;
  transaction_type: 'buy' | 'sell' | 'transfer_in' | 'transfer_out';
  symbol: string;
  quantity: number;
  price_usd: number;
  total_usd: number;
  fee_usd: number;
  transaction_date: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateCryptoTransaction {
  portfolio_id: number;
  transaction_type: 'buy' | 'sell' | 'transfer_in' | 'transfer_out';
  symbol: string;
  quantity: number;
  price_usd: number;
  fee_usd: number;
  transaction_date: string;
  notes?: string;
}

export interface UpdateCryptoTransaction {
  transaction_type?: 'buy' | 'sell' | 'transfer_in' | 'transfer_out';
  symbol?: string;
  quantity?: number;
  price_usd?: number;
  fee_usd?: number;
  transaction_date?: string;
  notes?: string;
}

export interface CreateCryptoPortfolio {
  name: string;
  description?: string;
}

export interface UpdateCryptoPortfolio {
  name?: string;
  description?: string;
}

export interface CryptoPerformanceDataPoint {
  date: string;
  value_usd: number;
}

export interface CryptoPortfolioPerformance {
  portfolio_data: CryptoPerformanceDataPoint[];
  start_value: number;
  end_value: number;
  change_amount: number;
  change_pct: number;
}

export interface CryptoPriceData {
  symbol: string;
  current_price_usd: number;
  price_change_24h: number;
  price_change_pct_24h: number;
  last_updated: string;
}

export interface CryptoAssetAllocation {
  symbol: string;
  name: string | null;
  value_usd: number;
  allocation_pct: number;
  quantity: number;
}

// Transaction type display mapping
export const CryptoTransactionTypeLabels = {
  buy: 'Buy',
  sell: 'Sell',
  transfer_in: 'Transfer In',
  transfer_out: 'Transfer Out',
} as const;

// Transaction type colors for badges
export const CryptoTransactionTypeColors = {
  buy: 'bg-green-100 text-green-800',
  sell: 'bg-red-100 text-red-800',
  transfer_in: 'bg-blue-100 text-blue-800',
  transfer_out: 'bg-orange-100 text-orange-800',
} as const;