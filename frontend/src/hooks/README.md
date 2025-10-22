# News Data Hooks

This directory contains custom React hooks for fetching and managing news data from the Alpha Vantage news API. The hooks follow the existing patterns in the TrackFolio codebase and integrate seamlessly with the existing data fetching architecture.

## Overview

### Core Hooks

1. **`useAlphaVantageNews.ts`** - Primary news hook for Alpha Vantage API integration
2. **`usePortfolioNewsIntegration.ts`** - Enhanced hook that integrates news with portfolio data
3. **`NewsIntegrationExample.tsx`** - Example component demonstrating usage

## Hook Reference

### useAlphaVantageNews

The main hook for fetching news data from the Alpha Vantage API with React Query integration.

#### Available Functions

```typescript
// Get news for top movers in the portfolio
useMoversNews(options: {
  limit?: number;
  minChangePercent?: number;
  quality?: NewsQualityLevel;
  staleTime?: number;
  enabled?: boolean;
  retry?: number;
})

// Get news for a specific ticker
useTickerNews(ticker: string, options: {
  limit?: number;
  quality?: NewsQualityLevel;
  staleTime?: number;
  enabled?: boolean;
  retry?: number;
})

// Get sentiment analysis for a specific ticker
useTickerSentiment(ticker: string, options: {
  days?: number;
  confidenceThreshold?: number;
  staleTime?: number;
  enabled?: boolean;
  retry?: number;
})

// Get news fetcher health status
useNewsHealthStatus(options: {
  staleTime?: number;
  enabled?: boolean;
  retry?: number;
})

// Get available quality levels
useNewsQualityLevels(options: {
  staleTime?: number;
  enabled?: boolean;
  retry?: number;
})

// Get supported news sources
useSupportedNewsSources(options: {
  staleTime?: number;
  enabled?: boolean;
  retry?: number;
})

// Mutation hooks for news operations
useRefreshNews() - Refresh news data
useClearNewsCache() - Clear news cache
```

#### Usage Example

```typescript
import { useMoversNews, useTickerNews } from '@/hooks/useAlphaVantageNews';

function NewsComponent() {
  // Get news for top movers
  const moversNews = useMoversNews({
    limit: 10,
    minChangePercent: 2.0,
    quality: 'high',
    staleTime: 300000, // 5 minutes
  });

  // Get news for a specific ticker
  const tickerNews = useTickerNews('AAPL', {
    limit: 50,
    quality: 'high',
    staleTime: 600000, // 10 minutes
  });

  if (moversNews.isLoading) return <div>Loading...</div>;
  if (moversNews.error) return <div>Error: {moversNews.error.message}</div>;

  return (
    <div>
      {moversNews.data?.movers.map(mover => (
        <div key={mover.ticker}>
          <h3>{mover.ticker}</h3>
          <p>{mover.articles.length} articles</p>
        </div>
      ))}
    </div>
  );
}
```

### usePortfolioNewsIntegration

Enhanced hook that automatically integrates news data with portfolio holdings, providing contextual news coverage based on user's portfolio.

#### Available Functions

```typescript
// Main portfolio news integration
usePortfolioNewsIntegration(options: {
  limit?: number;
  minChangePercent?: number;
  quality?: NewsQualityLevel;
  autoRefreshHoldings?: boolean;
  enabled?: boolean;
  retry?: number;
})

// Focus on best performers
useBestPerformersNews(options: {
  limit?: number;
  quality?: NewsQualityLevel;
})

// Focus on underperformers
useUnderperformersNews(options: {
  limit?: number;
  quality?: NewsQualityLevel;
})

// Holdings without news coverage
useHoldingsWithoutNews(options: {
  limit?: number;
  quality?: NewsQualityLevel;
})
```

#### Usage Example

```typescript
import { usePortfolioNewsIntegration } from '@/hooks/usePortfolioNewsIntegration';

function PortfolioNewsDashboard() {
  const portfolioNews = usePortfolioNewsIntegration({
    limit: 5,
    minChangePercent: 2.0,
    quality: 'high',
    autoRefreshHoldings: true,
  });

  if (portfolioNews.isLoading) return <div>Loading portfolio news...</div>;
  if (portfolioNews.newsError) return <div>Error loading news</div>;

  return (
    <div>
      <h2>Portfolio News Summary</h2>
      <p>Total Holdings: {portfolioNews.holdings.length}</p>
      <p>Holdings with News: {portfolioNews.holdingsWithNews.length}</p>
      <p>Best Performers: {portfolioNews.bestPerformingHoldings.length}</p>

      {/* Best performers with news */}
      <div>
        <h3>Best Performers</h3>
        {portfolioNews.bestPerformingHoldings.map(holding => (
          <NewsCard key={holding.ticker} holding={holding} />
        ))}
      </div>

      {/* Holdings without news */}
      <div>
        <h3>Holdings Without News Coverage</h3>
        {portfolioNews.holdingsWithoutNews.map(holding => (
          <HoldingCard key={holding.ticker} holding={holding} />
        ))}
      </div>
    </div>
  );
}
```

## Data Types

### NewsArticleDetail
```typescript
interface NewsArticleDetail {
  title?: string;
  url?: string;
  source?: string;
  source_name?: string;
  time?: string;
  summary?: string;
  banner_image?: string;
  topics: Array<{
    topic?: string;
    relevance_score?: number;
    title_sentiment?: string;
  }>;
  overall_sentiment_score?: number;
  overall_sentiment_label?: string;
  enriched_at: string;
  quality_score: number;
  relevance_score: number;
  word_count: number;
  has_image: boolean;
  topic_count: number;
  source_reliability: number;
}
```

