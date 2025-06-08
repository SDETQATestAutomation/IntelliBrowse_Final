"""
Notification Module - Webhook Channel Adapter

Generic HTTP webhook notification delivery.
Supports configurable authentication, HTTP methods, content types, and retry logic.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
import aiohttp
from urllib.parse import urlparse

from ..services.channel_adapter_base import (
    NotificationChannelAdapter, NotificationPayload, NotificationResult,
    NotificationResultStatus
)
from ...config.logging import get_logger

logger = get_logger(__name__)


class WebhookNotificationAdapter(NotificationChannelAdapter):
    """
    Generic webhook notification adapter for HTTP-based delivery.
    
    Features:
    - Configurable HTTP methods and content types
    - Authentication header support (Bearer, API Key, Custom)
    - Timeout and connection management
    - Retry logic for failed deliveries
    - Response validation and error handling
    - Rate limiting capability
    """
    
    def __init__(
        self,
        default_webhook_url: Optional[str] = None,
        http_method: str = "POST",
        content_type: str = "application/json",
        auth_type: Optional[str] = None,  # "bearer", "api_key", "custom"
        auth_value: Optional[str] = None,
        auth_header: str = "Authorization",
        custom_headers: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 30,
        rate_limit_per_second: int = 20,
        success_status_codes: Optional[List[int]] = None,
        validate_ssl: bool = True,
        enabled: bool = True
    ):
        """
        Initialize webhook notification adapter.
        
        Args:
            default_webhook_url: Default webhook URL if not provided per notification
            http_method: HTTP method to use (POST, PUT, PATCH)
            content_type: Content-Type header value
            auth_type: Authentication type ("bearer", "api_key", "custom")
            auth_value: Authentication value (token, key, etc.)
            auth_header: Header name for authentication
            custom_headers: Additional headers to include
            timeout_seconds: Request timeout
            rate_limit_per_second: Maximum requests per second
            success_status_codes: HTTP status codes considered successful
            validate_ssl: Whether to validate SSL certificates
            enabled: Whether adapter is enabled
        """
        super().__init__()
        
        # Configuration
        self.default_webhook_url = default_webhook_url
        self.http_method = http_method.upper()
        self.content_type = content_type
        self.auth_type = auth_type
        self.auth_value = auth_value
        self.auth_header = auth_header
        self.custom_headers = custom_headers or {}
        self.timeout_seconds = timeout_seconds
        self.rate_limit_per_second = rate_limit_per_second
        self.success_status_codes = success_status_codes or [200, 201, 202, 204]
        self.validate_ssl = validate_ssl
        self._enabled = enabled
        
        # Rate limiting
        self._last_send_time = 0.0
        self._send_count = 0
        
        # Logger
        self.logger = logger.bind(
            adapter="WebhookNotificationAdapter",
            default_url=default_webhook_url[:50] + "..." if default_webhook_url and len(default_webhook_url) > 50 else default_webhook_url
        )
        
        # HTTP session for connection pooling
        self._session = None
        
        # Validate configuration
        if self.http_method not in ["POST", "PUT", "PATCH"]:
            raise ValueError(f"Unsupported HTTP method: {self.http_method}")
    
    async def send(self, payload: NotificationPayload) -> NotificationResult:
        """
        Send webhook notification.
        
        Args:
            payload: Notification payload with content and recipient data
            
        Returns:
            NotificationResult with delivery status and metadata
        """
        start_time = datetime.now(timezone.utc)
        result = NotificationResult(
            channel="webhook",
            notification_id=payload.notification_id,
            provider_name="http_webhook"
        )
        
        try:
            self.logger.info(
                "Starting webhook delivery",
                notification_id=payload.notification_id,
                recipient_id=payload.recipient_id,
                method=self.http_method
            )
            
            # Determine webhook URL
            webhook_url = await self._determine_webhook_url(payload)
            if not webhook_url:
                error_msg = "No webhook URL available for delivery"
                self.logger.warning(error_msg)
                result.mark_completed(
                    success=False,
                    status=NotificationResultStatus.INVALID_RECIPIENT,
                    error_code="NO_WEBHOOK_URL",
                    error_message=error_msg
                )
                return result
            
            # Validate URL
            if not self._is_valid_url(webhook_url):
                error_msg = f"Invalid webhook URL: {webhook_url}"
                self.logger.warning(error_msg)
                result.mark_completed(
                    success=False,
                    status=NotificationResultStatus.INVALID_RECIPIENT,
                    error_code="INVALID_WEBHOOK_URL",
                    error_message=error_msg
                )
                return result
            
            # Apply rate limiting
            await self._apply_rate_limit()
            
            # Create webhook payload
            webhook_payload = await self._create_webhook_payload(payload)
            
            # Create request headers
            headers = await self._create_request_headers()
            
            # Send webhook request
            response_data = await self._send_webhook_request(
                webhook_url, webhook_payload, headers
            )
            
            # Process response
            if response_data.get("success", False):
                result.mark_completed(
                    success=True,
                    status=NotificationResultStatus.SUCCESS,
                    provider_message_id=response_data.get("message_id"),
                    metadata=response_data.get("metadata", {})
                )
                
                self.logger.info(
                    "Webhook delivered successfully",
                    notification_id=payload.notification_id,
                    webhook_url=webhook_url,
                    status_code=response_data.get("status_code"),
                    duration_ms=result.duration_ms
                )
            else:
                result.mark_completed(
                    success=False,
                    status=NotificationResultStatus.FAILURE,
                    error_code=response_data.get("error_code", "DELIVERY_FAILED"),
                    error_message=response_data.get("error_message", "Webhook delivery failed")
                )
                
                self.logger.error(
                    "Webhook delivery failed",
                    notification_id=payload.notification_id,
                    webhook_url=webhook_url,
                    error_code=result.error_code,
                    error_message=result.error_message
                )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Webhook adapter error",
                notification_id=payload.notification_id,
                error=str(e),
                exc_info=True
            )
            
            result.mark_completed(
                success=False,
                status=NotificationResultStatus.FAILURE,
                error_code="ADAPTER_EXCEPTION",
                error_message=str(e)
            )
            return result
    
    async def validate_recipient(self, recipient_data: Dict[str, Any]) -> bool:
        """
        Validate recipient data for webhook delivery.
        
        Args:
            recipient_data: Recipient information
            
        Returns:
            True if recipient data is valid for webhook delivery
        """
        # Check if webhook URL is available
        webhook_url = recipient_data.get("webhook_url")
        if webhook_url:
            return self._is_valid_url(webhook_url)
        
        # If no recipient-specific URL, check if default URL is configured
        if self.default_webhook_url:
            return self._is_valid_url(self.default_webhook_url)
        
        return False
    
    def is_enabled(self) -> bool:
        """Check if webhook adapter is enabled."""
        return self._enabled
    
    def get_channel_name(self) -> str:
        """Get channel name."""
        return "webhook"
    
    async def _determine_webhook_url(self, payload: NotificationPayload) -> Optional[str]:
        """
        Determine webhook URL for delivery.
        
        Args:
            payload: Notification payload
            
        Returns:
            Webhook URL to use for delivery
        """
        # Check payload context for webhook URL
        if payload.context and payload.context.get("webhook_url"):
            return payload.context["webhook_url"]
        
        # Check if recipient has webhook URL (requires recipient data)
        # This would typically be passed in the recipient data during dispatch
        
        # Fall back to default webhook URL
        return self.default_webhook_url
    
    def _is_valid_url(self, url: str) -> bool:
        """
        Validate URL format.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid
        """
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc and parsed.scheme in ["http", "https"])
        except Exception:
            return False
    
    async def _create_webhook_payload(self, payload: NotificationPayload) -> Union[Dict[str, Any], str]:
        """
        Create webhook payload from notification.
        
        Args:
            payload: Notification payload
            
        Returns:
            Formatted payload for webhook delivery
        """
        # Create comprehensive webhook payload
        webhook_data = {
            "notification": {
                "id": payload.notification_id,
                "type": payload.type,
                "priority": payload.priority,
                "title": payload.title,
                "message": payload.message,
                "created_at": payload.created_at.isoformat() if payload.created_at else None,
                "scheduled_at": payload.scheduled_at.isoformat() if payload.scheduled_at else None,
                "expires_at": payload.expires_at.isoformat() if payload.expires_at else None
            },
            "recipient": {
                "id": payload.recipient_id,
                "email": payload.recipient_email,
                "name": payload.recipient_name
            },
            "metadata": {
                "correlation_id": payload.correlation_id,
                "source_service": payload.source_service,
                "context": payload.context or {},
                "delivery_timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        # Add HTML content if available
        if payload.html_content:
            webhook_data["notification"]["html_content"] = payload.html_content
        
        # Return as JSON string or dict based on content type
        if self.content_type == "application/json":
            return webhook_data
        elif self.content_type == "application/x-www-form-urlencoded":
            # Flatten for form encoding
            return {
                "notification_id": payload.notification_id,
                "type": payload.type,
                "priority": payload.priority,
                "title": payload.title,
                "message": payload.message,
                "recipient_id": payload.recipient_id,
                "recipient_email": payload.recipient_email,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            # For other content types, return JSON string
            return json.dumps(webhook_data)
    
    async def _create_request_headers(self) -> Dict[str, str]:
        """
        Create HTTP headers for webhook request.
        
        Returns:
            Dict of headers to include in request
        """
        headers = {
            "Content-Type": self.content_type,
            "User-Agent": "IntelliBrowse-Notification-Service/1.0"
        }
        
        # Add authentication header
        if self.auth_type and self.auth_value:
            if self.auth_type == "bearer":
                headers[self.auth_header] = f"Bearer {self.auth_value}"
            elif self.auth_type == "api_key":
                headers[self.auth_header] = self.auth_value
            elif self.auth_type == "custom":
                headers[self.auth_header] = self.auth_value
        
        # Add custom headers
        headers.update(self.custom_headers)
        
        return headers
    
    async def _send_webhook_request(
        self,
        url: str,
        payload: Union[Dict[str, Any], str],
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Send HTTP webhook request.
        
        Args:
            url: Webhook URL
            payload: Request payload
            headers: Request headers
            
        Returns:
            Dict with success status and metadata
        """
        try:
            # Create HTTP session if not exists
            if not self._session:
                connector = aiohttp.TCPConnector(ssl=self.validate_ssl)
                timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout
                )
            
            # Prepare request data
            if self.content_type == "application/json":
                request_data = {"json": payload}
            elif self.content_type == "application/x-www-form-urlencoded":
                request_data = {"data": payload}
            else:
                request_data = {"data": payload}
            
            # Send request
            async with self._session.request(
                method=self.http_method,
                url=url,
                headers=headers,
                **request_data
            ) as response:
                response_text = await response.text()
                response_headers = dict(response.headers)
                
                # Check if response is successful
                if response.status in self.success_status_codes:
                    # Try to parse response for message ID
                    message_id = None
                    try:
                        response_json = await response.json()
                        message_id = response_json.get("id") or response_json.get("message_id")
                    except:
                        pass
                    
                    if not message_id:
                        message_id = f"webhook_{int(datetime.now().timestamp())}"
                    
                    return {
                        "success": True,
                        "message_id": message_id,
                        "metadata": {
                            "status_code": response.status,
                            "response_headers": response_headers,
                            "response_text": response_text[:500],  # Truncate long responses
                            "webhook_url": url[:100]  # Truncate long URLs
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error_code": f"WEBHOOK_HTTP_{response.status}",
                        "error_message": f"Webhook HTTP {response.status}: {response_text[:200]}"
                    }
                    
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "error_code": "WEBHOOK_CLIENT_ERROR",
                "error_message": f"HTTP client error: {str(e)}"
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error_code": "WEBHOOK_TIMEOUT",
                "error_message": f"Request timeout after {self.timeout_seconds} seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error_code": "WEBHOOK_EXCEPTION",
                "error_message": f"Webhook exception: {str(e)}"
            }
    
    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting to prevent overwhelming webhook endpoints."""
        current_time = asyncio.get_event_loop().time()
        
        # Reset counter every second
        if current_time - self._last_send_time >= 1.0:
            self._send_count = 0
            self._last_send_time = current_time
        
        # Check rate limit
        if self._send_count >= self.rate_limit_per_second:
            sleep_time = 1.0 - (current_time - self._last_send_time)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                self._send_count = 0
                self._last_send_time = asyncio.get_event_loop().time()
        
        self._send_count += 1
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None 