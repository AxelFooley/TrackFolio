"""
Comprehensive error handling and logging for blockchain services.

Provides centralized error handling, logging, and metrics collection
for blockchain API integrations.
"""
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from app.models.blockchain_data import BlockchainErrorResponse
from app.models.crypto_paper import BlockchainNetwork

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for classification."""
    NETWORK = "network"
    API_ERROR = "api_error"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    PARSING = "parsing"
    CACHE = "cache"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Context information for errors."""
    network: Optional[BlockchainNetwork] = None
    provider: Optional[str] = None
    address: Optional[str] = None
    tx_hash: Optional[str] = None
    endpoint: Optional[str] = None
    request_params: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass
class BlockchainError:
    """Enhanced blockchain error information."""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    original_exception: Optional[Exception] = None
    context: Optional[ErrorContext] = None
    stack_trace: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    is_resolved: bool = False


class BlockchainErrorHandler:
    """Centralized error handler for blockchain services."""

    def __init__(self):
        self.error_log: List[BlockchainError] = []
        self.error_counts: Dict[str, int] = {}
        self.network_error_counts: Dict[BlockchainNetwork, int] = {}
        self.provider_error_counts: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def handle_error(
        self,
        error: Exception,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        message: Optional[str] = None
    ) -> BlockchainError:
        """
        Handle and log blockchain errors.

        Args:
            error: Original exception
            category: Error category
            severity: Error severity
            context: Error context
            message: Custom error message

        Returns:
            BlockchainError object
        """
        try:
            # Generate error ID
            error_id = f"err_{int(datetime.utcnow().timestamp() * 1000)}"

            # Generate message if not provided
            if not message:
                message = f"{category.value}: {str(error)}"

            # Get stack trace
            stack_trace = traceback.format_exc() if isinstance(error, Exception) else None

            # Create error object
            blockchain_error = BlockchainError(
                error_id=error_id,
                category=category,
                severity=severity,
                message=message,
                original_exception=error,
                context=context,
                stack_trace=stack_trace
            )

            # Log error
            await self._log_error(blockchain_error)

            # Update metrics
            await self._update_metrics(blockchain_error)

            # Store error
            async with self._lock:
                self.error_log.append(blockchain_error)
                # Keep only last 1000 errors
                if len(self.error_log) > 1000:
                    self.error_log = self.error_log[-1000:]

            return blockchain_error

        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            # Fallback error object
            return BlockchainError(
                error_id=f"fallback_{int(datetime.utcnow().timestamp() * 1000)}",
                category=ErrorCategory.UNKNOWN,
                severity=ErrorSeverity.CRITICAL,
                message=f"Error handler failed: {str(e)}",
                original_exception=e
            )

    async def _log_error(self, error: BlockchainError):
        """Log error with appropriate level."""
        log_message = f"[{error.error_id}] {error.message}"

        if error.context:
            context_parts = []
            if error.context.network:
                context_parts.append(f"Network: {error.context.network.value}")
            if error.context.provider:
                context_parts.append(f"Provider: {error.context.provider}")
            if error.context.address:
                context_parts.append(f"Address: {error.context.address}")
            if error.context.endpoint:
                context_parts.append(f"Endpoint: {error.context.endpoint}")

            if context_parts:
                log_message += f" | Context: {' | '.join(context_parts)}"

        # Choose log level based on severity
        if error.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif error.severity == ErrorSeverity.HIGH:
            logger.error(log_message)
        elif error.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        # Log stack trace for debugging
        if error.stack_trace and error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            logger.debug(f"Stack trace for {error.error_id}:\n{error.stack_trace}")

    async def _update_metrics(self, error: BlockchainError):
        """Update error metrics."""
        # Update category counts
        category_key = error.category.value
        self.error_counts[category_key] = self.error_counts.get(category_key, 0) + 1

        # Update network counts
        if error.context and error.context.network:
            self.network_error_counts[error.context.network] = \
                self.network_error_counts.get(error.context.network, 0) + 1

        # Update provider counts
        if error.context and error.context.provider:
            provider_key = error.context.provider
            self.provider_error_counts[provider_key] = \
                self.provider_error_counts.get(provider_key, 0) + 1

    def classify_error(self, error: Exception) -> Tuple[ErrorCategory, ErrorSeverity]:
        """
        Classify error type and severity.

        Args:
            error: Exception to classify

        Returns:
            Tuple of (category, severity)
        """
        error_message = str(error).lower()
        error_type = type(error).__name__.lower()

        # Network/timeout errors
        if any(keyword in error_message for keyword in [
            "timeout", "connection", "network", "unreachable", "dns"
        ]) or any(keyword in error_type for keyword in [
            "timeout", "connection", "network"
        ]):
            if "timeout" in error_message:
                return ErrorCategory.TIMEOUT, ErrorSeverity.MEDIUM
            return ErrorCategory.NETWORK, ErrorSeverity.HIGH

        # Rate limiting
        if any(keyword in error_message for keyword in [
            "rate limit", "too many requests", "quota", "429"
        ]):
            return ErrorCategory.RATE_LIMIT, ErrorSeverity.HIGH

        # Authentication errors
        if any(keyword in error_message for keyword in [
            "unauthorized", "authentication", "api key", "401", "403"
        ]):
            return ErrorCategory.AUTHENTICATION, ErrorSeverity.CRITICAL

        # Validation errors
        if any(keyword in error_message for keyword in [
            "invalid", "validation", "malformed", "bad request", "400"
        ]):
            return ErrorCategory.VALIDATION, ErrorSeverity.MEDIUM

        # Parsing errors
        if any(keyword in error_message for keyword in [
            "parse", "json", "format", "decode"
        ]):
            return ErrorCategory.PARSING, ErrorSeverity.MEDIUM

        # API errors
        if any(keyword in error_message for keyword in [
            "api", "server error", "internal error", "500"
        ]):
            return ErrorCategory.API_ERROR, ErrorSeverity.HIGH

        # Cache errors
        if any(keyword in error_message for keyword in [
            "cache", "redis", "storage"
        ]):
            return ErrorCategory.CACHE, ErrorSeverity.LOW

        # Default classification
        return ErrorCategory.UNKNOWN, ErrorSeverity.MEDIUM

    async def get_error_summary(
        self,
        hours: int = 24,
        network: Optional[BlockchainNetwork] = None,
        severity: Optional[ErrorSeverity] = None
    ) -> Dict[str, Any]:
        """
        Get error summary for the specified time period.

        Args:
            hours: Number of hours to look back
            network: Filter by network
            severity: Filter by severity

        Returns:
            Error summary statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        # Filter errors
        filtered_errors = []
        for error in self.error_log:
            if error.timestamp < cutoff_time:
                continue

            if network and error.context and error.context.network != network:
                continue

            if severity and error.severity != severity:
                continue

            filtered_errors.append(error)

        # Calculate statistics
        total_errors = len(filtered_errors)
        error_by_category = {}
        error_by_severity = {}
        error_by_network = {}
        error_by_provider = {}

        for error in filtered_errors:
            # By category
            category = error.category.value
            error_by_category[category] = error_by_category.get(category, 0) + 1

            # By severity
            severity_key = error.severity.value
            error_by_severity[severity_key] = error_by_severity.get(severity_key, 0) + 1

            # By network
            if error.context and error.context.network:
                net_key = error.context.network.value
                error_by_network[net_key] = error_by_network.get(net_key, 0) + 1

            # By provider
            if error.context and error.context.provider:
                provider_key = error.context.provider
                error_by_provider[provider_key] = error_by_provider.get(provider_key, 0) + 1

        # Get recent errors
        recent_errors = filtered_errors[-10:]

        return {
            "total_errors": total_errors,
            "timeframe_hours": hours,
            "errors_by_category": error_by_category,
            "errors_by_severity": error_by_severity,
            "errors_by_network": error_by_network,
            "errors_by_provider": error_by_provider,
            "recent_errors": [
                {
                    "error_id": e.error_id,
                    "category": e.category.value,
                    "severity": e.severity.value,
                    "message": e.message,
                    "timestamp": e.timestamp.isoformat(),
                    "network": e.context.network.value if e.context and e.context.network else None,
                    "provider": e.context.provider if e.context else None
                }
                for e in recent_errors
            ]
        }

    async def clear_old_errors(self, hours: int = 168):  # 1 week
        """Clear old errors from memory."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        async with self._lock:
            original_count = len(self.error_log)
            self.error_log = [e for e in self.error_log if e.timestamp > cutoff_time]
            cleared_count = original_count - len(self.error_log)

        if cleared_count > 0:
            logger.info(f"Cleared {cleared_count} old errors from memory")

    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get overall health status based on recent errors.

        Returns:
            Health status information
        """
        # Get recent errors (last hour)
        recent_summary = await self.get_error_summary(hours=1)

        # Determine health status
        critical_errors = recent_summary["errors_by_severity"].get("critical", 0)
        high_errors = recent_summary["errors_by_severity"].get("high", 0)
        total_errors = recent_summary["total_errors"]

        if critical_errors > 0:
            health_status = "critical"
            health_message = f"Critical errors detected: {critical_errors}"
        elif high_errors > 5:
            health_status = "degraded"
            health_message = f"High number of errors: {high_errors}"
        elif total_errors > 20:
            health_status = "warning"
            health_message = f"Elevated error rate: {total_errors} errors/hour"
        else:
            health_status = "healthy"
            health_message = "Normal operation"

        return {
            "status": health_status,
            "message": health_message,
            "recent_errors_1h": recent_summary["total_errors"],
            "critical_errors_1h": critical_errors,
            "high_errors_1h": high_errors,
            "total_errors_stored": len(self.error_log),
            "last_updated": datetime.utcnow().isoformat()
        }


# Global error handler instance
blockchain_error_handler = BlockchainErrorHandler()


async def handle_blockchain_error(
    error: Exception,
    network: Optional[BlockchainNetwork] = None,
    provider: Optional[str] = None,
    address: Optional[str] = None,
    tx_hash: Optional[str] = None,
    endpoint: Optional[str] = None,
    request_params: Optional[Dict[str, Any]] = None
) -> BlockchainError:
    """
    Convenience function to handle blockchain errors.

    Args:
        error: Original exception
        network: Blockchain network
        provider: API provider
        address: Related address
        tx_hash: Related transaction hash
        endpoint: API endpoint
        request_params: Request parameters

    Returns:
        BlockchainError object
    """
    # Classify error
    category, severity = blockchain_error_handler.classify_error(error)

    # Create context
    context = ErrorContext(
        network=network,
        provider=provider,
        address=address,
        tx_hash=tx_hash,
        endpoint=endpoint,
        request_params=request_params
    )

    # Handle error
    return await blockchain_error_handler.handle_error(
        error=error,
        category=category,
        severity=severity,
        context=context
    )


def retry_on_error(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retry_on: Optional[List[Type[Exception]]] = None
):
    """
    Decorator for retrying blockchain operations on certain errors.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry
        retry_on: List of exception types to retry on
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_error = e

                    # Check if we should retry on this error
                    if retry_on and not any(isinstance(e, exc_type) for exc_type in retry_on):
                        break

                    # Don't retry on certain error types
                    category, _ = blockchain_error_handler.classify_error(e)
                    if category in [ErrorCategory.VALIDATION, ErrorCategory.AUTHENTICATION]:
                        break

                    if attempt < max_retries:
                        delay = base_delay * (backoff_factor ** attempt)
                        logger.warning(f"Retrying {func.__name__} in {delay}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)

            # All retries failed
            raise last_error

        return wrapper
    return decorator