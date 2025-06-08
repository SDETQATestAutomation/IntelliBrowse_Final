"""
Notification Module - Email Channel Adapter

Email notification delivery via SMTP or SendGrid API.
Supports HTML/plain text content, attachments, and rate limiting.
"""

import smtplib
import asyncio
import re
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, Optional, List
import ssl
import aiosmtplib

from ..services.channel_adapter_base import (
    NotificationChannelAdapter, NotificationPayload, NotificationResult,
    NotificationResultStatus
)
from ...config.logging import get_logger

logger = get_logger(__name__)


class EmailNotificationAdapter(NotificationChannelAdapter):
    """
    Email notification adapter supporting SMTP and SendGrid delivery.
    
    Features:
    - HTML and plain text content support
    - Attachment handling capability
    - Rate limiting and retry logic
    - Comprehensive error handling
    - Support for SMTP and SendGrid providers
    """
    
    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_use_tls: bool = True,
        sendgrid_api_key: Optional[str] = None,
        from_email: str = "noreply@intellibrowse.com",
        from_name: str = "IntelliBrowse",
        provider: str = "smtp",  # "smtp" or "sendgrid"
        rate_limit_per_second: int = 10,
        timeout_seconds: int = 30,
        enabled: bool = True
    ):
        """
        Initialize email notification adapter.
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_username: SMTP authentication username
            smtp_password: SMTP authentication password
            smtp_use_tls: Whether to use TLS encryption
            sendgrid_api_key: SendGrid API key (if using SendGrid)
            from_email: Default sender email address
            from_name: Default sender name
            provider: Email provider ("smtp" or "sendgrid")
            rate_limit_per_second: Maximum emails per second
            timeout_seconds: Timeout for email operations
            enabled: Whether adapter is enabled
        """
        super().__init__()
        
        # Configuration
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.smtp_use_tls = smtp_use_tls
        self.sendgrid_api_key = sendgrid_api_key
        self.from_email = from_email
        self.from_name = from_name
        self.provider = provider
        self.rate_limit_per_second = rate_limit_per_second
        self.timeout_seconds = timeout_seconds
        self._enabled = enabled
        
        # Rate limiting
        self._last_send_time = 0.0
        self._send_count = 0
        
        # Logger
        self.logger = logger.bind(
            adapter="EmailNotificationAdapter",
            provider=provider
        )
        
        # Email validation regex
        self.email_regex = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
    
    async def send(self, payload: NotificationPayload) -> NotificationResult:
        """
        Send email notification.
        
        Args:
            payload: Notification payload with content and recipient data
            
        Returns:
            NotificationResult with delivery status and metadata
        """
        start_time = datetime.now(timezone.utc)
        result = NotificationResult(
            channel="email",
            notification_id=payload.notification_id,
            provider_name=self.provider
        )
        
        try:
            self.logger.info(
                "Starting email delivery",
                notification_id=payload.notification_id,
                recipient_email=payload.recipient_email,
                provider=self.provider
            )
            
            # Validate recipient email
            if not payload.recipient_email or not self._is_valid_email(payload.recipient_email):
                error_msg = f"Invalid recipient email: {payload.recipient_email}"
                self.logger.warning(error_msg)
                result.mark_completed(
                    success=False,
                    status=NotificationResultStatus.INVALID_RECIPIENT,
                    error_code="INVALID_EMAIL",
                    error_message=error_msg
                )
                return result
            
            # Apply rate limiting
            await self._apply_rate_limit()
            
            # Send via configured provider
            if self.provider == "sendgrid":
                provider_response = await self._send_via_sendgrid(payload)
            else:  # smtp
                provider_response = await self._send_via_smtp(payload)
            
            # Process provider response
            if provider_response.get("success", False):
                result.mark_completed(
                    success=True,
                    status=NotificationResultStatus.SUCCESS,
                    provider_message_id=provider_response.get("message_id"),
                    metadata=provider_response.get("metadata", {})
                )
                
                self.logger.info(
                    "Email delivered successfully",
                    notification_id=payload.notification_id,
                    recipient_email=payload.recipient_email,
                    provider_message_id=provider_response.get("message_id"),
                    duration_ms=result.duration_ms
                )
            else:
                result.mark_completed(
                    success=False,
                    status=NotificationResultStatus.FAILURE,
                    error_code=provider_response.get("error_code", "DELIVERY_FAILED"),
                    error_message=provider_response.get("error_message", "Email delivery failed")
                )
                
                self.logger.error(
                    "Email delivery failed",
                    notification_id=payload.notification_id,
                    recipient_email=payload.recipient_email,
                    error_code=result.error_code,
                    error_message=result.error_message
                )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Email adapter error",
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
        Validate recipient data for email delivery.
        
        Args:
            recipient_data: Recipient information
            
        Returns:
            True if recipient data is valid for email delivery
        """
        email = recipient_data.get("email")
        if not email:
            return False
            
        return self._is_valid_email(email)
    
    def is_enabled(self) -> bool:
        """Check if email adapter is enabled."""
        return self._enabled
    
    def get_channel_name(self) -> str:
        """Get channel name."""
        return "email"
    
    async def _send_via_smtp(self, payload: NotificationPayload) -> Dict[str, Any]:
        """
        Send email via SMTP.
        
        Args:
            payload: Notification payload
            
        Returns:
            Dict with success status and metadata
        """
        try:
            # Create message
            message = await self._create_email_message(payload)
            
            # Send via SMTP
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                timeout=self.timeout_seconds
            ) as smtp:
                if self.smtp_use_tls:
                    await smtp.starttls()
                
                if self.smtp_username and self.smtp_password:
                    await smtp.login(self.smtp_username, self.smtp_password)
                
                # Send message
                await smtp.send_message(message)
                
                # Generate message ID (SMTP doesn't always provide one)
                message_id = f"smtp_{payload.notification_id}_{int(datetime.now().timestamp())}"
                
                return {
                    "success": True,
                    "message_id": message_id,
                    "metadata": {
                        "smtp_host": self.smtp_host,
                        "smtp_port": self.smtp_port
                    }
                }
                
        except aiosmtplib.SMTPException as e:
            return {
                "success": False,
                "error_code": "SMTP_ERROR",
                "error_message": f"SMTP error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error_code": "SMTP_EXCEPTION",
                "error_message": f"SMTP exception: {str(e)}"
            }
    
    async def _send_via_sendgrid(self, payload: NotificationPayload) -> Dict[str, Any]:
        """
        Send email via SendGrid API.
        
        Args:
            payload: Notification payload
            
        Returns:
            Dict with success status and metadata
        """
        try:
            # Import SendGrid (optional dependency)
            try:
                import sendgrid
                from sendgrid.helpers.mail import Mail, Email, To, Content
            except ImportError:
                return {
                    "success": False,
                    "error_code": "SENDGRID_NOT_AVAILABLE",
                    "error_message": "SendGrid library not installed"
                }
            
            if not self.sendgrid_api_key:
                return {
                    "success": False,
                    "error_code": "SENDGRID_NO_API_KEY",
                    "error_message": "SendGrid API key not configured"
                }
            
            # Create SendGrid client
            sg = sendgrid.SendGridAPIClient(api_key=self.sendgrid_api_key)
            
            # Create email
            from_email = Email(self.from_email, self.from_name)
            to_email = To(payload.recipient_email, payload.recipient_name)
            subject = payload.title
            
            # Content
            if payload.html_content:
                content = Content("text/html", payload.html_content)
            else:
                content = Content("text/plain", payload.message)
            
            mail = Mail(from_email, to_email, subject, content)
            
            # Add plain text version if HTML is provided
            if payload.html_content and payload.message:
                mail.add_content(Content("text/plain", payload.message))
            
            # Send email
            response = await asyncio.to_thread(sg.send, mail)
            
            # Parse response
            if response.status_code in [200, 201, 202]:
                message_id = response.headers.get('X-Message-Id', f"sg_{payload.notification_id}")
                
                return {
                    "success": True,
                    "message_id": message_id,
                    "metadata": {
                        "sendgrid_status": response.status_code,
                        "sendgrid_headers": dict(response.headers)
                    }
                }
            else:
                return {
                    "success": False,
                    "error_code": f"SENDGRID_HTTP_{response.status_code}",
                    "error_message": f"SendGrid HTTP {response.status_code}: {response.body}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error_code": "SENDGRID_EXCEPTION",
                "error_message": f"SendGrid exception: {str(e)}"
            }
    
    async def _create_email_message(self, payload: NotificationPayload) -> MIMEMultipart:
        """
        Create email message from payload.
        
        Args:
            payload: Notification payload
            
        Returns:
            MIMEMultipart email message
        """
        # Create multipart message
        message = MIMEMultipart("alternative")
        
        # Headers
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message["To"] = payload.recipient_email
        message["Subject"] = payload.title
        message["Message-ID"] = f"<{payload.notification_id}@intellibrowse.com>"
        
        # Add custom headers
        message["X-Notification-ID"] = payload.notification_id
        message["X-Notification-Type"] = payload.type
        message["X-Priority"] = str(self._get_email_priority(payload.priority))
        
        # Content
        if payload.message:
            text_part = MIMEText(payload.message, "plain", "utf-8")
            message.attach(text_part)
        
        if payload.html_content:
            html_part = MIMEText(payload.html_content, "html", "utf-8")
            message.attach(html_part)
        
        return message
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email address format."""
        if not email or not isinstance(email, str):
            return False
        
        return bool(self.email_regex.match(email.strip()))
    
    def _get_email_priority(self, priority: str) -> int:
        """Convert notification priority to email priority."""
        priority_map = {
            "critical": 1,
            "high": 2,
            "medium": 3,
            "low": 4
        }
        return priority_map.get(priority.lower(), 3)
    
    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting to prevent overwhelming email servers."""
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