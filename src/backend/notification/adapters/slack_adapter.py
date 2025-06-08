"""
Notification Module - Slack Channel Adapter

Slack notification delivery via webhook API.
Supports rich message formatting, channels, direct messages, and rate limiting.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import aiohttp

from ..services.channel_adapter_base import (
    NotificationChannelAdapter, NotificationPayload, NotificationResult,
    NotificationResultStatus
)
from ...config.logging import get_logger

logger = get_logger(__name__)


class SlackNotificationAdapter(NotificationChannelAdapter):
    """
    Slack notification adapter using webhook integration.
    
    Features:
    - Webhook-based message delivery
    - Channel and direct message support
    - Rich message formatting (blocks, attachments)
    - Error handling for invalid channels/users
    - Rate limiting compliance with Slack API
    - Comprehensive logging and result tracking
    """
    
    def __init__(
        self,
        webhook_url: str,
        default_channel: Optional[str] = None,
        bot_name: str = "IntelliBrowse Bot",
        bot_icon: Optional[str] = None,
        rate_limit_per_minute: int = 50,  # Slack webhook rate limit
        timeout_seconds: int = 30,
        enabled: bool = True
    ):
        """
        Initialize Slack notification adapter.
        
        Args:
            webhook_url: Slack webhook URL for message delivery
            default_channel: Default channel for notifications
            bot_name: Bot display name in Slack
            bot_icon: Bot icon emoji or URL
            rate_limit_per_minute: Maximum messages per minute
            timeout_seconds: Timeout for HTTP requests
            enabled: Whether adapter is enabled
        """
        super().__init__()
        
        # Configuration
        self.webhook_url = webhook_url
        self.default_channel = default_channel
        self.bot_name = bot_name
        self.bot_icon = bot_icon
        self.rate_limit_per_minute = rate_limit_per_minute
        self.timeout_seconds = timeout_seconds
        self._enabled = enabled
        
        # Rate limiting
        self._send_times = []
        
        # Logger
        self.logger = logger.bind(
            adapter="SlackNotificationAdapter",
            webhook_url=webhook_url[:50] + "..." if len(webhook_url) > 50 else webhook_url
        )
        
        # HTTP session for connection pooling
        self._session = None
    
    async def send(self, payload: NotificationPayload) -> NotificationResult:
        """
        Send Slack notification.
        
        Args:
            payload: Notification payload with content and recipient data
            
        Returns:
            NotificationResult with delivery status and metadata
        """
        start_time = datetime.now(timezone.utc)
        result = NotificationResult(
            channel="slack",
            notification_id=payload.notification_id,
            provider_name="slack_webhook"
        )
        
        try:
            self.logger.info(
                "Starting Slack delivery",
                notification_id=payload.notification_id,
                recipient_id=payload.recipient_id
            )
            
            # Apply rate limiting
            await self._apply_rate_limit()
            
            # Create Slack message
            slack_message = await self._create_slack_message(payload)
            
            # Validate message
            if not slack_message:
                error_msg = "Failed to create valid Slack message"
                self.logger.warning(error_msg)
                result.mark_completed(
                    success=False,
                    status=NotificationResultStatus.INVALID_PAYLOAD,
                    error_code="INVALID_MESSAGE",
                    error_message=error_msg
                )
                return result
            
            # Send message via webhook
            response_data = await self._send_webhook_message(slack_message)
            
            # Process response
            if response_data.get("success", False):
                result.mark_completed(
                    success=True,
                    status=NotificationResultStatus.SUCCESS,
                    provider_message_id=response_data.get("message_id"),
                    metadata=response_data.get("metadata", {})
                )
                
                self.logger.info(
                    "Slack message delivered successfully",
                    notification_id=payload.notification_id,
                    duration_ms=result.duration_ms
                )
            else:
                result.mark_completed(
                    success=False,
                    status=NotificationResultStatus.FAILURE,
                    error_code=response_data.get("error_code", "DELIVERY_FAILED"),
                    error_message=response_data.get("error_message", "Slack delivery failed")
                )
                
                self.logger.error(
                    "Slack delivery failed",
                    notification_id=payload.notification_id,
                    error_code=result.error_code,
                    error_message=result.error_message
                )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Slack adapter error",
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
        Validate recipient data for Slack delivery.
        
        Args:
            recipient_data: Recipient information
            
        Returns:
            True if recipient data is valid for Slack delivery
        """
        # For webhook delivery, we need at least a user_id or email
        user_id = recipient_data.get("user_id")
        email = recipient_data.get("email")
        
        return bool(user_id or email)
    
    def is_enabled(self) -> bool:
        """Check if Slack adapter is enabled."""
        return self._enabled and bool(self.webhook_url)
    
    def get_channel_name(self) -> str:
        """Get channel name."""
        return "slack"
    
    async def _create_slack_message(self, payload: NotificationPayload) -> Dict[str, Any]:
        """
        Create Slack message payload from notification.
        
        Args:
            payload: Notification payload
            
        Returns:
            Dict containing Slack message payload
        """
        # Base message structure
        message = {
            "username": self.bot_name,
            "text": payload.title,  # Fallback text
        }
        
        # Add bot icon
        if self.bot_icon:
            if self.bot_icon.startswith("http"):
                message["icon_url"] = self.bot_icon
            else:
                message["icon_emoji"] = self.bot_icon
        
        # Determine channel
        channel = await self._determine_channel(payload)
        if channel:
            message["channel"] = channel
        
        # Create rich message blocks
        blocks = await self._create_message_blocks(payload)
        if blocks:
            message["blocks"] = blocks
        
        # Add attachments for additional context
        attachments = await self._create_attachments(payload)
        if attachments:
            message["attachments"] = attachments
        
        return message
    
    async def _determine_channel(self, payload: NotificationPayload) -> Optional[str]:
        """
        Determine target Slack channel for notification.
        
        Args:
            payload: Notification payload
            
        Returns:
            Channel name or user ID, or None for default
        """
        # Check if recipient has Slack-specific data
        if hasattr(payload, 'context') and payload.context:
            slack_channel = payload.context.get('slack_channel')
            if slack_channel:
                return slack_channel
        
        # Use default channel if configured
        if self.default_channel:
            return self.default_channel
        
        # For direct messages, use user email or ID
        if payload.recipient_email:
            return f"@{payload.recipient_email}"
        
        return None
    
    async def _create_message_blocks(self, payload: NotificationPayload) -> List[Dict[str, Any]]:
        """
        Create Slack blocks for rich message formatting.
        
        Args:
            payload: Notification payload
            
        Returns:
            List of Slack block elements
        """
        blocks = []
        
        # Header block with title
        if payload.title:
            blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": payload.title[:150],  # Slack limit
                    "emoji": True
                }
            })
        
        # Main content block
        if payload.message:
            # Split long messages into multiple blocks
            message_text = payload.message
            if len(message_text) > 3000:  # Slack block text limit
                message_text = message_text[:2997] + "..."
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message_text
                }
            })
        
        # Context block with metadata
        context_elements = []
        
        if payload.type:
            context_elements.append({
                "type": "mrkdwn",
                "text": f"*Type:* {payload.type}"
            })
        
        if payload.priority:
            priority_emoji = self._get_priority_emoji(payload.priority)
            context_elements.append({
                "type": "mrkdwn",
                "text": f"*Priority:* {priority_emoji} {payload.priority.title()}"
            })
        
        if payload.source_service:
            context_elements.append({
                "type": "mrkdwn",
                "text": f"*Source:* {payload.source_service}"
            })
        
        if context_elements:
            blocks.append({
                "type": "context",
                "elements": context_elements
            })
        
        # Add divider if we have multiple blocks
        if len(blocks) > 1:
            blocks.insert(-1, {"type": "divider"})
        
        return blocks
    
    async def _create_attachments(self, payload: NotificationPayload) -> List[Dict[str, Any]]:
        """
        Create Slack attachments for additional context.
        
        Args:
            payload: Notification payload
            
        Returns:
            List of Slack attachment objects
        """
        attachments = []
        
        # Color coding based on priority
        color = self._get_priority_color(payload.priority)
        
        # Create attachment with additional fields
        attachment = {
            "color": color,
            "fields": [],
            "footer": "IntelliBrowse Notification System",
            "ts": int(payload.created_at.timestamp()) if payload.created_at else int(datetime.now().timestamp())
        }
        
        # Add notification ID field
        attachment["fields"].append({
            "title": "Notification ID",
            "value": payload.notification_id,
            "short": True
        })
        
        # Add correlation ID if present
        if payload.correlation_id:
            attachment["fields"].append({
                "title": "Correlation ID",
                "value": payload.correlation_id,
                "short": True
            })
        
        # Add context fields
        if payload.context:
            for key, value in payload.context.items():
                if key.startswith('slack_'):
                    continue  # Skip Slack-specific context
                
                if len(attachment["fields"]) < 10:  # Slack limit
                    attachment["fields"].append({
                        "title": key.replace('_', ' ').title(),
                        "value": str(value)[:500],  # Truncate long values
                        "short": len(str(value)) < 50
                    })
        
        if attachment["fields"]:
            attachments.append(attachment)
        
        return attachments
    
    def _get_priority_emoji(self, priority: str) -> str:
        """Get emoji for notification priority."""
        priority_emojis = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "ℹ️",
            "low": "📝"
        }
        return priority_emojis.get(priority.lower(), "📝")
    
    def _get_priority_color(self, priority: str) -> str:
        """Get color code for notification priority."""
        priority_colors = {
            "critical": "#FF0000",  # Red
            "high": "#FF9900",      # Orange
            "medium": "#36A64F",    # Green
            "low": "#808080"        # Gray
        }
        return priority_colors.get(priority.lower(), "#808080")
    
    async def _send_webhook_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send message via Slack webhook.
        
        Args:
            message: Slack message payload
            
        Returns:
            Dict with success status and metadata
        """
        try:
            # Create HTTP session if not exists
            if not self._session:
                timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
                self._session = aiohttp.ClientSession(timeout=timeout)
            
            # Send webhook request
            async with self._session.post(
                self.webhook_url,
                json=message,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "IntelliBrowse-Notification-Service"
                }
            ) as response:
                response_text = await response.text()
                
                # Slack webhook returns "ok" for success
                if response.status == 200 and response_text.strip() == "ok":
                    # Generate message ID (webhooks don't provide one)
                    message_id = f"slack_{int(datetime.now().timestamp())}"
                    
                    return {
                        "success": True,
                        "message_id": message_id,
                        "metadata": {
                            "slack_status": response.status,
                            "slack_response": response_text
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error_code": f"SLACK_HTTP_{response.status}",
                        "error_message": f"Slack webhook error: {response_text}"
                    }
                    
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "error_code": "SLACK_CLIENT_ERROR",
                "error_message": f"HTTP client error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error_code": "SLACK_EXCEPTION",
                "error_message": f"Slack webhook exception: {str(e)}"
            }
    
    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting to comply with Slack API limits."""
        current_time = datetime.now()
        
        # Remove sends older than 1 minute
        cutoff_time = current_time.timestamp() - 60
        self._send_times = [
            send_time for send_time in self._send_times 
            if send_time > cutoff_time
        ]
        
        # Check if we're at the rate limit
        if len(self._send_times) >= self.rate_limit_per_minute:
            # Calculate sleep time to next available slot
            oldest_send = min(self._send_times)
            sleep_time = 60 - (current_time.timestamp() - oldest_send)
            
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                # Remove the oldest send after waiting
                self._send_times.remove(oldest_send)
        
        # Record this send
        self._send_times.append(current_time.timestamp())
    
    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None 