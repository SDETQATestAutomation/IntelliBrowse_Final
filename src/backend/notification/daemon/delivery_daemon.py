"""
IntelliBrowse Notification Engine - Delivery Daemon

This module implements the core notification delivery daemon that continuously
processes pending notifications, manages channel adapters, and provides
robust background task processing with retry logic and graceful shutdown.

Classes:
    - DeliveryDaemon: Main delivery daemon with async processing
    - DaemonConfig: Configuration for daemon operation
    - ChannelManager: Manages channel adapter lifecycle
    - HealthMonitor: Monitors daemon and adapter health

Author: IntelliBrowse Team
Created: Phase 5 - Background Tasks & Delivery Daemon Implementation
"""

import asyncio
import logging
import signal
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Type
from enum import Enum
from dataclasses import dataclass
import uuid

from pydantic import BaseModel, Field
from pymongo.collection import Collection

# Import channel adapters and utilities
from ..adapters.channel.base_adapter import (
    BaseChannelAdapter,
    ChannelType,
    DeliveryContext,
    DeliveryPriority
)
from ..adapters.channel.email_adapter import EmailAdapter, EmailConfig
from ..adapters.channel.in_app_adapter import InAppAdapter, InAppConfig

# Import services and models
from ..services.delivery_task_service import (
    DeliveryTaskService,
    DeliveryResult,
    DeliveryResultStatus,
    NotificationQuery
)
from ..models.notification_model import NotificationModel
from ..schemas.user_context import UserContext
from ..utils.retry import (
    RetryPolicy,
    RetryableOperation,
    DEFAULT_RETRY_POLICY,
    EMAIL_DELIVERY_RETRY_POLICY
)

# Configure logging
logger = logging.getLogger(__name__)


class DaemonState(str, Enum):
    """Enumeration of daemon states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class DaemonConfig(BaseModel):
    """
    Configuration for delivery daemon operation
    
    Provides comprehensive configuration options for daemon behavior,
    processing intervals, batch sizes, and error handling.
    """
    
    # Processing configuration
    polling_interval_seconds: float = Field(default=5.0, description="Polling interval for pending notifications")
    batch_size: int = Field(default=50, description="Number of notifications to process per batch")
    max_concurrent_deliveries: int = Field(default=10, description="Maximum concurrent delivery tasks")
    
    # Retry configuration
    default_retry_policy: RetryPolicy = Field(default=DEFAULT_RETRY_POLICY, description="Default retry policy")
    
    # Health monitoring
    health_check_interval_seconds: float = Field(default=60.0, description="Health check interval")
    max_consecutive_failures: int = Field(default=5, description="Max failures before marking adapter unhealthy")
    
    # Cleanup configuration
    cleanup_interval_hours: int = Field(default=24, description="Cleanup interval in hours")
    audit_retention_days: int = Field(default=30, description="Audit log retention in days")
    
    # Performance configuration
    processing_timeout_seconds: float = Field(default=300.0, description="Processing timeout per batch")
    graceful_shutdown_timeout_seconds: float = Field(default=30.0, description="Graceful shutdown timeout")
    
    # Channel configuration
    enabled_channels: List[ChannelType] = Field(
        default=[ChannelType.EMAIL, ChannelType.IN_APP],
        description="Enabled notification channels"
    )
    
    # Priority processing
    priority_processing_enabled: bool = Field(default=True, description="Enable priority-based processing")
    critical_priority_batch_size: int = Field(default=20, description="Batch size for critical priority notifications")


@dataclass
class DaemonStats:
    """Statistics tracking for delivery daemon"""
    start_time: datetime
    total_notifications_processed: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    retry_attempts: int = 0
    
    # Performance metrics
    average_processing_time_ms: float = 0.0
    last_batch_processing_time_ms: float = 0.0
    
    # Health metrics
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    
    def get_success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_notifications_processed == 0:
            return 0.0
        return self.successful_deliveries / self.total_notifications_processed
    
    def get_uptime_seconds(self) -> float:
        """Calculate uptime in seconds"""
        return (datetime.now(timezone.utc) - self.start_time).total_seconds()


class HealthMonitor:
    """
    Health monitoring for delivery daemon and channel adapters
    
    Provides comprehensive health checking, performance monitoring,
    and automatic recovery for unhealthy components.
    """
    
    def __init__(self, config: DaemonConfig):
        """
        Initialize health monitor
        
        Args:
            config: Daemon configuration
        """
        self.config = config
        self.logger = logger.bind(component="HealthMonitor")
        
        # Health state tracking
        self._adapter_health: Dict[str, bool] = {}
        self._adapter_failure_counts: Dict[str, int] = {}
        self._last_health_check = None
    
    async def check_adapter_health(self, adapters: Dict[ChannelType, BaseChannelAdapter]) -> Dict[str, bool]:
        """
        Check health of all channel adapters
        
        Args:
            adapters: Dictionary of channel adapters
            
        Returns:
            Dictionary of adapter health status
        """
        health_results = {}
        
        for channel_type, adapter in adapters.items():
            try:
                is_healthy = await adapter.health_check()
                health_results[channel_type.value] = is_healthy
                
                if is_healthy:
                    # Reset failure count on successful health check
                    self._adapter_failure_counts[channel_type.value] = 0
                else:
                    # Increment failure count
                    self._adapter_failure_counts[channel_type.value] = \
                        self._adapter_failure_counts.get(channel_type.value, 0) + 1
                    
                    self.logger.warning(
                        f"Adapter {channel_type.value} health check failed",
                        consecutive_failures=self._adapter_failure_counts[channel_type.value]
                    )
                
            except Exception as e:
                health_results[channel_type.value] = False
                self._adapter_failure_counts[channel_type.value] = \
                    self._adapter_failure_counts.get(channel_type.value, 0) + 1
                
                self.logger.error(
                    f"Error checking {channel_type.value} adapter health",
                    error=str(e),
                    consecutive_failures=self._adapter_failure_counts[channel_type.value],
                    exc_info=True
                )
        
        self._adapter_health = health_results
        self._last_health_check = datetime.now(timezone.utc)
        
        return health_results
    
    def is_adapter_healthy(self, channel_type: ChannelType) -> bool:
        """Check if specific adapter is healthy"""
        failure_count = self._adapter_failure_counts.get(channel_type.value, 0)
        return failure_count < self.config.max_consecutive_failures
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary"""
        return {
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
            "adapter_health": self._adapter_health.copy(),
            "adapter_failure_counts": self._adapter_failure_counts.copy(),
            "unhealthy_adapters": [
                channel for channel, count in self._adapter_failure_counts.items()
                if count >= self.config.max_consecutive_failures
            ]
        }


