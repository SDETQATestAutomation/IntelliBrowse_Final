"""
Notification Module - Retry Manager

Handles automatic retry logic, fallback channels, and exponential backoff.
Integrates with delivery history tracking and circuit breaker patterns.
"""

import asyncio
import random
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum

from ..models import (
    NotificationModel, NotificationChannel, DeliveryStatus,
    NotificationDeliveryHistory
)
from .channel_adapter_base import (
    NotificationChannelAdapter, NotificationPayload, NotificationResult,
    NotificationResultStatus
)
from ...config.logging import get_logger

logger = get_logger(__name__)


class RetryPolicy(str, Enum):
    """Retry policy types."""
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"


class FailureType(str, Enum):
    """Types of delivery failures."""
    TRANSIENT = "transient"  # Network issues, timeouts
    PERMANENT = "permanent"  # Invalid recipient, authentication
    RATE_LIMITED = "rate_limited"  # Rate limit exceeded
    CONFIGURATION = "configuration"  # Missing config, invalid setup


class RetryConfiguration:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retry_attempts: int = 3,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 300.0,  # 5 minutes
        retry_policy: RetryPolicy = RetryPolicy.EXPONENTIAL,
        jitter_factor: float = 0.1,
        retry_multiplier: float = 2.0,
        enable_fallback: bool = True,
        fallback_channels: Optional[List[NotificationChannel]] = None,
        permanent_failure_codes: Optional[List[str]] = None,
        transient_failure_codes: Optional[List[str]] = None
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_retry_attempts: Maximum number of retry attempts per channel
            base_delay_seconds: Base delay for retry calculations
            max_delay_seconds: Maximum delay between retries
            retry_policy: Type of retry policy to use
            jitter_factor: Random jitter factor (0.0 to 1.0)
            retry_multiplier: Multiplier for exponential backoff
            enable_fallback: Whether to enable fallback to other channels
            fallback_channels: Ordered list of fallback channels
            permanent_failure_codes: Error codes considered permanent failures
            transient_failure_codes: Error codes considered transient failures
        """
        self.max_retry_attempts = max_retry_attempts
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.retry_policy = retry_policy
        self.jitter_factor = jitter_factor
        self.retry_multiplier = retry_multiplier
        self.enable_fallback = enable_fallback
        self.fallback_channels = fallback_channels or []
        
        # Default failure code classifications
        self.permanent_failure_codes = permanent_failure_codes or [
            "INVALID_EMAIL", "INVALID_RECIPIENT", "NO_ADAPTER", 
            "ADAPTER_DISABLED", "AUTHENTICATION_FAILED", "FORBIDDEN"
        ]
        
        self.transient_failure_codes = transient_failure_codes or [
            "NETWORK_ERROR", "TIMEOUT", "CONNECTION_FAILED", "TEMPORARY_UNAVAILABLE",
            "RATE_LIMITED", "SERVER_ERROR", "SERVICE_UNAVAILABLE"
        ]


class RetryManager:
    """
    Manages retry logic and fallback mechanisms for notification delivery.
    
    Features:
    - Exponential backoff with jitter
    - Channel fallback on persistent failures
    - Dead letter queue for failed notifications
    - Integration with delivery history tracking
    - Configurable retry policies per notification type
    """
    
    def __init__(
        self,
        default_config: Optional[RetryConfiguration] = None,
        type_specific_configs: Optional[Dict[str, RetryConfiguration]] = None
    ):
        """
        Initialize retry manager.
        
        Args:
            default_config: Default retry configuration
            type_specific_configs: Notification type-specific configurations
        """
        self.default_config = default_config or RetryConfiguration()
        self.type_specific_configs = type_specific_configs or {}
        self.logger = logger.bind(service="RetryManager")
        
        # Dead letter queue for failed notifications
        self.dead_letter_queue: List[Dict[str, Any]] = []
    
    async def execute_with_retry(
        self,
        notification: NotificationModel,
        channel: NotificationChannel,
        adapter: NotificationChannelAdapter,
        payload: NotificationPayload,
        history: NotificationDeliveryHistory,
        dispatch_function: Callable[[NotificationPayload], Awaitable[NotificationResult]]
    ) -> NotificationResult:
        """
        Execute notification delivery with retry logic.
        
        Args:
            notification: Notification being sent
            channel: Target channel
            adapter: Channel adapter
            payload: Notification payload
            history: Delivery history record
            dispatch_function: Function to call for delivery
            
        Returns:
            Final NotificationResult after all retry attempts
        """
        config = self._get_retry_config(notification.type.value)
        attempt_count = 0
        last_result = None
        
        self.logger.info(
            "Starting delivery with retry logic",
            notification_id=notification.notification_id,
            channel=channel.value,
            max_attempts=config.max_retry_attempts
        )
        
        while attempt_count <= config.max_retry_attempts:
            try:
                # Execute delivery attempt
                result = await dispatch_function(payload)
                last_result = result
                
                # Check if delivery was successful
                if result.success:
                    self.logger.info(
                        "Delivery successful",
                        notification_id=notification.notification_id,
                        channel=channel.value,
                        attempt=attempt_count + 1
                    )
                    return result
                
                # Determine failure type
                failure_type = self._classify_failure(result.error_code)
                
                # Don't retry permanent failures
                if failure_type == FailureType.PERMANENT:
                    self.logger.warning(
                        "Permanent failure detected, stopping retries",
                        notification_id=notification.notification_id,
                        channel=channel.value,
                        error_code=result.error_code
                    )
                    break
                
                # Check if we should retry
                if attempt_count >= config.max_retry_attempts:
                    self.logger.warning(
                        "Maximum retry attempts reached",
                        notification_id=notification.notification_id,
                        channel=channel.value,
                        attempts=attempt_count + 1
                    )
                    break
                
                # Calculate delay before next retry
                delay = self._calculate_retry_delay(config, attempt_count, failure_type)
                
                self.logger.info(
                    "Retrying delivery after delay",
                    notification_id=notification.notification_id,
                    channel=channel.value,
                    attempt=attempt_count + 1,
                    delay_seconds=delay,
                    error_code=result.error_code
                )
                
                # Wait before retry
                await asyncio.sleep(delay)
                
                attempt_count += 1
                
            except Exception as e:
                self.logger.error(
                    "Exception during retry attempt",
                    notification_id=notification.notification_id,
                    channel=channel.value,
                    attempt=attempt_count + 1,
                    error=str(e),
                    exc_info=True
                )
                
                # Create error result
                last_result = NotificationResult(
                    channel=channel.value,
                    notification_id=notification.notification_id,
                    status=NotificationResultStatus.FAILURE,
                    success=False,
                    error_code="RETRY_EXCEPTION",
                    error_message=str(e)
                )
                
                if attempt_count >= config.max_retry_attempts:
                    break
                
                attempt_count += 1
                
                # Wait before retry on exception
                delay = self._calculate_retry_delay(config, attempt_count - 1, FailureType.TRANSIENT)
                await asyncio.sleep(delay)
        
        # All retries exhausted
        self.logger.error(
            "All retry attempts exhausted",
            notification_id=notification.notification_id,
            channel=channel.value,
            total_attempts=attempt_count + 1
        )
        
        return last_result or NotificationResult(
            channel=channel.value,
            notification_id=notification.notification_id,
            status=NotificationResultStatus.FAILURE,
            success=False,
            error_code="RETRY_EXHAUSTED",
            error_message="All retry attempts failed"
        )
    
    async def execute_with_fallback(
        self,
        notification: NotificationModel,
        primary_channels: List[NotificationChannel],
        channel_adapters: Dict[str, NotificationChannelAdapter],
        payload: NotificationPayload,
        history: NotificationDeliveryHistory,
        dispatch_function: Callable[[NotificationChannel, NotificationPayload], Awaitable[NotificationResult]]
    ) -> Dict[str, NotificationResult]:
        """
        Execute notification delivery with channel fallback.
        
        Args:
            notification: Notification being sent
            primary_channels: Primary channels to try
            channel_adapters: Available channel adapters
            payload: Notification payload
            history: Delivery history record
            dispatch_function: Function to call for delivery
            
        Returns:
            Dict mapping channel names to delivery results
        """
        config = self._get_retry_config(notification.type.value)
        results = {}
        
        # Try primary channels first
        for channel in primary_channels:
            if channel.value not in channel_adapters:
                continue
                
            adapter = channel_adapters[channel.value]
            if not adapter.is_enabled():
                continue
            
            self.logger.info(
                "Attempting delivery on primary channel",
                notification_id=notification.notification_id,
                channel=channel.value
            )
            
            # Execute with retry for this channel
            result = await self.execute_with_retry(
                notification, channel, adapter, payload, history,
                lambda p: dispatch_function(channel, p)
            )
            
            results[channel.value] = result
            
            # If successful, we're done
            if result.success:
                self.logger.info(
                    "Primary channel delivery successful",
                    notification_id=notification.notification_id,
                    channel=channel.value
                )
                return results
        
        # If fallback is disabled or no fallback channels, return results
        if not config.enable_fallback or not config.fallback_channels:
            return results
        
        # Try fallback channels
        self.logger.info(
            "Primary channels failed, trying fallback channels",
            notification_id=notification.notification_id,
            fallback_channels=[ch.value for ch in config.fallback_channels]
        )
        
        for fallback_channel in config.fallback_channels:
            # Skip if already tried or not available
            if (fallback_channel.value in results or 
                fallback_channel.value not in channel_adapters):
                continue
            
            adapter = channel_adapters[fallback_channel.value]
            if not adapter.is_enabled():
                continue
            
            self.logger.info(
                "Attempting delivery on fallback channel",
                notification_id=notification.notification_id,
                channel=fallback_channel.value
            )
            
            # Execute with retry for fallback channel
            result = await self.execute_with_retry(
                notification, fallback_channel, adapter, payload, history,
                lambda p: dispatch_function(fallback_channel, p)
            )
            
            results[fallback_channel.value] = result
            
            # If successful, we're done
            if result.success:
                self.logger.info(
                    "Fallback channel delivery successful",
                    notification_id=notification.notification_id,
                    channel=fallback_channel.value
                )
                return results
        
        # All channels failed - add to dead letter queue
        await self._add_to_dead_letter_queue(notification, results)
        
        return results
    
    async def _add_to_dead_letter_queue(
        self,
        notification: NotificationModel,
        failed_results: Dict[str, NotificationResult]
    ) -> None:
        """
        Add failed notification to dead letter queue.
        
        Args:
            notification: Failed notification
            failed_results: Results from all attempted channels
        """
        dead_letter_entry = {
            "notification_id": notification.notification_id,
            "notification_type": notification.type.value,
            "priority": notification.priority.value,
            "created_at": notification.created_at,
            "failed_at": datetime.now(timezone.utc),
            "attempted_channels": list(failed_results.keys()),
            "failure_reasons": {
                channel: {
                    "error_code": result.error_code,
                    "error_message": result.error_message
                }
                for channel, result in failed_results.items()
            },
            "retry_count": len(failed_results),
            "notification_data": {
                "title": notification.title,
                "recipients": [r.dict() if hasattr(r, 'dict') else r for r in notification.recipients],
                "content": notification.content,
                "source_service": notification.source_service
            }
        }
        
        self.dead_letter_queue.append(dead_letter_entry)
        
        self.logger.error(
            "Notification added to dead letter queue",
            notification_id=notification.notification_id,
            attempted_channels=list(failed_results.keys()),
            queue_size=len(self.dead_letter_queue)
        )
    
    def _get_retry_config(self, notification_type: str) -> RetryConfiguration:
        """Get retry configuration for notification type."""
        return self.type_specific_configs.get(notification_type, self.default_config)
    
    def _classify_failure(self, error_code: Optional[str]) -> FailureType:
        """
        Classify failure type based on error code.
        
        Args:
            error_code: Error code from delivery attempt
            
        Returns:
            FailureType classification
        """
        if not error_code:
            return FailureType.TRANSIENT
        
        error_code_upper = error_code.upper()
        
        # Check for permanent failures
        for permanent_code in self.default_config.permanent_failure_codes:
            if permanent_code.upper() in error_code_upper:
                return FailureType.PERMANENT
        
        # Check for rate limiting
        if "RATE" in error_code_upper and "LIMIT" in error_code_upper:
            return FailureType.RATE_LIMITED
        
        # Check for transient failures
        for transient_code in self.default_config.transient_failure_codes:
            if transient_code.upper() in error_code_upper:
                return FailureType.TRANSIENT
        
        # Default to transient for unknown errors
        return FailureType.TRANSIENT
    
    def _calculate_retry_delay(
        self,
        config: RetryConfiguration,
        attempt_number: int,
        failure_type: FailureType
    ) -> float:
        """
        Calculate delay before next retry attempt.
        
        Args:
            config: Retry configuration
            attempt_number: Current attempt number (0-based)
            failure_type: Type of failure
            
        Returns:
            Delay in seconds
        """
        # Base delay calculation
        if config.retry_policy == RetryPolicy.FIXED:
            delay = config.base_delay_seconds
        elif config.retry_policy == RetryPolicy.LINEAR:
            delay = config.base_delay_seconds * (attempt_number + 1)
        else:  # EXPONENTIAL
            delay = config.base_delay_seconds * (config.retry_multiplier ** attempt_number)
        
        # Apply special handling for rate limiting
        if failure_type == FailureType.RATE_LIMITED:
            # Longer delay for rate limiting
            delay = max(delay, 60.0)  # At least 1 minute
        
        # Cap at maximum delay
        delay = min(delay, config.max_delay_seconds)
        
        # Add jitter to prevent thundering herd
        if config.jitter_factor > 0:
            jitter = delay * config.jitter_factor * random.random()
            delay += jitter
        
        return delay
    
    def get_dead_letter_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the dead letter queue."""
        if not self.dead_letter_queue:
            return {
                "total_failed": 0,
                "by_type": {},
                "by_channel": {},
                "oldest_failure": None,
                "newest_failure": None
            }
        
        # Count by notification type
        type_counts = {}
        channel_counts = {}
        
        for entry in self.dead_letter_queue:
            # Count by type
            ntype = entry["notification_type"]
            type_counts[ntype] = type_counts.get(ntype, 0) + 1
            
            # Count by attempted channels
            for channel in entry["attempted_channels"]:
                channel_counts[channel] = channel_counts.get(channel, 0) + 1
        
        # Find oldest and newest failures
        failed_times = [entry["failed_at"] for entry in self.dead_letter_queue]
        
        return {
            "total_failed": len(self.dead_letter_queue),
            "by_type": type_counts,
            "by_channel": channel_counts,
            "oldest_failure": min(failed_times).isoformat() if failed_times else None,
            "newest_failure": max(failed_times).isoformat() if failed_times else None
        }
    
    def clear_dead_letter_queue(self) -> int:
        """Clear dead letter queue and return number of entries cleared."""
        count = len(self.dead_letter_queue)
        self.dead_letter_queue.clear()
        return count 