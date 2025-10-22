"""
News models - News articles and sentiment analysis data.
"""
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Date, JSON, Index, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Dict, Any, Optional, List
import enum

from app.database import Base


class SentimentType(str, enum.Enum):
    """Sentiment type enumeration."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class NewsSource(str, enum.Enum):
    """News source enumeration."""
    ALPHA_VANTAGE = "alpha_vantage"
    YAHOO_FINANCE = "yahoo_finance"
    REUTERS = "reuters"
    BLOOMBERG = "bloomberg"
    CNBC = "cnbc"
    MARKET_WATCH = "market_watch"
    OTHER = "other"


class NewsArticle(Base):
    """
    NewsArticle model for storing individual news articles.

    Based on Alpha Vantage NEWS_SENTIMENT API response structure.
    Supports various news sources with comprehensive metadata.
    """
    __tablename__ = "news_articles"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Article identification and metadata
    article_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Unique identifier for the article from source"
    )
    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Article title"
    )
    url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="Article URL"
    )
    source: Mapped[NewsSource] = mapped_column(
        String(20),
        nullable=False,
        default=NewsSource.ALPHA_VANTAGE,
        comment="News source"
    )
    source_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Source name/organization"
    )

    # Content and summary
    summary: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
        comment="Article summary or snippet"
    )
    content: Mapped[str | None] = mapped_column(
        String(20000),
        nullable=True,
        comment="Full article content if available"
    )
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
        comment="Article language code"
    )

    # Publication information
    published_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="Article publication timestamp"
    )
    published_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Article publication date"
    )

    # Multimedia
    banner_image_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="Banner image URL"
    )
    thumbnail_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="Thumbnail image URL"
    )

    # Raw topics data (flexible JSON storage)
    topics_json: Mapped[Dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Raw topics data from source"
    )

    # Processing metadata
    relevance_score: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=8),
        nullable=True,
        comment="Article relevance score for portfolio (0.0-1.0)"
    )
    sentiment_score: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=8),
        nullable=True,
        comment="Overall sentiment score (-1.0 to 1.0)"
    )
    sentiment_label: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Overall sentiment label"
    )

    # Article status
    is_processed: Mapped[bool] = mapped_column(
        String(5),
        nullable=False,
        default="false",
        comment="Whether article has been processed for sentiment"
    )
    is_duplicate: Mapped[bool] = mapped_column(
        String(5),
        nullable=False,
        default="false",
        comment="Whether article is a duplicate"
    )

    # Source-specific data
    source_data: Mapped[Dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Source-specific additional data"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    sentiments: Mapped[List["NewsTickerSentiment"]] = relationship(
        "NewsTickerSentiment",
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    # Composite indexes for common queries
    __table_args__ = (
        # Unique constraint to prevent duplicate articles by source and article_id
        UniqueConstraint('source', 'article_id', name='uix_news_source_article_id'),

        # Performance indexes
        Index('ix_news_published_at', 'published_at'),
        Index('ix_news_published_date', 'published_date'),
        Index('ix_news_source', 'source'),
        Index('ix_news_sentiment_label', 'sentiment_label'),
        Index('ix_news_relevance_score', 'relevance_score'),
        Index('ix_news_ticker_sentiment', 'published_date', 'sentiment_label'),
    )

    # Constraints
    __table_args__ = (
        CheckConstraint('relevance_score >= 0 AND relevance_score <= 1', name='ck_relevance_score_range'),
        CheckConstraint('sentiment_score >= -1 AND sentiment_score <= 1', name='ck_sentiment_score_range'),
    )

    def __repr__(self) -> str:
        title_preview = self.title[:50] + "..." if self.title else None
        return (
            f"NewsArticle(id={self.id!r}, "
            f"title={title_preview!r}, "
            f"source={self.source.value!r}, "
            f"published_at={self.published_at!r})"
        )

    @property
    def topics(self) -> List[Dict[str, Any]]:
        """Get topics as a list of dictionaries."""
        return self.topics_json or []

    @topics.setter
    def topics(self, value: List[Dict[str, Any]]) -> None:
        """Set topics from a list of dictionaries."""
        self.topics_json = value

    @property
    def has_sentiment(self) -> bool:
        """Check if article has sentiment analysis."""
        return self.sentiment_score is not None and self.sentiment_label is not None

    @property
    def is_high_relevance(self) -> bool:
        """Check if article is high relevance (score >= 0.7)."""
        return self.relevance_score is not None and self.relevance_score >= Decimal('0.7')

    @property
    def publication_date_str(self) -> str:
        """Get publication date as string in YYYY-MM-DD format."""
        return self.published_date.isoformat()


class NewsTickerSentiment(Base):
    """
    NewsTickerSentiment model for ticker-level sentiment analysis.

    Links news articles to specific tickers with sentiment analysis.
    Supports weighted sentiment calculations for portfolio analysis.
    """
    __tablename__ = "news_ticker_sentiments"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign key relationship
    article_id: Mapped[int] = mapped_column(
        ForeignKey("news_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Ticker and asset identification
    ticker: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Ticker symbol"
    )
    isin: Mapped[str | None] = mapped_column(
        String(12),
        nullable=True,
        index=True,
        comment="ISIN if available"
    )
    asset_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="STOCK",
        comment="STOCK, ETF, CRYPTO, etc."
    )

    # Sentiment analysis
    sentiment_type: Mapped[SentimentType] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="Sentiment classification"
    )
    sentiment_score: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=8),
        nullable=True,
        comment="Sentiment score for this ticker (-1.0 to 1.0)"
    )
    relevance_score: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=8),
        nullable=True,
        comment="Relevance score for this ticker (0.0-1.0)"
    )

    # Topic and keyword analysis
    topics_json: Mapped[Dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Topic data for this ticker"
    )
    keywords: Mapped[Dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Keyword analysis for this ticker"
    )

    # Confidence and reliability metrics
    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=8),
        nullable=True,
        comment="Confidence in sentiment analysis (0.0-1.0)"
    )
    relevance_factor: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=8),
        nullable=True,
        comment="How relevant this ticker is to the article"
    )

    # Processing metadata
    processed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When sentiment was processed"
    )
    processing_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="1.0",
        comment="Sentiment processing version"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    article: Mapped["NewsArticle"] = relationship(
        "NewsArticle",
        back_populates="sentiments"
    )

    # Composite indexes for common queries
    __table_args__ = (
        # Unique constraint to prevent duplicate sentiment entries per article-ticker
        UniqueConstraint('article_id', 'ticker', name='uix_news_ticker_sentiment'),

        # Performance indexes
        Index('ix_news_ticker_sentiment_ticker_date', 'ticker', 'processed_at'),
        Index('ix_news_ticker_sentiment_type_date', 'sentiment_type', 'processed_at'),
        Index('ix_news_ticker_sentiment_relevance', 'relevance_score'),
        Index('ix_news_ticker_sentiment_confidence', 'confidence_score'),
    )

    # Constraints
    __table_args__ = (
        CheckConstraint('sentiment_score >= -1 AND sentiment_score <= 1', name='ck_ticker_sentiment_score_range'),
        CheckConstraint('relevance_score >= 0 AND relevance_score <= 1', name='ck_ticker_relevance_score_range'),
        CheckConstraint('confidence_score >= 0 AND confidence_score <= 1', name='ck_ticker_confidence_score_range'),
        CheckConstraint('relevance_factor >= 0 AND relevance_factor <= 1', name='ck_ticker_relevance_factor_range'),
    )

    def __repr__(self) -> str:
        return (
            f"NewsTickerSentiment(id={self.id!r}, "
            f"ticker={self.ticker!r}, "
            f"sentiment_type={self.sentiment_type.value!r}, "
            f"score={self.sentiment_score!r}, "
            f"processed_at={self.processed_at!r})"
        )

    @property
    def topics(self) -> Dict[str, Any]:
        """Get topics as a dictionary."""
        return self.topics_json or {}

    @topics.setter
    def topics(self, value: Dict[str, Any]) -> None:
        """Set topics from a dictionary."""
        self.topics_json = value

    @property
    def keywords_dict(self) -> Dict[str, Any]:
        """Get keywords as a dictionary."""
        return self.keywords or {}

    @keywords_dict.setter
    def keywords_dict(self, value: Dict[str, Any]) -> None:
        """Set keywords from a dictionary."""
        self.keywords = value

    @property
    def is_positive(self) -> bool:
        """Check if sentiment is positive."""
        return self.sentiment_type == SentimentType.POSITIVE

    @property
    def is_negative(self) -> bool:
        """Check if sentiment is negative."""
        return self.sentiment_type == SentimentType.NEGATIVE

    @property
    def is_high_confidence(self) -> bool:
        """Check if sentiment analysis has high confidence."""
        return self.confidence_score is not None and self.confidence_score >= Decimal('0.8')

    @property
    def is_high_relevance(self) -> bool:
        """Check if ticker is highly relevant to article."""
        return self.relevance_score is not None and self.relevance_score >= Decimal('0.7')