class ChannelManager:
    """
    Manages channel adapter lifecycle and routing
    
    Handles adapter initialization, configuration, and routing
    of notifications to appropriate delivery channels.
    """
    
    def __init__(self, config: DaemonConfig, collections: Dict[str, Collection]):
        """
        Initialize channel manager
        
        Args:
            config: Daemon configuration
            collections: MongoDB collections for adapters
        """
        self.config = config
        self.collections = collections
        self.logger = logger.bind(component="ChannelManager")
        
        # Adapter registry
        self.adapters: Dict[ChannelType, BaseChannelAdapter] = {}
        self.adapter_configs: Dict[ChannelType, Any] = {}
    
    async def initialize_adapters(self) -> bool:
        """
        Initialize all enabled channel adapters
        
        Returns:
            True if all adapters initialized successfully
        """
        self.logger.info("Initializing channel adapters")
        
        success = True
        
        for channel_type in self.config.enabled_channels:
            try:
                adapter = await self._create_adapter(channel_type)
                if adapter:
                    initialization_result = await adapter.initialize()
                    if initialization_result:
                        self.adapters[channel_type] = adapter
                        self.logger.info(f"Initialized {channel_type.value} adapter successfully")
                    else:
                        self.logger.error(f"Failed to initialize {channel_type.value} adapter")
                        success = False
                else:
                    self.logger.error(f"Failed to create {channel_type.value} adapter")
                    success = False
                    
            except Exception as e:
                self.logger.error(
                    f"Error initializing {channel_type.value} adapter",
                    error=str(e),
                    exc_info=True
                )
                success = False
        
        self.logger.info(
            f"Channel adapter initialization complete",
            initialized_count=len(self.adapters),
            total_requested=len(self.config.enabled_channels),
            success=success
        )
        
        return success
    
    async def _create_adapter(self, channel_type: ChannelType) -> Optional[BaseChannelAdapter]:
        """Create adapter instance for channel type"""
        try:
            if channel_type == ChannelType.EMAIL:
                # Create email adapter configuration
                email_config = EmailConfig(
                    smtp_host="localhost",  # Should be loaded from environment
                    smtp_port=587,
                    use_tls=True,
                    default_from_email="noreply@intellibrowse.com",
                    default_from_name="IntelliBrowse",
                    username=None,  # Should be loaded from environment
                    password=None   # Should be loaded from environment
                )
                return EmailAdapter(email_config)
                
            elif channel_type == ChannelType.IN_APP:
                # Create in-app adapter configuration
                in_app_config = InAppConfig()
                collection = self.collections.get("in_app_notifications")
                if collection:
                    return InAppAdapter(in_app_config, collection)
                else:
                    self.logger.error("In-app notifications collection not provided")
                    return None
            
            else:
                self.logger.warning(f"Unsupported channel type: {channel_type.value}")
                return None
                
        except Exception as e:
            self.logger.error(
                f"Error creating {channel_type.value} adapter",
                error=str(e),
                exc_info=True
            )
            return None
    
    def get_adapter(self, channel_type: ChannelType) -> Optional[BaseChannelAdapter]:
        """Get adapter for channel type"""
        return self.adapters.get(channel_type)
    
    def get_all_adapters(self) -> Dict[ChannelType, BaseChannelAdapter]:
        """Get all adapters"""
        return self.adapters.copy()
    
    async def shutdown_adapters(self):
        """Shutdown all adapters"""
        self.logger.info("Shutting down channel adapters")
        
        for channel_type, adapter in self.adapters.items():
            try:
                await adapter.shutdown()
                self.logger.info(f"Shut down {channel_type.value} adapter")
            except Exception as e:
                self.logger.warning(
                    f"Error shutting down {channel_type.value} adapter",
                    error=str(e)
                )
        
        self.adapters.clear()


