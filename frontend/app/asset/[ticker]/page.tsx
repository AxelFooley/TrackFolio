'use client';

import { useParams } from 'next/navigation';
import { useAssetDetail } from '@/hooks/useAsset';
import { AssetHeader } from '@/components/Asset/AssetHeader';
import { PositionSummary } from '@/components/Asset/PositionSummary';
import { PriceChart } from '@/components/Asset/PriceChart';
import { TransactionHistory } from '@/components/Asset/TransactionHistory';
import { Loader2 } from 'lucide-react';

/**
 * Render the asset detail page for the route's ticker, handling loading, error, and success states.
 *
 * When loading, displays a centered spinner; on error or missing data, displays an "Asset Not Found" message
 * mentioning the ticker; otherwise renders a layout containing AssetHeader, PositionSummary, PriceChart, and TransactionHistory.
 *
 * @returns The page's JSX element representing the asset detail view for the current ticker.
 */
export default function AssetDetailPage() {
  const params = useParams();
  const ticker = params?.ticker as string;
  const { data: assetData, isLoading, error } = useAssetDetail(ticker);

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-center h-96">
          <Loader2 className="h-12 w-12 animate-spin text-primary" />
        </div>
      </div>
    );
  }

  if (error || !assetData) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Asset Not Found</h2>
          <p className="text-gray-600">
            Unable to load data for {ticker}. The asset may not exist in your portfolio.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        <AssetHeader position={assetData} />
        <PositionSummary position={assetData} />
        <PriceChart ticker={ticker} position={assetData} />
        <TransactionHistory ticker={ticker} />
      </div>
    </div>
  );
}