### NewsQualityLevel
```typescript
type NewsQualityLevel = 'high' | 'medium' | 'low' | 'recent' | 'popular';
```

- **high**: High relevance (>0.7) and excludes neutral sentiment
- **medium**: Medium relevance (>0.5) and includes neutral sentiment
- **low**: All relevance levels, no filtering
- **recent**: Very recent news with time-based filtering
- **popular**: News with multiple topics coverage

### MoversNewsResponse
```typescript
interface MoversNewsResponse {
  movers: NewsFetchResult[];
  total_movers: number;
  successful_movers: number;
  total_api_calls: number;
  total_articles: number;
  cache_hit_rate: number;
  movers_criteria: {
    min_change_percent: number;
    quality_level: string;
    limit: number;
  };
}
```

## Integration with Existing Components

### Dashboard Integration
The news hooks can be integrated into the existing Dashboard component:

```typescript
// In Dashboard/page.tsx
import { usePortfolioNewsIntegration } from '@/hooks/usePortfolioNewsIntegration';

export default function Dashboard() {
  const portfolioNews = usePortfolioNewsIntegration({
    limit: 5,
    quality: 'high',
  });

  // Add to existing dashboard components
  return (
    <div>
      {/* Existing dashboard components */}
      <PortfolioOverview data={portfolioOverview} />
      <HoldingsTable holdings={holdings} />

      {/* Add news components */}
      <NewsSection news={portfolioNews} />
      <SentimentAnalysisSection sentiment={portfolioNews.sentimentData} />
    </div>
  );
}
```

### Asset Detail Integration
The hooks can be used in asset detail pages:

```typescript
// In asset/[ticker]/page.tsx
import { useTickerNews, useTickerSentiment } from '@/hooks/useAlphaVantageNews';

export default function AssetDetailPage({ params }) {
  const tickerNews = useTickerNews(params.ticker, { limit: 20 });
  const tickerSentiment = useTickerSentiment(params.ticker);

  return (
    <div>
      <AssetHeader asset={asset} />
      <PriceChart prices={prices} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <NewsSection news={tickerNews} />
        <SentimentSection sentiment={tickerSentiment} />
      </div>
    </div>
  );
}
```

## Cache Management

The hooks implement intelligent caching strategies:

- **Movers News**: 5 minutes cache (frequent updates)
- **Ticker News**: 10 minutes cache
- **Sentiment Analysis**: 30 minutes cache (expensive computation)
- **Quality Levels**: 24 hours cache (static configuration)
- **Health Status**: 10 minutes cache

### Cache Invalidation

The hooks automatically invalidate caches when:

1. **Portfolio changes**: Holdings are refreshed and news is refetched
2. **Manual refresh**: User triggers refresh via UI
3. **Cache clear**: User clears cache via UI
4. **Error conditions**: Failed API calls trigger refetch

### Cache Keys

Cache keys are structured hierarchically:

```typescript
NEWS_QUERY_KEYS = {
  all: ['alpha-vantage-news'] as const,
  movers: () => [...NEWS_QUERY_KEYS.all, 'movers'] as const,
  ticker: (ticker: string) => [...NEWS_QUERY_KEYS.all, 'ticker', ticker] as const,
  sentiment: (ticker: string) => [...NEWS_QUERY_KEYS.all, 'sentiment', ticker] as const,
  // ... other keys
};
```

## Error Handling

The hooks provide comprehensive error handling:

```typescript
// Loading states
if (newsQuery.isLoading) return <LoadingSpinner />;
if (newsQuery.isError) return <ErrorDisplay error={newsQuery.error} />;

// Retry logic
retry: 2, // Retry failed requests up to 2 times

// Error boundaries
// Implement ErrorBoundary components for better error handling
```

## Performance Optimization

1. **Debouncing**: Rapid successive requests are debounced
2. **Parallel fetching**: Batch requests for multiple tickers
3. **Selective refetching**: Only refetch when data is actually stale
4. **Memory efficient**: Clean up unused data
5. **Background fetching**: Data fetches in background tabs

## Testing

The hooks include TypeScript types and are designed to be easily testable:

```typescript
// Test file example
import { renderHook, waitFor } from '@testing-library/react';
import { useMoversNews } from '@/hooks/useAlphaVantageNews';

describe('useMoversNews', () => {
  it('should fetch movers news successfully', async () => {
    const { result } = renderHook(() => useMoversNews());

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
```

## API Endpoints

The hooks integrate with the following API endpoints:

- `GET /api/news/movers` - Portfolio movers news
- `GET /api/news/{ticker}` - Specific ticker news
- `GET /api/news/sentiment/{ticker}` - Sentiment analysis
- `GET /api/news/health` - Health status
- `POST /api/news/refresh` - Refresh news
- `DELETE /api/news/cache` - Clear cache
- `GET /api/news/quality-levels` - Quality levels
- `GET /api/news/supported-sources` - Supported sources

## Configuration

Default configurations can be customized:

```typescript
// Override default values in hook calls
useMoversNews({
  limit: 20, // Default: 10
  minChangePercent: 5.0, // Default: 2.0
  quality: 'medium', // Default: 'high'
  staleTime: 600000, // Default: 300000 (5 minutes)
});
```

## Contributing

When adding new hooks:

1. Follow the existing TypeScript patterns
2. Include comprehensive error handling
3. Implement appropriate caching strategies
4. Add JSDoc documentation
5. Include usage examples
6. Ensure integration with existing portfolio data