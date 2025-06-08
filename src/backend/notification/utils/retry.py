"""
IntelliBrowse Notification Engine - Retry Utilities

This module provides comprehensive retry logic, exponential backoff, circuit breaker
patterns, and timeout handling for robust notification delivery with failure recovery.

Classes:
    - RetryPolicy: Configurable retry policy with exponential backoff
    - CircuitBreaker: Circuit breaker pattern for external service protection
    - RetryableOperation: Decorator for adding retry logic to async functions
    - DeliveryTimeout: Timeout wrapper for delivery operations

Author: IntelliBrowse Team
Created: Phase 5 - Background Tasks & Delivery Daemon Implementation
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from dataclasses import dataclass
from functools import wraps

from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)

# Type definitions
T = TypeVar('T')
AsyncCallable = Callable[..., Any]


class RetryStrategy(str, Enum):
    """Enumeration of supported retry strategies"""
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIBONACCI_BACKOFF = "fibonacci_backoff"


class CircuitBreakerState(str, Enum):
    """Circuit breaker state enumeration"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryAttempt:
    """Information about a retry attempt"""
    attempt_number: int
    delay_seconds: float
    total_elapsed_seconds: float
    last_exception: Optional[Exception]
    timestamp: datetime


class RetryPolicy(BaseModel):
    """
    Configurable retry policy with multiple backoff strategies
    
    Supports exponential backoff, linear backoff, fibonacci sequences,
    and fixed delays with jitter and maximum retry limits.
    """
    
    max_attempts: int = Field(default=3, ge=1, le=10, description="Maximum number of retry attempts")
    base_delay: float = Field(default=1.0, ge=0.1, le=60.0, description="Base delay in seconds")
    max_delay: float = Field(default=60.0, ge=1.0, le=300.0, description="Maximum delay in seconds")
    strategy: RetryStrategy = Field(default=RetryStrategy.EXPONENTIAL_BACKOFF, description="Retry strategy")
    jitter: bool = Field(default=True, description="Add random jitter to delays")
    jitter_range: float = Field(default=0.1, ge=0.0, le=0.5, description="Jitter range as fraction of delay")
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=5.0, description="Backoff multiplier for exponential strategy")
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a specific attempt number
        
        Args:
            attempt: Attempt number (1-based)
            
        Returns:
            Delay in seconds with applied strategy and jitter
        """
        if attempt <= 0:
            return 0.0
        
        # Calculate base delay using strategy
        if self.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.base_delay * attempt
        elif self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.base_delay * (self.backoff_multiplier ** (attempt - 1))
        elif self.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            delay = self.base_delay * self._fibonacci(attempt)
        else:
            delay = self.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled
        if self.jitter:
            jitter_amount = delay * self.jitter_range
            jitter_offset = random.uniform(-jitter_amount, jitter_amount)
            delay = max(0.1, delay + jitter_offset)
        
        return delay
    
    def _fibonacci(self, n: int) -> int:
        """Calculate fibonacci number for fibonacci backoff strategy"""
        if n <= 1:
            return 1
        elif n == 2:
            return 1
        else:
            a, b = 1, 1
            for _ in range(2, n):
                a, b = b, a + b
            return b
    
    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """
        Determine if operation should be retried based on attempt count and exception
        
        Args:
            attempt: Current attempt number (1-based)
            exception: Exception that occurred
            
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_attempts:
            return False
        
        # Check if exception is retryable
        return self._is_retryable_exception(exception)
    
    def _is_retryable_exception(self, exception: Exception) -> bool:
        """
        Determine if an exception is retryable
        
        Args:
            exception: Exception to check
            
        Returns:
            True if retryable, False otherwise
        """
        # Non-retryable exceptions
        non_retryable = (
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            # Add more non-retryable exceptions as needed
        )
        
        if isinstance(exception, non_retryable):
            return False
        
        # Retryable exceptions (network, temporary failures, etc.)
        retryable = (
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
            OSError,
            # Add more retryable exceptions as needed
        )
        
        return isinstance(exception, retryable) or True  # Default to retryable


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for external service protection
    
    Provides automatic failure detection and recovery for external services,
    preventing cascade failures and allowing graceful degradation.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        name: str = "circuit_breaker"
    ):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before testing service recovery
            expected_exception: Exception type that triggers circuit breaker
            name: Circuit breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        # State tracking
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitBreakerState.CLOSED
        
        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        
        self.logger = logger.bind(circuit_breaker=name)
    
    async def call(self, func: AsyncCallable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenException: If circuit is open
            Original exception: If function fails and circuit remains closed
        """
        self.total_calls += 1
        
        # Check circuit state
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.logger.info("Circuit breaker moving to HALF_OPEN state")
            else:
                self.logger.warning("Circuit breaker is OPEN, rejecting call")
                raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is open")
        
        try:
            # Execute function
            result = await func(*args, **kwargs)
            
            # Success - reset failure count
            self._on_success()
            return result
            
        except self.expected_exception as e:
            # Failure - increment failure count
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful execution"""
        self.total_successes += 1
        self.failure_count = 0
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            self.logger.info("Circuit breaker reset to CLOSED state")
    
    def _on_failure(self):
        """Handle failed execution"""
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures",
                failure_threshold=self.failure_threshold
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "success_rate": self.total_successes / max(self.total_calls, 1)
        }


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class DeliveryTimeout:
    """Timeout wrapper for delivery operations with graceful handling"""
    
    def __init__(self, timeout_seconds: float = 30.0, operation_name: str = "delivery"):
        """
        Initialize timeout wrapper
        
        Args:
            timeout_seconds: Timeout duration in seconds
            operation_name: Operation name for logging
        """
        self.timeout_seconds = timeout_seconds
        self.operation_name = operation_name
        self.logger = logger.bind(operation=operation_name)
    
    async def execute(self, func: AsyncCallable, *args, **kwargs) -> Any:
        """
        Execute function with timeout protection
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            asyncio.TimeoutError: If operation times out
        """
        try:
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            self.logger.warning(
                f"{self.operation_name} operation timed out",
                timeout_seconds=self.timeout_seconds
            )
            raise


