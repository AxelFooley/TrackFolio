'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ExternalLink, Clock, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useNews } from '@/hooks/useNews';
import type { NewsArticle, NewsFilters } from '@/lib/types';
import {
  getSentimentInfo,
  formatRelevanceScore,
  getRelevanceColor,
  formatRelativeDate,
  truncateText
} from '@/lib/utils';

interface NewsCardsProps {
  filters?: NewsFilters;
  limit?: number;
  showTitle?: boolean;
  className?: string;
}

/**
 * A responsive news cards component that displays news articles with sentiment analysis.
 *
 * Features:
 * - Mobile-first responsive design
 * - Loading skeletons and error states
 * - Sentiment indicators with color coding (green=positive, red=negative, neutral=gray)
 * - Article cards with title, source, timestamp, summary, and relevance score
 * - Click-through functionality to full articles
 * - Accessibility features with proper ARIA labels
 * - Hover effects and smooth transitions
 */
export function NewsCards({
  filters = {},
  limit = 10,
  showTitle = true,
  className = ''
}: NewsCardsProps) {
  const router = useRouter();
  const [expandedArticles, setExpandedArticles] = useState<Set<string>>(new Set());

  // Enhanced filters with default values
  const enhancedFilters: NewsFilters = {
    ...filters,
    limit,
  };

  const {
    data: newsData,
    isLoading,
    error,
    refetch
  } = useNews(enhancedFilters);

  const handleArticleClick = (article: NewsArticle, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // Open in new tab if URL exists
    if (article.url) {
      window.open(article.url, '_blank', 'noopener,noreferrer');
    }

    // Track analytics if needed
    console.log('Article clicked:', article.title || 'Untitled Article');
  };

  const toggleExpand = (articleId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    const newExpanded = new Set(expandedArticles);
    if (newExpanded.has(articleId)) {
      newExpanded.delete(articleId);
    } else {
      newExpanded.add(articleId);
    }
    setExpandedArticles(newExpanded);
  };

  const renderSentimentIcon = (sentiment: 'positive' | 'negative' | 'neutral') => {
    const sentimentInfo = getSentimentInfo(sentiment);

    switch (sentiment) {
      case 'positive':
        return <TrendingUp className="h-4 w-4" />;
      case 'negative':
        return <TrendingDown className="h-4 w-4" />;
      case 'neutral':
        return <Minus className="h-4 w-4" />;
    }
  };

  const renderSentimentBadge = (sentiment: 'positive' | 'negative' | 'neutral', score: number) => {
    const sentimentInfo = getSentimentInfo(sentiment);

    return (
      <Badge
        variant="outline"
        className={`${sentimentInfo.borderColor} border-current text-xs gap-1`}
        title={`Sentiment: ${sentimentInfo.label} (Score: ${score.toFixed(2)})`}
      >
        {renderSentimentIcon(sentiment)}
        <span>{sentimentInfo.label}</span>
      </Badge>
    );
  };

  const renderRelevanceBadge = (score: number) => {
    const relevanceText = formatRelevanceScore(score);
    const relevanceColor = getRelevanceColor(score);

    return (
      <Badge
        variant="outline"
        className={`text-xs border-current ${relevanceColor}`}
        title={`Relevance: ${relevanceText} (${score.toFixed(2)})`}
      >
        {relevanceText}
      </Badge>
    );
  };

  // Loading state
  if (isLoading) {
    return (
      <div className={`space-y-4 ${className}`}>
        {showTitle && (
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Latest News</h2>
            <p className="text-sm text-gray-600 mt-1">Loading financial news...</p>
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(limit)].map((_, index) => (
            <Card key={index} className="overflow-hidden">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div className="h-4 bg-gray-200 rounded animate-pulse w-24"></div>
                  <div className="h-6 w-16 bg-gray-200 rounded-full animate-pulse"></div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="h-4 bg-gray-200 rounded animate-pulse w-3/4"></div>
                <div className="space-y-2">
                  <div className="h-3 bg-gray-200 rounded animate-pulse"></div>
                  <div className="h-3 bg-gray-200 rounded animate-pulse w-5/6"></div>
                  <div className="h-3 bg-gray-200 rounded animate-pulse w-4/6"></div>
                </div>
                <div className="flex items-center justify-between">
                  <div className="h-6 w-20 bg-gray-200 rounded-full animate-pulse"></div>
                  <div className="h-6 w-16 bg-gray-200 rounded-full animate-pulse"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`text-center py-8 ${className}`}>
        <h3 className="text-lg font-semibold text-red-600 mb-2">Failed to Load News</h3>
        <p className="text-gray-600 mb-4">
          {error instanceof Error ? error.message : 'Unable to fetch news articles'}
        </p>
        <Button
          onClick={() => refetch()}
          variant="outline"
          className="px-4 py-2"
        >
          Try Again
        </Button>
      </div>
    );
  }

  // No data state
  if (!newsData || newsData.articles.length === 0) {
    return (
      <div className={`text-center py-8 ${className}`}>
        <h3 className="text-lg font-semibold text-gray-600 mb-2">No News Available</h3>
        <p className="text-gray-500">
          {filters.query ? 'No news found for your search.' : 'No financial news available at the moment.'}
        </p>
      </div>
    );
  }

  const articles = newsData?.articles?.slice(0, limit) || [];

  return (
    <div className={`space-y-4 ${className}`}>
      {showTitle && (
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-gray-900">Latest News</h2>
          <p className="text-sm text-gray-600 mt-1">
            {newsData?.total || 0} articles found
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {articles.map((article, index) => {
          if (!article || !article.id) {
            return (
              <Card key={`missing-article-${index}`} className="overflow-hidden">
                <CardContent className="p-4 text-center text-gray-500">
                  Invalid article data
                </CardContent>
              </Card>
            );
          }

          const isExpanded = expandedArticles.has(article.id);
          const summary = article.summary ? (isExpanded ? article.summary : truncateText(article.summary, 120)) : '';

          return (
            <Card
              key={article.id}
              className="group cursor-pointer transition-all duration-200 hover:shadow-lg hover:-translate-y-1"
              onClick={(e) => handleArticleClick(article, e)}
              role="article"
              aria-labelledby={`article-title-${article.id}`}
              aria-describedby={`article-summary-${article.id}`}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleArticleClick(article, e as any);
                }
              }}
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <CardTitle
                      id={`article-title-${article.id}`}
                      className="text-lg font-medium text-gray-900 leading-tight line-clamp-2"
                    >
                      {article.title ? truncateText(article.title, 60) : 'Untitled Article'}
                    </CardTitle>
                  </div>
                  <ExternalLink className="h-4 w-4 text-gray-400 flex-shrink-0 mt-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>

                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <Clock className="h-3 w-3" />
                    <span>{article.publish_date ? formatRelativeDate(article.publish_date) : 'Unknown date'}</span>
                  </div>
                  {article.sentiment && article.sentiment_score ? renderSentimentBadge(article.sentiment, article.sentiment_score) : null}
                </div>
              </CardHeader>

              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <p
                    id={`article-summary-${article.id}`}
                    className="text-sm text-gray-600 leading-relaxed line-clamp-3"
                    style={{ maxHeight: isExpanded ? 'none' : '4.5rem' }}
                  >
                    {summary}
                  </p>
                  {!isExpanded && article.summary.length > 120 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs text-blue-600 hover:text-blue-800 p-0 h-auto"
                      onClick={(e) => toggleExpand(article.id, e)}
                    >
                      Read more
                    </Button>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <div className="text-xs text-gray-500">
                    <span className="font-medium">Source:</span> {article.source || 'Unknown'}
                  </div>
                  {article.relevance_score ? renderRelevanceBadge(article.relevance_score) : null}
                </div>

                {(article.tickers || []).length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {(article.tickers || []).slice(0, 3).map((ticker, index) => (
                      <Badge
                        key={ticker || index}
                        variant="outline"
                        className="text-xs border-blue-200 text-blue-600"
                      >
                        {ticker || ''}
                      </Badge>
                    ))}
                    {(article.tickers || []).length > 3 && (
                      <Badge variant="outline" className="text-xs text-gray-500">
                        +{(article.tickers || []).length - 3}
                      </Badge>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {articles.length < newsData.total && (
        <div className="text-center">
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push('/news')}
          >
            View All {newsData.total} Articles
          </Button>
        </div>
      )}
    </div>
  );
}