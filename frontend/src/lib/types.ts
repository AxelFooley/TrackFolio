// Portfolio Types (existing)
export interface Position {
  ticker: string;
  isin: string;
  description: string | null;
  asset_type: string;
  quantity: number;
  average_cost: number | null;
  cost_basis: number | null;
  current_price: number | null;
  current_value: number | null;
  unrealized_gain: number | null;
  return_percentage: number | null;
  irr: number | null;
  currency: string;
  today_change?: number | null;
  today_change_percent?: number | null;
  last_calculated_at?: string;
  splits?: Array<{
    date: string;
    ratio: string;
    old_ticker: string;
    new_ticker: string;
  }>;
}

export interface PortfolioOverview {
  current_value: number;
  total_cost_basis: number;
  total_profit: number;
  currency: string;
  average_annual_return: number | null;
  today_gain_loss: number | null;
  today_gain_loss_pct: number | null;
}

export interface Transaction {
  id: number;
  operation_date: string;
  value_date: string;
  transaction_type: 'BUY' | 'SELL' | 'DIVIDEND' | 'FEE';
  ticker: string;
  isin: string | null;
  description: string;
  quantity: number;
  price_per_share: number;
  amount_eur: number;
  amount_currency: number;
  currency: string;
  fees: number;
  order_reference: string;
  transaction_hash: string;
  imported_at: string;
  created_at: string;
  updated_at: string;
}

export interface PerformanceData {
  date: string;
  portfolio: number;
  benchmark?: number;
}

export interface Benchmark {
  id: number;
  ticker: string;
  description: string | null;
}

export interface PriceUpdate {
  last_update: string | null;
}

// Transaction Forms
export interface TransactionCreate {
  isin: string;
  ticker: string;
  transaction_type: 'BUY' | 'SELL' | 'DIVIDEND' | 'FEE';
  quantity: number | null;
  amount: number | null;
  fees: number;
  date: string;
  currency: string;
  broker?: string | null;
  description?: string | null;
}

export interface TransactionUpdate {
  transaction_type?: 'BUY' | 'SELL' | 'DIVIDEND' | 'FEE';
  quantity?: number | null;
  amount?: number | null;
  fees?: number;
  date?: string;
  broker?: string | null;
  description?: string | null;
}

// Crypto Portfolio Types
export interface CryptoPortfolio {
  id: number;
  name: string;
  description: string | null;
  base_currency: 'USD' | 'EUR';
  created_at: string;
  updated_at: string;
  total_value_usd?: number;
  total_value_eur?: number;
  total_profit_usd?: number;
  total_profit_eur?: number;
  profit_percentage_usd?: number;
  profit_percentage_eur?: number;
  wallet_address?: string | null;
  wallet_sync_enabled?: boolean;
  last_wallet_sync?: string | null;
  wallet_transaction_count?: number | null;
  wallet_sync_status?: 'synced' | 'syncing' | 'error' | 'never' | 'disabled';
}

export interface CryptoPortfolioList {
  portfolios: CryptoPortfolio[];
  total_count: number;
}

export interface CryptoPosition {
  symbol: string;
  quantity: number;
  average_cost: number;
  cost_basis: number;
  current_price: number;
  current_value: number;
  unrealized_gain_loss: number;
  unrealized_gain_loss_pct: number | null;
  realized_gain_loss: number | null;
  first_purchase_date: string | null;
  last_transaction_date: string | null;
  // Optional fields for UI compatibility
  id?: number;
  portfolio_id?: number;
  asset_name?: string;
  currency?: 'USD' | 'EUR';
  last_updated?: string;
  // Aliases for backwards compatibility
  unrealized_gain?: number;
  return_percentage?: number;
}

export interface CryptoTransaction {
  id: number;
  portfolio_id: number;
  symbol: string;
  transaction_type: 'BUY' | 'SELL' | 'TRANSFER_IN' | 'TRANSFER_OUT';
  quantity: number;
  price_at_execution: number;
  fee: number;
  currency: 'USD' | 'EUR';
  timestamp: string;
  exchange?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  total_amount?: number;
  fee_currency?: string | null;
  transaction_hash?: string | null;
}

export interface CryptoPrice {
  symbol: string;
  current_price: number;
  price_change_24h: number;
  price_change_percentage_24h: number;
  market_cap: number;
  volume_24h: number;
  currency: 'USD' | 'EUR';
  last_updated: string;
}

export interface CryptoPriceHistory {
  timestamp: string;
  price: number;
  volume?: number;
}

export interface CryptoPerformanceData {
  date: string;
  portfolio_value: number;
  benchmark_value?: number;
}

export interface CryptoPortfolioMetrics {
  total_value: number;
  total_cost_basis: number;
  total_profit: number;
  profit_percentage: number;
  best_performer: CryptoPosition | null;
  worst_performer: CryptoPosition | null;
  largest_position: CryptoPosition | null;
  asset_allocation: Array<{
    symbol: string;
    name: string;
    value: number;
    percentage: number;
  }>;
}