def retryable(
    policy: Optional[RetryPolicy] = None,
    circuit_breaker: Optional[CircuitBreaker] = None,
    timeout: Optional[DeliveryTimeout] = None
):
    """
    Decorator for adding retry logic to async functions
    
    Args:
        policy: Retry policy configuration
        circuit_breaker: Circuit breaker for protection
        timeout: Timeout configuration
        
    Returns:
        Decorated function with retry logic
    """
    if policy is None:
        policy = RetryPolicy()
    
    def decorator(func: AsyncCallable) -> AsyncCallable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            attempts: List[RetryAttempt] = []
            start_time = time.time()
            
            for attempt in range(1, policy.max_attempts + 1):
                try:
                    # Apply timeout if configured
                    if timeout:
                        if circuit_breaker:
                            result = await timeout.execute(circuit_breaker.call, func, *args, **kwargs)
                        else:
                            result = await timeout.execute(func, *args, **kwargs)
                    else:
                        if circuit_breaker:
                            result = await circuit_breaker.call(func, *args, **kwargs)
                        else:
                            result = await func(*args, **kwargs)
                    
                    # Success
                    logger.info(
                        f"Operation succeeded on attempt {attempt}",
                        function=func.__name__,
                        attempt=attempt,
                        total_elapsed=time.time() - start_time
                    )
                    return result
                    
                except Exception as e:
                    elapsed_time = time.time() - start_time
                    
                    # Record attempt
                    attempts.append(RetryAttempt(
                        attempt_number=attempt,
                        delay_seconds=0.0,  # Will be calculated for next attempt
                        total_elapsed_seconds=elapsed_time,
                        last_exception=e,
                        timestamp=datetime.utcnow()
                    ))
                    
                    # Check if should retry
                    if not policy.should_retry(attempt, e):
                        logger.error(
                            f"Operation failed permanently after {attempt} attempts",
                            function=func.__name__,
                            attempts=attempt,
                            total_elapsed=elapsed_time,
                            error=str(e)
                        )
                        raise e
                    
                    # Calculate delay for next attempt
                    if attempt < policy.max_attempts:
                        delay = policy.calculate_delay(attempt + 1)
                        attempts[-1].delay_seconds = delay
                        
                        logger.warning(
                            f"Operation failed on attempt {attempt}, retrying in {delay:.2f}s",
                            function=func.__name__,
                            attempt=attempt,
                            delay_seconds=delay,
                            error=str(e)
                        )
                        
                        await asyncio.sleep(delay)
            
            # All attempts exhausted
            last_exception = attempts[-1].last_exception if attempts else Exception("Unknown error")
            logger.error(
                f"Operation failed after all {policy.max_attempts} attempts",
                function=func.__name__,
                max_attempts=policy.max_attempts,
                total_elapsed=time.time() - start_time
            )
            raise last_exception
        
        return wrapper
    return decorator


