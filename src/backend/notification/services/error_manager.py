"""
Notification Module - Error Manager

Comprehensive error handling, circuit breaker patterns, and timeout management.
Provides structured error categorization and failure pattern detection.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque

from ..models import NotificationChannel
from .channel_adapter_base import NotificationResult, NotificationResultStatus
from ...config.logging import get_logger

logger = get_logger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorMetrics:
    """Error metrics for monitoring."""
    total_errors: int = 0
    errors_by_code: Dict[str, int] = field(default_factory=dict)
    errors_by_channel: Dict[str, int] = field(default_factory=dict)
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    first_error_time: Optional[datetime] = None
    last_error_time: Optional[datetime] = None
    error_rate_per_minute: float = 0.0
    consecutive_failures: int = 0


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 3  # Successes before closing circuit
    timeout_seconds: int = 60   # Time to wait before half-open
    monitoring_window_seconds: int = 300  # 5 minutes
    error_rate_threshold: float = 0.5  # 50% error rate threshold


class CircuitBreaker:
    """
    Circuit breaker implementation for channel adapters.
    
    Prevents cascade failures by temporarily blocking requests
    to consistently failing services.
    """
    
    def __init__(self, channel: str, config: CircuitBreakerConfig):
        """
        Initialize circuit breaker.
        
        Args:
            channel: Channel name this breaker protects
            config: Circuit breaker configuration
        """
        self.channel = channel
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state_changed_time = datetime.now(timezone.utc)
        
        # Track recent requests for error rate calculation
        self.recent_requests = deque(maxlen=100)
        
        self.logger = logger.bind(
            circuit_breaker=True,
            channel=channel
        )
    
    async def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        # Check circuit state
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker open for channel: {self.channel}"
                )
        
        # Record request start
        request_start = time.time()
        
        try:
            # Execute function
            result = await func(*args, **kwargs)
            
            # Record success
            self._record_success(request_start)
            
            return result
            
        except Exception as e:
            # Record failure
            self._record_failure(request_start, str(e))
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset from open to half-open."""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = datetime.now(timezone.utc) - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.timeout_seconds
    
    def _transition_to_half_open(self):
        """Transition circuit breaker to half-open state."""
        self.state = CircuitBreakerState.HALF_OPEN
        self.success_count = 0
        self.state_changed_time = datetime.now(timezone.utc)
        
        self.logger.info(
            "Circuit breaker transitioned to half-open",
            channel=self.channel
        )
    
    def _record_success(self, request_start_time: float):
        """Record successful request."""
        duration = time.time() - request_start_time
        
        self.recent_requests.append({
            "success": True,
            "timestamp": datetime.now(timezone.utc),
            "duration": duration
        })
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        
        # Reset failure count on success
        self.failure_count = 0
    
    def _record_failure(self, request_start_time: float, error: str):
        """Record failed request."""
        duration = time.time() - request_start_time
        
        self.recent_requests.append({
            "success": False,
            "timestamp": datetime.now(timezone.utc),
            "duration": duration,
            "error": error
        })
        
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        # Check if we should open the circuit
        if (self.state == CircuitBreakerState.CLOSED and 
            self.failure_count >= self.config.failure_threshold):
            self._transition_to_open()
        elif (self.state == CircuitBreakerState.HALF_OPEN and
              self.failure_count >= 1):
            self._transition_to_open()
    
    def _transition_to_closed(self):
        """Transition circuit breaker to closed state."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.state_changed_time = datetime.now(timezone.utc)
        
        self.logger.info(
            "Circuit breaker closed - service recovered",
            channel=self.channel
        )
    
    def _transition_to_open(self):
        """Transition circuit breaker to open state."""
        self.state = CircuitBreakerState.OPEN
        self.state_changed_time = datetime.now(timezone.utc)
        
        self.logger.error(
            "Circuit breaker opened - service failing",
            channel=self.channel,
            failure_count=self.failure_count
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.config.monitoring_window_seconds)
        
        # Calculate recent error rate
        recent_requests = [
            req for req in self.recent_requests
            if req["timestamp"] >= window_start
        ]
        
        total_recent = len(recent_requests)
        failed_recent = sum(1 for req in recent_requests if not req["success"])
        error_rate = failed_recent / total_recent if total_recent > 0 else 0.0
        
        return {
            "channel": self.channel,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "error_rate": error_rate,
            "total_recent_requests": total_recent,
            "failed_recent_requests": failed_recent,
            "state_changed_time": self.state_changed_time.isoformat(),
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class ErrorManager:
    """
    Comprehensive error management for notification delivery.
    
    Features:
    - Circuit breaker pattern per channel
    - Error categorization and severity classification
    - Timeout management with configurable windows
    - Error rate monitoring and alerting
    - Structured error context for troubleshooting
    """
    
    def __init__(
        self,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        default_timeout_seconds: float = 30.0,
        channel_timeouts: Optional[Dict[str, float]] = None,
        error_tracking_window_minutes: int = 60
    ):
        """
        Initialize error manager.
        
        Args:
            circuit_breaker_config: Default circuit breaker configuration
            default_timeout_seconds: Default timeout for operations
            channel_timeouts: Channel-specific timeout configurations
            error_tracking_window_minutes: Window for error rate calculations
        """
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.default_timeout_seconds = default_timeout_seconds
        self.channel_timeouts = channel_timeouts or {}
        self.error_tracking_window = timedelta(minutes=error_tracking_window_minutes)
        
        # Circuit breakers per channel
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Error tracking
        self.error_metrics = ErrorMetrics()
        self.error_history: List[Dict[str, Any]] = []
        
        # Error pattern detection
        self.error_patterns: Dict[str, List[datetime]] = defaultdict(list)
        
        self.logger = logger.bind(service="ErrorManager")
    
    async def execute_with_protection(
        self,
        channel: str,
        operation_name: str,
        func,
        *args,
        timeout_override: Optional[float] = None,
        **kwargs
    ):
        """
        Execute operation with error protection and circuit breaker.
        
        Args:
            channel: Channel name
            operation_name: Description of operation
            func: Function to execute
            *args: Function arguments
            timeout_override: Override default timeout
            **kwargs: Function keyword arguments
            
        Returns:
            Operation result
            
        Raises:
            Various exceptions based on failure type
        """
        # Get or create circuit breaker for channel
        circuit_breaker = self._get_circuit_breaker(channel)
        
        # Determine timeout
        timeout = (timeout_override or 
                  self.channel_timeouts.get(channel, self.default_timeout_seconds))
        
        operation_start = datetime.now(timezone.utc)
        
        try:
            self.logger.debug(
                "Starting protected operation",
                channel=channel,
                operation=operation_name,
                timeout=timeout,
                circuit_state=circuit_breaker.state.value
            )
            
            # Execute with circuit breaker and timeout
            result = await asyncio.wait_for(
                circuit_breaker.call(func, *args, **kwargs),
                timeout=timeout
            )
            
            # Record successful operation
            self._record_operation_success(channel, operation_name, operation_start)
            
            return result
            
        except CircuitBreakerOpenError as e:
            # Circuit breaker prevented execution
            error_context = self._create_error_context(
                channel, operation_name, operation_start,
                error_code="CIRCUIT_BREAKER_OPEN",
                error_message=str(e),
                severity=ErrorSeverity.HIGH
            )
            
            self._record_error(error_context)
            raise
            
        except asyncio.TimeoutError:
            # Operation timeout
            error_context = self._create_error_context(
                channel, operation_name, operation_start,
                error_code="OPERATION_TIMEOUT",
                error_message=f"Operation timed out after {timeout} seconds",
                severity=ErrorSeverity.MEDIUM
            )
            
            self._record_error(error_context)
            raise
            
        except Exception as e:
            # Other errors
            error_severity = self._classify_error_severity(str(e))
            error_context = self._create_error_context(
                channel, operation_name, operation_start,
                error_code=type(e).__name__,
                error_message=str(e),
                severity=error_severity
            )
            
            self._record_error(error_context)
            raise
    
    def _get_circuit_breaker(self, channel: str) -> CircuitBreaker:
        """Get or create circuit breaker for channel."""
        if channel not in self.circuit_breakers:
            self.circuit_breakers[channel] = CircuitBreaker(
                channel, self.circuit_breaker_config
            )
        
        return self.circuit_breakers[channel]
    
    def _create_error_context(
        self,
        channel: str,
        operation: str,
        start_time: datetime,
        error_code: str,
        error_message: str,
        severity: ErrorSeverity
    ) -> Dict[str, Any]:
        """Create structured error context."""
        duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return {
            "timestamp": datetime.now(timezone.utc),
            "channel": channel,
            "operation": operation,
            "error_code": error_code,
            "error_message": error_message,
            "severity": severity.value,
            "duration_ms": duration,
            "start_time": start_time,
            "correlation_id": f"error_{int(time.time() * 1000)}"
        }
    
    def _record_operation_success(
        self,
        channel: str,
        operation: str,
        start_time: datetime
    ):
        """Record successful operation for metrics."""
        duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        self.logger.debug(
            "Operation completed successfully",
            channel=channel,
            operation=operation,
            duration_ms=duration
        )
    
    def _record_error(self, error_context: Dict[str, Any]):
        """Record error for tracking and analysis."""
        # Update error metrics
        self.error_metrics.total_errors += 1
        self.error_metrics.last_error_time = error_context["timestamp"]
        
        if self.error_metrics.first_error_time is None:
            self.error_metrics.first_error_time = error_context["timestamp"]
        
        # Update error counts
        error_code = error_context["error_code"]
        channel = error_context["channel"]
        severity = error_context["severity"]
        
        self.error_metrics.errors_by_code[error_code] = (
            self.error_metrics.errors_by_code.get(error_code, 0) + 1
        )
        self.error_metrics.errors_by_channel[channel] = (
            self.error_metrics.errors_by_channel.get(channel, 0) + 1
        )
        self.error_metrics.errors_by_severity[severity] = (
            self.error_metrics.errors_by_severity.get(severity, 0) + 1
        )
        
        # Add to error history
        self.error_history.append(error_context)
        
        # Track error patterns
        self.error_patterns[error_code].append(error_context["timestamp"])
        
        # Clean up old error patterns
        self._cleanup_old_errors()
        
        # Update error rates
        self._update_error_rates()
        
        # Log error with context
        self.logger.error(
            "Error recorded",
            **error_context
        )
        
        # Check for error patterns that need attention
        self._check_error_patterns(error_code)
    
    def _classify_error_severity(self, error_message: str) -> ErrorSeverity:
        """Classify error severity based on error message."""
        error_lower = error_message.lower()
        
        # Critical errors
        if any(keyword in error_lower for keyword in [
            "authentication", "authorization", "security", "corruption"
        ]):
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if any(keyword in error_lower for keyword in [
            "connection", "network", "database", "service unavailable"
        ]):
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if any(keyword in error_lower for keyword in [
            "timeout", "rate limit", "temporary", "retry"
        ]):
            return ErrorSeverity.MEDIUM
        
        # Default to low severity
        return ErrorSeverity.LOW
    
    def _cleanup_old_errors(self):
        """Remove old errors outside tracking window."""
        cutoff_time = datetime.now(timezone.utc) - self.error_tracking_window
        
        # Clean error history
        self.error_history = [
            error for error in self.error_history
            if error["timestamp"] >= cutoff_time
        ]
        
        # Clean error patterns
        for error_code in list(self.error_patterns.keys()):
            self.error_patterns[error_code] = [
                timestamp for timestamp in self.error_patterns[error_code]
                if timestamp >= cutoff_time
            ]
            
            # Remove empty patterns
            if not self.error_patterns[error_code]:
                del self.error_patterns[error_code]
    
    def _update_error_rates(self):
        """Update error rate calculations."""
        window_start = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        # Count errors in the last minute
        recent_errors = [
            error for error in self.error_history
            if error["timestamp"] >= window_start
        ]
        
        self.error_metrics.error_rate_per_minute = len(recent_errors)
    
    def _check_error_patterns(self, error_code: str):
        """Check for concerning error patterns."""
        if error_code not in self.error_patterns:
            return
        
        recent_errors = self.error_patterns[error_code]
        
        # Check for burst of errors (5+ in 1 minute)
        if len(recent_errors) >= 5:
            one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
            recent_burst = [ts for ts in recent_errors if ts >= one_minute_ago]
            
            if len(recent_burst) >= 5:
                self.logger.warning(
                    "Error burst detected",
                    error_code=error_code,
                    count=len(recent_burst),
                    time_window="1_minute"
                )
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get comprehensive error summary."""
        circuit_breaker_states = {
            channel: breaker.get_metrics()
            for channel, breaker in self.circuit_breakers.items()
        }
        
        return {
            "error_metrics": {
                "total_errors": self.error_metrics.total_errors,
                "errors_by_code": dict(self.error_metrics.errors_by_code),
                "errors_by_channel": dict(self.error_metrics.errors_by_channel),
                "errors_by_severity": dict(self.error_metrics.errors_by_severity),
                "error_rate_per_minute": self.error_metrics.error_rate_per_minute,
                "first_error_time": (
                    self.error_metrics.first_error_time.isoformat()
                    if self.error_metrics.first_error_time else None
                ),
                "last_error_time": (
                    self.error_metrics.last_error_time.isoformat()
                    if self.error_metrics.last_error_time else None
                )
            },
            "circuit_breakers": circuit_breaker_states,
            "recent_errors": [
                error for error in self.error_history[-10:]  # Last 10 errors
            ],
            "error_patterns": {
                code: len(timestamps)
                for code, timestamps in self.error_patterns.items()
            }
        }
    
    def reset_circuit_breaker(self, channel: str) -> bool:
        """Manually reset circuit breaker for a channel."""
        if channel in self.circuit_breakers:
            breaker = self.circuit_breakers[channel]
            breaker._transition_to_closed()
            
            self.logger.info(
                "Circuit breaker manually reset",
                channel=channel
            )
            return True
        
        return False
    
    def get_channel_health(self, channel: str) -> Dict[str, Any]:
        """Get health status for a specific channel."""
        breaker = self.circuit_breakers.get(channel)
        
        if not breaker:
            return {
                "channel": channel,
                "status": "unknown",
                "circuit_breaker": "not_initialized"
            }
        
        return {
            "channel": channel,
            "status": "healthy" if breaker.state == CircuitBreakerState.CLOSED else "unhealthy",
            "circuit_breaker": breaker.get_metrics()
        } 