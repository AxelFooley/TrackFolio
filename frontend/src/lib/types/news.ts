export interface NewsArticleDetail {
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

export interface NewsFetchResult {
  ticker: string;
  articles: NewsArticleDetail[];
  success: boolean;
  error_message?: string;
  api_calls_made: number;
  cached_articles: number;
  processed_articles: number;
  filter_applied: boolean;
}

export interface MoversNewsResponse {
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

export interface NewsSentimentSummary {
  positive_sentiment: number;
  negative_sentiment: number;
  neutral_sentiment: number;
  overall_sentiment: 'positive' | 'negative' | 'neutral';
  confidence_score: number;
}

export interface NewsSourceSummary {
  source_name: string;
  article_count: number;
  average_reliability: number;
  most_recent_article?: string;
}

export interface NewsSummary {
  ticker: string;
  total_articles: number;
  total_api_calls: number;
  filtered_articles: number;
  average_relevance: number;
  sentiment_summary: NewsSentimentSummary;
  top_sources: NewsSourceSummary[];
  recent_articles: NewsArticleDetail[];
  summary_generated_at: string;
  quality_tier: string;
}

export interface NewsHealthMetrics {
  service_name: string;
  status: string;
  timestamp: string;
  rate_limiter: {
    daily_calls: number;
    daily_limit: number;
    hourly_calls: number;
    hourly_limit: number;
    wait_time_seconds: number;
  };
  cache_service: {
    cache_hit_rate: number;
    cache_size: number;
    cache_hits: number;
    cache_misses: number;
  };
  configuration: {
    max_concurrent_requests: number;
    max_batch_size: number;
    retry_count: number;
    timeout_seconds: number;
  };
  quality_thresholds: {
    high: number;
    medium: number;
    low: number;
  };
}

export type NewsQualityLevel = 'high' | 'medium' | 'low' | 'recent' | 'popular';

export interface UseAlphaVantageNewsOptions {
  quality?: NewsQualityLevel;
  limit?: number;
  staleTime?: number;
  enabled?: boolean;
  retry?: number;
}

export interface UseMoversNewsOptions {
  limit?: number;
  minChangePercent?: number;
  quality?: NewsQualityLevel;
  staleTime?: number;
  enabled?: boolean;
  retry?: number;
}

export interface UseTickerSentimentOptions {
  days?: number;
  confidenceThreshold?: number;
  staleTime?: number;
  enabled?: boolean;
  retry?: number;
}