class RetryableOperation:
    """
    Context manager and utility class for retryable operations
    
    Provides programmatic control over retry logic with comprehensive
    monitoring and error reporting capabilities.
    """
    
    def __init__(
        self,
        operation_name: str,
        policy: Optional[RetryPolicy] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        timeout: Optional[DeliveryTimeout] = None
    ):
        """
        Initialize retryable operation
        
        Args:
            operation_name: Name of operation for logging
            policy: Retry policy configuration
            circuit_breaker: Circuit breaker for protection
            timeout: Timeout configuration
        """
        self.operation_name = operation_name
        self.policy = policy or RetryPolicy()
        self.circuit_breaker = circuit_breaker
        self.timeout = timeout
        self.logger = logger.bind(operation=operation_name)
        
        self.attempts: List[RetryAttempt] = []
        self.start_time: Optional[float] = None
    
    async def execute(self, func: AsyncCallable, *args, **kwargs) -> Any:
        """
        Execute operation with retry logic
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        self.start_time = time.time()
        self.attempts = []
        
        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                # Apply timeout and circuit breaker if configured
                if self.timeout:
                    if self.circuit_breaker:
                        result = await self.timeout.execute(self.circuit_breaker.call, func, *args, **kwargs)
                    else:
                        result = await self.timeout.execute(func, *args, **kwargs)
                else:
                    if self.circuit_breaker:
                        result = await self.circuit_breaker.call(func, *args, **kwargs)
                    else:
                        result = await func(*args, **kwargs)
                
                # Success
                self.logger.info(
                    f"{self.operation_name} succeeded on attempt {attempt}",
                    attempt=attempt,
                    total_elapsed=time.time() - self.start_time
                )
                return result
                
            except Exception as e:
                elapsed_time = time.time() - self.start_time
                
                # Record attempt
                self.attempts.append(RetryAttempt(
                    attempt_number=attempt,
                    delay_seconds=0.0,
                    total_elapsed_seconds=elapsed_time,
                    last_exception=e,
                    timestamp=datetime.utcnow()
                ))
                
                # Check if should retry
                if not self.policy.should_retry(attempt, e):
                    self.logger.error(
                        f"{self.operation_name} failed permanently after {attempt} attempts",
                        attempts=attempt,
                        total_elapsed=elapsed_time,
                        error=str(e)
                    )
                    raise e
                
                # Calculate delay for next attempt
                if attempt < self.policy.max_attempts:
                    delay = self.policy.calculate_delay(attempt + 1)
                    self.attempts[-1].delay_seconds = delay
                    
                    self.logger.warning(
                        f"{self.operation_name} failed on attempt {attempt}, retrying in {delay:.2f}s",
                        attempt=attempt,
                        delay_seconds=delay,
                        error=str(e)
                    )
                    
                    await asyncio.sleep(delay)
        
        # All attempts exhausted
        last_exception = self.attempts[-1].last_exception if self.attempts else Exception("Unknown error")
        self.logger.error(
            f"{self.operation_name} failed after all {self.policy.max_attempts} attempts",
            max_attempts=self.policy.max_attempts,
            total_elapsed=time.time() - self.start_time
        )
        raise last_exception
    
    def get_attempt_history(self) -> List[Dict[str, Any]]:
        """Get history of all retry attempts"""
        return [
            {
                "attempt_number": attempt.attempt_number,
                "delay_seconds": attempt.delay_seconds,
                "total_elapsed_seconds": attempt.total_elapsed_seconds,
                "exception": str(attempt.last_exception) if attempt.last_exception else None,
                "timestamp": attempt.timestamp.isoformat()
            }
            for attempt in self.attempts
        ]


# Predefined retry policies for common scenarios
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF
)

AGGRESSIVE_RETRY_POLICY = RetryPolicy(
    max_attempts=5,
    base_delay=0.5,
    max_delay=60.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    backoff_multiplier=2.5
)

CONSERVATIVE_RETRY_POLICY = RetryPolicy(
    max_attempts=2,
    base_delay=2.0,
    max_delay=10.0,
    strategy=RetryStrategy.LINEAR_BACKOFF
)

EMAIL_DELIVERY_RETRY_POLICY = RetryPolicy(
    max_attempts=4,
    base_delay=2.0,
    max_delay=120.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    backoff_multiplier=3.0
)

WEBHOOK_DELIVERY_RETRY_POLICY = RetryPolicy(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    backoff_multiplier=2.0
) 