class DeliveryDaemon:
    """
    Main notification delivery daemon
    
    Provides continuous background processing of pending notifications
    with robust error handling, retry logic, and graceful shutdown.
    """
    
    def __init__(
        self,
        config: DaemonConfig,
        delivery_service: DeliveryTaskService,
        collections: Dict[str, Collection]
    ):
        """
        Initialize delivery daemon
        
        Args:
            config: Daemon configuration
            delivery_service: Delivery task service
            collections: MongoDB collections for adapters
        """
        self.config = config
        self.delivery_service = delivery_service
        self.collections = collections
        
        # Daemon state
        self.state = DaemonState.STOPPED
        self.stats = DaemonStats(start_time=datetime.now(timezone.utc))
        self.daemon_id = f"daemon_{uuid.uuid4().hex[:8]}"
        
        # Component managers
        self.channel_manager = ChannelManager(config, collections)
        self.health_monitor = HealthMonitor(config)
        
        # Async task management
        self._running_tasks: List[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        self._processing_semaphore = asyncio.Semaphore(config.max_concurrent_deliveries)
        
        # Performance tracking
        self._processing_times: List[float] = []
        self._last_cleanup = datetime.now(timezone.utc)
        
        self.logger = logger.bind(daemon_id=self.daemon_id)
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    async def start(self) -> bool:
        """
        Start the delivery daemon
        
        Returns:
            True if started successfully, False otherwise
        """
        try:
            self.logger.info("Starting notification delivery daemon")
            self.state = DaemonState.STARTING
            
            # Initialize channel adapters
            adapters_initialized = await self.channel_manager.initialize_adapters()
            if not adapters_initialized:
                self.logger.error("Failed to initialize channel adapters")
                self.state = DaemonState.ERROR
                return False
            
            # Start background tasks
            self._start_background_tasks()
            
            self.state = DaemonState.RUNNING
            self.stats.start_time = datetime.now(timezone.utc)
            
            self.logger.info("Notification delivery daemon started successfully")
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to start delivery daemon",
                error=str(e),
                exc_info=True
            )
            self.state = DaemonState.ERROR
            return False
    
    def _start_background_tasks(self):
        """Start background processing tasks"""
        # Main processing loop
        processing_task = asyncio.create_task(self._processing_loop())
        self._running_tasks.append(processing_task)
        
        # Health monitoring task
        health_task = asyncio.create_task(self._health_monitoring_loop())
        self._running_tasks.append(health_task)
        
        # Cleanup task
        cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._running_tasks.append(cleanup_task)
    
    async def _processing_loop(self):
        """Main notification processing loop"""
        self.logger.info("Starting notification processing loop")
        
        while not self._shutdown_event.is_set():
            try:
                await self._process_pending_notifications()
                
                # Wait for next polling interval
                await asyncio.sleep(self.config.polling_interval_seconds)
                
            except asyncio.CancelledError:
                self.logger.info("Processing loop cancelled")
                break
            except Exception as e:
                self.logger.error(
                    "Error in processing loop",
                    error=str(e),
                    exc_info=True
                )
                self.stats.consecutive_failures += 1
                
                # Back off on consecutive failures
                if self.stats.consecutive_failures > 3:
                    await asyncio.sleep(self.config.polling_interval_seconds * 2)
    
    async def _process_pending_notifications(self):
        """Process pending notifications in batches"""
        start_time = time.time()
        
        try:
            # Get pending notifications with priority handling
            notifications = await self._get_prioritized_notifications()
            
            if not notifications:
                return
            
            self.logger.info(
                f"Processing {len(notifications)} pending notifications",
                batch_size=len(notifications)
            )
            
            # Process notifications concurrently
            tasks = []
            for notification in notifications:
                task = asyncio.create_task(
                    self._process_single_notification(notification)
                )
                tasks.append(task)
            
            # Wait for all deliveries to complete with timeout
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.config.processing_timeout_seconds
            )
            
            # Update performance metrics
            processing_time = (time.time() - start_time) * 1000
            self.stats.last_batch_processing_time_ms = processing_time
            self._processing_times.append(processing_time)
            
            # Keep only recent processing times for average calculation
            if len(self._processing_times) > 100:
                self._processing_times = self._processing_times[-100:]
            
            self.stats.average_processing_time_ms = sum(self._processing_times) / len(self._processing_times)
            self.stats.consecutive_failures = 0  # Reset on successful batch
            
        except asyncio.TimeoutError:
            self.logger.warning(
                "Notification processing batch timed out",
                timeout_seconds=self.config.processing_timeout_seconds
            )
            self.stats.consecutive_failures += 1
        except Exception as e:
            self.logger.error(
                "Error processing notification batch",
                error=str(e),
                exc_info=True
            )
            self.stats.consecutive_failures += 1
    
    async def _get_prioritized_notifications(self) -> List[NotificationModel]:
        """Get pending notifications with priority-based ordering"""
        notifications = []
        
        if self.config.priority_processing_enabled:
            # First, get critical priority notifications
            critical_query = NotificationQuery(
                limit=self.config.critical_priority_batch_size,
                statuses=[],  # Will be set in delivery service
                min_priority="critical"
            )
            
            critical_notifications = await self.delivery_service.get_pending_notifications(critical_query)
            notifications.extend(critical_notifications)
            
            # Then get remaining notifications up to batch size
            remaining_slots = self.config.batch_size - len(critical_notifications)
            if remaining_slots > 0:
                regular_query = NotificationQuery(limit=remaining_slots)
                regular_notifications = await self.delivery_service.get_pending_notifications(regular_query)
                notifications.extend(regular_notifications)
        else:
            # Simple batch processing without priority
            query = NotificationQuery(limit=self.config.batch_size)
            notifications = await self.delivery_service.get_pending_notifications(query)
        
        return notifications
    
    async def _process_single_notification(self, notification: NotificationModel):
        """Process a single notification with retry logic"""
        async with self._processing_semaphore:
            try:
                # Determine delivery channel
                channel_type = self._determine_delivery_channel(notification)
                
                if not channel_type:
                    self.logger.warning(
                        "No suitable delivery channel found for notification",
                        notification_id=notification.notification_id
                    )
                    return
                
                # Get channel adapter
                adapter = self.channel_manager.get_adapter(channel_type)
                if not adapter:
                    self.logger.error(
                        f"Adapter not available for channel {channel_type.value}",
                        notification_id=notification.notification_id
                    )
                    return
                
                # Check adapter health
                if not self.health_monitor.is_adapter_healthy(channel_type):
                    self.logger.warning(
                        f"Skipping delivery - adapter {channel_type.value} is unhealthy",
                        notification_id=notification.notification_id
                    )
                    return
                
                # Create delivery context
                context = await self._create_delivery_context(notification, channel_type)
                
                # Attempt delivery with retry logic
                retry_operation = RetryableOperation(
                    operation_name=f"deliver_{channel_type.value}",
                    policy=self._get_retry_policy_for_channel(channel_type)
                )
                
                result = await retry_operation.execute(adapter.send, context)
                
                # Handle delivery result
                await self._handle_delivery_result(notification, context, result)
                
            except Exception as e:
                self.logger.error(
                    "Error processing notification",
                    notification_id=notification.notification_id,
                    error=str(e),
                    exc_info=True
                )
                
                # Mark as failed
                failure_result = DeliveryResult(
                    notification_id=notification.notification_id,
                    user_id=notification.user_id,
                    channel="unknown",
                    status=DeliveryResultStatus.FAILED,
                    attempt_timestamp=datetime.now(timezone.utc),
                    processing_time_ms=0.0,
                    success=False,
                    error_message=str(e),
                    error_code="PROCESSING_ERROR",
                    error_details=None,
                    external_id=None,
                    response_data=None,
                    attempt_number=1,
                    max_attempts=1,
                    should_retry=False,
                    next_retry_at=None
                )
                
                await self.delivery_service.mark_as_failed(
                    notification_id=notification.notification_id,
                    user_id=notification.user_id,
                    channel="unknown",
                    result=failure_result
                )
                
                self.stats.failed_deliveries += 1
                self.stats.total_notifications_processed += 1
    
    def _determine_delivery_channel(self, notification: NotificationModel) -> Optional[ChannelType]:
        """Determine appropriate delivery channel for notification"""
        # Check notification metadata for preferred channel
        preferred_channel = notification.metadata.get("preferred_channel")
        if preferred_channel:
            try:
                channel_type = ChannelType(preferred_channel)
                if channel_type in self.config.enabled_channels:
                    return channel_type
            except ValueError:
                pass
        
        # Default channel selection based on priority
        if notification.priority == "critical":
            # Critical notifications prefer immediate channels
            for channel in [ChannelType.IN_APP, ChannelType.EMAIL]:
                if channel in self.config.enabled_channels:
                    return channel
        
        # Default to first enabled channel
        if self.config.enabled_channels:
            return self.config.enabled_channels[0]
        
        return None
    
    async def _create_delivery_context(
        self,
        notification: NotificationModel,
        channel_type: ChannelType
    ) -> DeliveryContext:
        """Create delivery context for notification"""
        # This would typically fetch user context from user service
        # For now, creating a mock user context
        user_context = UserContext(
            user_id=notification.user_id,
            username=f"user_{notification.user_id}",
            email=f"user_{notification.user_id}@example.com",
            full_name=f"User {notification.user_id}",
            preferences={}
        )
        
        return DeliveryContext(
            notification_id=notification.notification_id,
            user_id=notification.user_id,
            correlation_id=f"delivery_{uuid.uuid4().hex[:12]}",
            user_context=user_context,
            notification=notification,
            preferred_channel=channel_type,
            delivery_priority=DeliveryPriority(notification.priority),
            attempt_number=1,
            metadata={}
        )
    
    def _get_retry_policy_for_channel(self, channel_type: ChannelType) -> RetryPolicy:
        """Get retry policy for specific channel"""
        if channel_type == ChannelType.EMAIL:
            return EMAIL_DELIVERY_RETRY_POLICY
        else:
            return self.config.default_retry_policy
    
    async def _handle_delivery_result(
        self,
        notification: NotificationModel,
        context: DeliveryContext,
        result: DeliveryResult
    ):
        """Handle delivery result and update notification status"""
        if result.success:
            await self.delivery_service.mark_as_delivered(
                notification_id=notification.notification_id,
                user_id=notification.user_id,
                channel=result.channel,
                result=result
            )
            self.stats.successful_deliveries += 1
        else:
            await self.delivery_service.mark_as_failed(
                notification_id=notification.notification_id,
                user_id=notification.user_id,
                channel=result.channel,
                result=result
            )
            self.stats.failed_deliveries += 1
            
            if result.should_retry:
                self.stats.retry_attempts += 1
        
        self.stats.total_notifications_processed += 1
    
    async def _health_monitoring_loop(self):
        """Health monitoring background task"""
        self.logger.info("Starting health monitoring loop")
        
        while not self._shutdown_event.is_set():
            try:
                # Check adapter health
                adapters = self.channel_manager.get_all_adapters()
                await self.health_monitor.check_adapter_health(adapters)
                
                self.stats.last_health_check = datetime.now(timezone.utc)
                
                await asyncio.sleep(self.config.health_check_interval_seconds)
                
            except asyncio.CancelledError:
                self.logger.info("Health monitoring loop cancelled")
                break
            except Exception as e:
                self.logger.error(
                    "Error in health monitoring loop",
                    error=str(e),
                    exc_info=True
                )
    
    async def _cleanup_loop(self):
        """Cleanup background task"""
        self.logger.info("Starting cleanup loop")
        
        while not self._shutdown_event.is_set():
            try:
                current_time = datetime.now(timezone.utc)
                
                # Check if cleanup is due
                time_since_last_cleanup = current_time - self._last_cleanup
                if time_since_last_cleanup.total_seconds() >= (self.config.cleanup_interval_hours * 3600):
                    await self._perform_cleanup()
                    self._last_cleanup = current_time
                
                # Sleep for 1 hour between cleanup checks
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                self.logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                self.logger.error(
                    "Error in cleanup loop",
                    error=str(e),
                    exc_info=True
                )
    
    async def _perform_cleanup(self):
        """Perform cleanup operations"""
        self.logger.info("Performing cleanup operations")
        
        try:
            # Clean up old audit logs
            deleted_count = await self.delivery_service.cleanup_old_audit_logs(
                retention_days=self.config.audit_retention_days
            )
            
            self.logger.info(f"Cleaned up {deleted_count} old audit logs")
            
            # Clean up expired in-app notifications
            in_app_adapter = self.channel_manager.get_adapter(ChannelType.IN_APP)
            if in_app_adapter and hasattr(in_app_adapter, 'cleanup_expired_notifications'):
                expired_count = await in_app_adapter.cleanup_expired_notifications()
                self.logger.info(f"Cleaned up {expired_count} expired in-app notifications")
            
        except Exception as e:
            self.logger.error(
                "Error during cleanup operations",
                error=str(e),
                exc_info=True
            )
    
    async def shutdown(self):
        """Gracefully shutdown the delivery daemon"""
        if self.state == DaemonState.STOPPING:
            return
        
        self.logger.info("Initiating graceful shutdown of delivery daemon")
        self.state = DaemonState.STOPPING
        
        # Signal shutdown to all loops
        self._shutdown_event.set()
        
        # Cancel all running tasks
        for task in self._running_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete with timeout
        if self._running_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._running_tasks, return_exceptions=True),
                    timeout=self.config.graceful_shutdown_timeout_seconds
                )
            except asyncio.TimeoutError:
                self.logger.warning("Some tasks did not complete within shutdown timeout")
        
        # Shutdown channel adapters
        await self.channel_manager.shutdown_adapters()
        
        self.state = DaemonState.STOPPED
        self.logger.info("Delivery daemon shutdown complete")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive daemon status"""
        return {
            "daemon_id": self.daemon_id,
            "state": self.state.value,
            "uptime_seconds": self.stats.get_uptime_seconds(),
            "statistics": {
                "total_processed": self.stats.total_notifications_processed,
                "successful_deliveries": self.stats.successful_deliveries,
                "failed_deliveries": self.stats.failed_deliveries,
                "retry_attempts": self.stats.retry_attempts,
                "success_rate": self.stats.get_success_rate(),
                "average_processing_time_ms": self.stats.average_processing_time_ms,
                "last_batch_processing_time_ms": self.stats.last_batch_processing_time_ms
            },
            "health": self.health_monitor.get_health_summary(),
            "configuration": {
                "polling_interval_seconds": self.config.polling_interval_seconds,
                "batch_size": self.config.batch_size,
                "max_concurrent_deliveries": self.config.max_concurrent_deliveries,
                "enabled_channels": [channel.value for channel in self.config.enabled_channels]
            }
        }