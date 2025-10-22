'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useHoldings } from '@/hooks/usePortfolio';
import { useRealtimePrices } from '@/hooks/useRealtimePrices';
import { useMoversNews } from '@/hooks/useAlphaVantageNews';
import { formatCurrency, formatPercentage } from '@/lib/utils';
import { TrendingUp, TrendingDown, ChevronDown, ChevronUp, AlertTriangle, ExternalLink } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { MoversNewsResponse, NewsFetchResult, NewsArticleDetail } from '@/lib/types/news';

/**
 * Render a card showing the top daily gainers and losers from the user's holdings with integrated news.
 *
 * Computes current value, unrealized gain, today's total position change, and today's percentage change using holdings and real-time price data, then displays the top three gainers and top three losers. Integrates news for movers with sentiment indicators and toggleable news section.
 *
 * @returns A React element displaying today's movers (top gainers and top losers) with current value, today's change, and integrated news.
 */
export function TodaysMovers() {
  const { data: holdings, isLoading: isLoadingHoldings } = useHoldings();
  const symbols = (holdings && Array.isArray(holdings)) ? holdings.map(h => h.ticker) : [];
  const { realtimePrices } = useRealtimePrices(symbols);
  const [showNews, setShowNews] = useState(false);

  // Fetch news for top movers
  const {
    data: moversNews,
    isLoading: isLoadingNews,
    error: newsError,
    refetch: refetchNews
  } = useMoversNews({
    limit: 10,
    minChangePercent: 2.0,
    quality: 'high',
    enabled: symbols.length > 0
  });

  // Extract news from movers response
  const tickerNewsMap = useMemo(() => {
    if (!moversNews || !moversNews.movers || !Array.isArray(moversNews.movers)) return new Map<string, NewsArticleDetail[]>();

    const map = new Map<string, NewsArticleDetail[]>();
    moversNews.movers.forEach((mover) => {
      if (!mover || typeof mover !== 'object') return;
      if (mover.success && mover.articles && Array.isArray(mover.articles) && mover.articles.length > 0) {
        map.set(mover.ticker, mover.articles.slice(0, 3)); // Limit to 3 articles per ticker
      }
    });
    return map;
  }, [moversNews]);

  // Merge holdings with real-time data for consistency
  const holdingsWithRealtimeData = useMemo(() => {
    if (!holdings || !Array.isArray(holdings)) return [];

    return holdings.map((holding) => {
      if (!holding || typeof holding !== 'object') return holding;

      const realtimePrice = realtimePrices.get(holding.ticker);

      if (realtimePrice) {
        // Calculate updated values with real-time price
        const currentValue = holding.quantity * realtimePrice.current_price;
        const costBasis = holding.cost_basis || 0;
        const unrealizedGain = currentValue - costBasis;
        const returnPercentage = costBasis > 0
          ? unrealizedGain / costBasis
          : 0;

        // Calculate change values if not provided
        const hasPrevClose = typeof realtimePrice.previous_close === 'number';
        const changeAmount = realtimePrice.change_amount ??
          (hasPrevClose ? (realtimePrice.current_price - realtimePrice.previous_close) : 0);
        const changePercent = realtimePrice.change_percent ??
        (realtimePrice.previous_close && realtimePrice.previous_close > 0 ?
            ((realtimePrice.current_price - realtimePrice.previous_close) / realtimePrice.previous_close) * 100 : 0);

        return {
          ...holding,
          current_price: realtimePrice.current_price,
          current_value: currentValue,
          unrealized_gain: unrealizedGain,
          return_percentage: returnPercentage,
          // Total position change (not per-share)
          today_change: changeAmount * holding.quantity,
          today_change_percent: changePercent,
        };
      }

      return holding;
    });
  }, [holdings, realtimePrices]);

  // Filter holdings with today_change_percent and sort
  const holdingsWithChange = useMemo(() => {
    return holdingsWithRealtimeData
      .filter((h) => h.today_change_percent !== null && h.today_change_percent !== undefined && h.today_change_percent !== 0)
      .sort((a, b) => (b.today_change_percent || 0) - (a.today_change_percent || 0));
  }, [holdingsWithRealtimeData]);

  const gainers = useMemo(() => holdingsWithChange.filter(h => (h.today_change_percent || 0) > 0).slice(0, 3), [holdingsWithChange]);
  const losers = useMemo(() => {
    const filteredLosers = holdingsWithChange.filter(h => (h.today_change_percent || 0) < 0);
    return [...filteredLosers].sort((a, b) => (a.today_change_percent || 0) - (b.today_change_percent || 0)).slice(0, 3);
  }, [holdingsWithChange]);

  // Handle loading and empty states
  if (isLoadingHoldings) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s Movers</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-200 rounded"></div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!holdings || holdings.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s Movers</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <p className="text-gray-500 mb-2">No holdings data available</p>
            <p className="text-sm text-gray-400">
              Import transactions to start tracking your portfolio
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // If no holdings have today's change data
  if (holdingsWithChange.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s Movers</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <p className="text-gray-500 mb-2">No movers data available yet</p>
            <p className="text-sm text-gray-400">
              Data will appear after we have multiple days of price history
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Today&apos;s Movers</CardTitle>
          {(symbols.length > 0 || isLoadingNews) && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowNews(!showNews)}
              className="flex items-center gap-2"
            >
              {showNews ? (
                <>
                  <ChevronUp className="h-4 w-4" />
                  Hide News
                </>
              ) : (
                <>
                  <ChevronDown className="h-4 w-4" />
                  Show News
                </>
              )}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="text-sm font-semibold text-success mb-3 flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Top Gainers
            </h3>
            <div className="space-y-3">
              {gainers.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-4">No gainers</p>
              ) : (
                gainers.map((holding) => (
                  <div
                    key={holding.ticker}
                    className="flex items-center justify-between"
                  >
                    <div>
                      <p className="font-medium">{holding.ticker}</p>
                      <p className="text-sm text-gray-600">
                        {formatCurrency(holding.current_value, holding.currency)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium text-success">
                        {holding.today_change_percent !== null && holding.today_change_percent !== undefined
                          ? formatPercentage(holding.today_change_percent)
                          : '—'}
                      </p>
                      <p className="text-sm text-gray-600">
                        {formatCurrency(holding.today_change, holding.currency)}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-danger mb-3 flex items-center gap-2">
              <TrendingDown className="h-4 w-4" />
              Top Losers
            </h3>
            <div className="space-y-3">
              {losers.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-4">No losers</p>
              ) : (
                losers.map((holding) => (
                  <div
                    key={holding.ticker}
                    className="flex items-center justify-between"
                  >
                    <div>
                      <p className="font-medium">{holding.ticker}</p>
                      <p className="text-sm text-gray-600">
                        {formatCurrency(holding.current_value, holding.currency)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-medium text-danger">
                        {holding.today_change_percent !== null && holding.today_change_percent !== undefined
                          ? formatPercentage(holding.today_change_percent)
                          : '—'}
                      </p>
                      <p className="text-sm text-gray-600">
                        {formatCurrency(holding.today_change, holding.currency)}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* News Section */}
        {showNews && symbols.length > 0 && (
          <div className="mt-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-500" />
                Market News for Top Movers
              </h3>
              <div className="flex items-center gap-2">
                {isLoadingNews && (
                  <div className="animate-spin h-4 w-4 border-2 border-gray-300 border-t-blue-500 rounded-full"></div>
                )}
                {newsError && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => refetchNews()}
                    className="text-xs"
                  >
                    Retry
                  </Button>
                )}
              </div>
            </div>

            {isLoadingNews ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="animate-pulse">
                    <div className="h-4 bg-gray-200 rounded animate-pulse w-3/4 mb-2"></div>
                    <div className="h-3 bg-gray-200 rounded animate-pulse w-full mb-2"></div>
                    <div className="h-3 bg-gray-200 rounded animate-pulse w-5/6"></div>
                  </div>
                ))}
              </div>
            ) : newsError ? (
              <div className="text-center py-6">
                <p className="text-red-600 mb-2">Failed to load market news</p>
                <p className="text-sm text-gray-500">
                  {newsError instanceof Error ? newsError.message : 'Unable to fetch news articles'}
                </p>
              </div>
            ) : tickerNewsMap.size > 0 ? (
              <div className="space-y-4">
                {Array.from(tickerNewsMap.entries()).slice(0, 4).map(([ticker, articles]) => (
                  <div key={ticker} className="border border-gray-200 rounded-lg p-4 bg-white">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="font-semibold text-gray-900 flex items-center gap-2">
                        <span className="text-sm bg-blue-100 text-blue-800 px-2 py-1 rounded">
                          {ticker}
                        </span>
                        <span className="text-sm text-gray-600">
                          {articles.length} article{articles.length !== 1 ? 's' : ''}
                        </span>
                      </h4>
                    </div>
                    <div className="space-y-2">
                      {articles.map((article, index) => (
                        <div key={index} className="border-l-4 border-blue-200 pl-3 py-2">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <h5 className="text-sm font-medium text-gray-900 mb-1 line-clamp-2">
                                {article.title}
                              </h5>
                              <p className="text-xs text-gray-600 line-clamp-2 mb-1">
                                {article.summary}
                              </p>
                              <div className="flex items-center gap-2 mt-1">
                                <span className="text-xs text-gray-500">
                                  {article.source_name || article.source}
                                </span>
                                <span className="text-xs text-gray-400">•</span>
                                <span className="text-xs text-gray-500">
                                  {article.time || 'Just now'}
                                </span>
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="ml-3"
                              onClick={() => {
                                if (article.url) {
                                  window.open(article.url, '_blank', 'noopener,noreferrer');
                                }
                              }}
                            >
                              <ExternalLink className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6">
                <p className="text-gray-600">No market news available for today&apos;s movers</p>
                <p className="text-sm text-gray-500 mt-1">
                  News will appear when market activity is detected
                </p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}