// Crypto Forms
export interface CryptoPortfolioCreate {
  name: string;
  description?: string | null;
  base_currency: 'USD' | 'EUR';
  wallet_address?: string | null;
}

export interface CryptoPortfolioUpdate {
  name?: string;
  description?: string | null;
  base_currency?: 'USD' | 'EUR';
  wallet_address?: string | null;
}

export interface CryptoTransactionCreate {
  symbol: string;
  transaction_type: 'BUY' | 'SELL' | 'TRANSFER_IN' | 'TRANSFER_OUT';
  quantity: number;
  price_at_execution: number;
  fee: number;
  currency: 'USD' | 'EUR';
  timestamp: string;
  exchange?: string | null;
  notes?: string | null;
}

export interface CryptoTransactionUpdate {
  transaction_type?: 'BUY' | 'SELL' | 'TRANSFER_IN' | 'TRANSFER_OUT';
  quantity?: number;
  price_at_execution?: number;
  fee?: number;
  currency?: 'USD' | 'EUR';
  timestamp?: string;
  exchange?: string | null;
  notes?: string | null;
}

// Common Types
export type TimeRange = '1D' | '1W' | '1M' | '3M' | '6M' | '1Y' | 'YTD' | 'ALL';

// API Response Types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

// Realtime Price Types
export interface RealtimePrice {
  symbol: string;
  current_price: number;
  previous_close: number;
  change_amount?: number;
  change_percent?: number;
  currency: string;
  last_updated: string;
}

export interface RealtimePriceResponse {
  prices: RealtimePrice[];
  fetched_count: number;
  total_count: number;
  timestamp: string;
}

// Asset Search Types
export interface TickerSearchResult {
  ticker: string;
  name: string;
  type: string;
}

// Unified Holdings Types (Traditional + Crypto)
export type AssetType = 'STOCK' | 'ETF' | 'CRYPTO';

export interface UnifiedHolding {
  id: string;
  type: AssetType;
  ticker: string;
  isin?: string;
  name?: string;
  quantity: number;
  current_price: number;
  current_value: number;
  average_cost: number;
  total_cost: number;
  profit_loss: number;
  profit_loss_pct: number;
  currency: string;
  portfolio_id?: number;
  portfolio_name?: string;
  today_change?: number;
  today_change_percent?: number;
}

export interface UnifiedOverview {
  total_value: number;
  traditional_value: number;
  crypto_value: number;
  total_cost: number;
  total_profit: number;
  total_profit_pct: number;
  today_change: number;
  today_change_pct: number;
  currency: string;
}

export interface UnifiedPerformanceData {
  date: string;
  total: number;
  traditional: number;
  crypto: number;
  benchmark?: number;
  currency?: string;
}

export interface UnifiedMover {
  id: string;
  type: AssetType;
  ticker: string;
  name?: string;
  current_value: number;
  today_change: number;
  today_change_percent: number;
  currency: string;
  portfolio_name?: string;
}

// Unified Holdings Types (Traditional + Crypto)
export type AssetType = 'STOCK' | 'ETF' | 'CRYPTO';

export interface UnifiedHolding {
  id: string;
  type: AssetType;
  ticker: string;
  isin?: string;
  name?: string;
  quantity: number;
  current_price: number;
  current_value: number;
  average_cost: number;
  total_cost: number;
  profit_loss: number;
  profit_loss_pct: number;
  currency: string;
  portfolio_id?: number;
  portfolio_name?: string;
  today_change?: number;
  today_change_percent?: number;
}

export interface UnifiedOverview {
  total_value: number;
  traditional_value: number;
  crypto_value: number;
  total_cost: number;
  total_profit: number;
  total_profit_pct: number;
  today_change: number;
  today_change_pct: number;
  currency: string;
}

export interface UnifiedPerformanceData {
  date: string;
  total: number;
  traditional: number;
  crypto: number;
  benchmark?: number;
  currency?: string;
}

export interface UnifiedMover {
  id: string;
  type: AssetType;
  ticker: string;
  name?: string;
  current_value: number;
  today_change: number;
  today_change_percent: number;
  currency: string;
  portfolio_name?: string;
}

// Wallet Types
export interface WalletSyncStatus {
  status: 'synced' | 'syncing' | 'error' | 'never' | 'disabled';
  last_sync?: string | null;
  transaction_count?: number;
  error_message?: string | null;
}

export interface WalletTransaction {
  txid: string;
  blockhash: string;
  block_height: number;
  confirmations: number;
  timestamp: number;
  size: number;
  weight: number;
  fee: number;
  status: 'confirmed' | 'unconfirmed';
  inputs: Array<{
    txid: string;
    vout: number;
    script_sig: string;
    value: number;
    address?: string;
  }>;
  outputs: Array<{
    script_pubkey: string;
    value: number;
    address?: string;
  }>;
}

export interface WalletTransactionPreview {
  total_transactions: number;
  transactions: WalletTransaction[];
  total_value: number;
  last_transaction?: string;
}