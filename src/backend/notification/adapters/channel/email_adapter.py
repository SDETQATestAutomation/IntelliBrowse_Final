"""
IntelliBrowse Notification Engine - Email Channel Adapter

This module implements the email notification delivery channel using SMTP,
providing robust email delivery with support for HTML content, attachments,
and comprehensive error handling with retry logic.

Classes:
    - EmailAdapter: SMTP-based email delivery adapter
    - EmailConfig: Email-specific configuration
    - SMTPConnectionManager: SMTP connection management

Author: IntelliBrowse Team
Created: Phase 5 - Background Tasks & Delivery Daemon Implementation
"""

import asyncio
import logging
import smtplib
import ssl
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Any
import aiosmtplib

from pydantic import BaseModel, Field, EmailStr, validator

from .base_adapter import (
    BaseChannelAdapter,
    ChannelConfig,
    ChannelType,
    DeliveryContext,
    AdapterCapabilities,
    DeliveryPriority
)
from ...services.delivery_task_service import DeliveryResult, DeliveryResultStatus

# Configure logging
logger = logging.getLogger(__name__)


class EmailConfig(ChannelConfig):
    """
    Email-specific configuration extending base channel config
    
    Provides comprehensive SMTP configuration options for email delivery
    with support for authentication, encryption, and delivery preferences.
    """
    
    channel_type: ChannelType = Field(default=ChannelType.EMAIL, description="Channel type")
    
    # SMTP Server configuration
    smtp_host: str = Field(..., description="SMTP server hostname")
    smtp_port: int = Field(default=587, description="SMTP server port")
    use_tls: bool = Field(default=True, description="Use TLS encryption")
    use_ssl: bool = Field(default=False, description="Use SSL encryption")
    
    # Authentication
    username: Optional[str] = Field(None, description="SMTP username")
    password: Optional[str] = Field(None, description="SMTP password")
    
    # Default sender information
    default_from_email: EmailStr = Field(..., description="Default sender email address")
    default_from_name: Optional[str] = Field(None, description="Default sender name")
    
    # Email formatting
    support_html: bool = Field(default=True, description="Support HTML email content")
    support_attachments: bool = Field(default=True, description="Support email attachments")
    
    # Content limits
    max_recipients: int = Field(default=100, description="Maximum recipients per email")
    max_attachment_size_mb: float = Field(default=25.0, description="Maximum attachment size in MB")
    
    # Connection management
    connection_pool_size: int = Field(default=5, description="SMTP connection pool size")
    connection_timeout: float = Field(default=30.0, description="SMTP connection timeout")
    read_timeout: float = Field(default=60.0, description="SMTP read timeout")
    
    @validator('smtp_port')
    def validate_smtp_port(cls, v):
        """Validate SMTP port range"""
        if not 1 <= v <= 65535:
            raise ValueError('SMTP port must be between 1 and 65535')
        return v
    
    @validator('use_tls', 'use_ssl')
    def validate_encryption(cls, v, values):
        """Validate TLS/SSL configuration"""
        if values.get('use_tls') and values.get('use_ssl'):
            raise ValueError('Cannot use both TLS and SSL simultaneously')
        return v


class SMTPConnectionManager:
    """
    SMTP connection manager with connection pooling and health monitoring
    
    Manages SMTP connections efficiently with automatic reconnection,
    health checking, and graceful error handling.
    """
    
    def __init__(self, config: EmailConfig):
        """
        Initialize SMTP connection manager
        
        Args:
            config: Email configuration
        """
        self.config = config
        self.logger = logger.bind(component="SMTPConnectionManager")
        
        # Connection state
        self._connection: Optional[aiosmtplib.SMTP] = None
        self._connection_lock = asyncio.Lock()
        self._last_connection_attempt = None
        self._connection_failures = 0
        self._max_connection_failures = 3
    
    async def get_connection(self) -> aiosmtplib.SMTP:
        """
        Get an active SMTP connection
        
        Returns:
            Active SMTP connection
            
        Raises:
            ConnectionError: If connection cannot be established
        """
        async with self._connection_lock:
            if self._connection is None or not self._connection.is_connected:
                await self._establish_connection()
            
            return self._connection
    
    async def _establish_connection(self):
        """Establish SMTP connection with retry logic"""
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                self.logger.info(
                    f"Establishing SMTP connection (attempt {attempt})",
                    host=self.config.smtp_host,
                    port=self.config.smtp_port
                )
                
                # Create SMTP connection
                self._connection = aiosmtplib.SMTP(
                    hostname=self.config.smtp_host,
                    port=self.config.smtp_port,
                    timeout=self.config.connection_timeout
                )
                
                # Connect and start TLS if required
                await self._connection.connect()
                
                if self.config.use_tls:
                    await self._connection.starttls()
                
                # Authenticate if credentials provided
                if self.config.username and self.config.password:
                    await self._connection.login(
                        self.config.username,
                        self.config.password
                    )
                
                # Test connection
                await self._connection.noop()
                
                self.logger.info("SMTP connection established successfully")
                self._connection_failures = 0
                self._last_connection_attempt = datetime.now(timezone.utc)
                return
                
            except Exception as e:
                self.logger.warning(
                    f"SMTP connection attempt {attempt} failed",
                    error=str(e),
                    host=self.config.smtp_host,
                    port=self.config.smtp_port
                )
                
                if self._connection:
                    try:
                        await self._connection.quit()
                    except:
                        pass
                    self._connection = None
                
                self._connection_failures += 1
                
                if attempt < max_attempts:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        raise ConnectionError(f"Failed to establish SMTP connection after {max_attempts} attempts")
    
    async def health_check(self) -> bool:
        """
        Perform health check on SMTP connection
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            if self._connection is None or not self._connection.is_connected:
                return False
            
            # Send NOOP command to test connection
            await self._connection.noop()
            return True
            
        except Exception as e:
            self.logger.warning("SMTP health check failed", error=str(e))
            return False
    
    async def close(self):
        """Close SMTP connection"""
        if self._connection:
            try:
                await self._connection.quit()
                self.logger.info("SMTP connection closed")
            except Exception as e:
                self.logger.warning("Error closing SMTP connection", error=str(e))
            finally:
                self._connection = None


class EmailAdapter(BaseChannelAdapter):
    """
    Email notification delivery adapter using SMTP
    
    Provides comprehensive email delivery functionality with support for
    HTML content, attachments, personalization, and robust error handling.
    """
    
    def __init__(self, config: EmailConfig):
        """
        Initialize email adapter
        
        Args:
            config: Email configuration
        """
        super().__init__(config)
        self.email_config = config
        self.connection_manager = SMTPConnectionManager(config)
        
        # Adapter state
        self._capabilities = AdapterCapabilities(
            supports_rich_content=config.support_html,
            supports_attachments=config.support_attachments,
            supports_templates=True,
            supports_scheduling=False,  # Handled by delivery daemon
            supports_batching=True,
            supports_personalization=True,
            supports_delivery_tracking=False,  # Basic SMTP doesn't provide tracking
            supports_read_receipts=False,
            supports_engagement_tracking=False,
            max_content_length=1000000,  # 1MB content limit
            max_subject_length=255,
            max_attachment_size_mb=config.max_attachment_size_mb,
            supported_content_types=["text/plain", "text/html"],
            rate_limit_info={}
        )
    
    @property
    def channel_type(self) -> ChannelType:
        """Get channel type"""
        return ChannelType.EMAIL
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        """Get adapter capabilities"""
        return self._capabilities
    
    async def initialize(self) -> bool:
        """
        Initialize email adapter and test SMTP connection
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.info("Initializing email adapter")
            
            # Test SMTP connection
            connection = await self.connection_manager.get_connection()
            health_ok = await self.connection_manager.health_check()
            
            if health_ok:
                self._is_initialized = True
                self.logger.info("Email adapter initialized successfully")
                return True
            else:
                self.logger.error("Email adapter initialization failed - health check failed")
                return False
                
        except Exception as e:
            self.logger.error(
                "Email adapter initialization failed",
                error=str(e),
                exc_info=True
            )
            return False
    
    async def send(self, context: DeliveryContext) -> DeliveryResult:
        """
        Send email notification
        
        Args:
            context: Delivery context containing notification and user information
            
        Returns:
            Delivery result with status and metadata
        """
        start_time = time.time()
        
        try:
            # Validate delivery context
            is_valid, error_message = await self.validate_delivery_context(context)
            if not is_valid:
                processing_time = (time.time() - start_time) * 1000
                self._update_metrics(False)
                return self._create_delivery_result(
                    context=context,
                    status=DeliveryResultStatus.FAILED,
                    success=False,
                    processing_time_ms=processing_time,
                    error_message=error_message,
                    error_code="VALIDATION_ERROR"
                )
            
            # Prepare email content
            email_content = await self.prepare_content(
                context.notification,
                context.user_context
            )
            
            # Create email message
            message = await self._create_email_message(context, email_content)
            
            # Send email
            connection = await self.connection_manager.get_connection()
            
            recipients = [context.user_context.email]
            await connection.send_message(message)
            
            processing_time = (time.time() - start_time) * 1000
            self._update_metrics(True)
            
            self.logger.info(
                "Email sent successfully",
                notification_id=context.notification_id,
                user_id=context.user_id,
                recipient=context.user_context.email,
                processing_time_ms=processing_time
            )
            
            return self._create_delivery_result(
                context=context,
                status=DeliveryResultStatus.SUCCESS,
                success=True,
                processing_time_ms=processing_time,
                external_id=f"email_{context.notification_id}_{int(time.time())}",
                response_data={
                    "recipient": context.user_context.email,
                    "subject": email_content.get("subject"),
                    "smtp_host": self.email_config.smtp_host
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self._update_metrics(False)
            
            self.logger.error(
                "Email delivery failed",
                notification_id=context.notification_id,
                user_id=context.user_id,
                error=str(e),
                exc_info=True
            )
            
            return self._create_delivery_result(
                context=context,
                status=DeliveryResultStatus.FAILED,
                success=False,
                processing_time_ms=processing_time,
                error_message=str(e),
                error_code="SMTP_ERROR"
            )
    
    async def _create_email_message(
        self,
        context: DeliveryContext,
        email_content: Dict[str, Any]
    ) -> MIMEMultipart:
        """
        Create email message from context and content
        
        Args:
            context: Delivery context
            email_content: Prepared email content
            
        Returns:
            Email message ready for sending
        """
        # Create message
        message = MIMEMultipart('alternative')
        
        # Set headers
        message['Subject'] = email_content.get('subject', context.notification.title)
        message['From'] = f"{self.email_config.default_from_name or 'IntelliBrowse'} <{self.email_config.default_from_email}>"
        message['To'] = context.user_context.email
        message['Message-ID'] = f"<{context.notification_id}@intellibrowse.local>"
        message['Date'] = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')
        
        # Add custom headers for tracking
        message['X-Notification-ID'] = context.notification_id
        message['X-User-ID'] = context.user_id
        message['X-Correlation-ID'] = context.correlation_id
        
        # Create text content
        text_content = email_content.get('content', context.notification.content)
        text_part = MIMEText(text_content, 'plain', 'utf-8')
        message.attach(text_part)
        
        # Create HTML content if supported
        if self.email_config.support_html and email_content.get('html_content'):
            html_content = email_content['html_content']
            html_part = MIMEText(html_content, 'html', 'utf-8')
            message.attach(html_part)
        elif self.email_config.support_html:
            # Convert text to basic HTML
            html_content = f"""
            <html>
                <head>
                    <meta charset="utf-8">
                    <title>{email_content.get('subject', context.notification.title)}</title>
                </head>
                <body>
                    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <h2>{context.notification.title}</h2>
                        <div>{text_content.replace(chr(10), '<br>')}</div>
                        <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;">
                        <p style="font-size: 12px; color: #666;">
                            This is an automated notification from IntelliBrowse.
                        </p>
                    </div>
                </body>
            </html>
            """
            html_part = MIMEText(html_content, 'html', 'utf-8')
            message.attach(html_part)
        
        return message
    
    async def prepare_content(
        self,
        notification: "NotificationModel",
        user_context: "UserContext"
    ) -> Dict[str, Any]:
        """
        Prepare email content with personalization
        
        Args:
            notification: Notification to prepare
            user_context: User context for personalization
            
        Returns:
            Prepared email content
        """
        # Basic content preparation
        content = await super().prepare_content(notification, user_context)
        
        # Email-specific personalization
        personalized_content = content['content']
        personalized_subject = content['subject']
        
        # Replace personalization placeholders
        replacements = {
            '{user_name}': user_context.full_name or user_context.username,
            '{user_email}': user_context.email,
            '{notification_title}': notification.title,
            '{user_id}': user_context.user_id
        }
        
        for placeholder, value in replacements.items():
            personalized_content = personalized_content.replace(placeholder, str(value))
            personalized_subject = personalized_subject.replace(placeholder, str(value))
        
        content.update({
            'subject': personalized_subject,
            'content': personalized_content,
            'recipient_email': user_context.email,
            'recipient_name': user_context.full_name or user_context.username
        })
        
        return content
    
    async def health_check(self) -> bool:
        """
        Perform health check on email adapter
        
        Returns:
            True if adapter is healthy, False otherwise
        """
        try:
            if not self._is_initialized:
                return False
            
            # Check SMTP connection health
            health_ok = await self.connection_manager.health_check()
            
            if health_ok:
                self._last_health_check = datetime.now(timezone.utc)
                return True
            else:
                self.logger.warning("Email adapter health check failed - SMTP connection unhealthy")
                return False
                
        except Exception as e:
            self.logger.error(
                "Email adapter health check failed",
                error=str(e),
                exc_info=True
            )
            return False
    
    async def shutdown(self):
        """Shutdown email adapter and close connections"""
        self.logger.info("Shutting down email adapter")
        
        try:
            await self.connection_manager.close()
        except Exception as e:
            self.logger.warning("Error during email adapter shutdown", error=str(e))
        
        await super().shutdown()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get email adapter metrics"""
        base_metrics = super().get_metrics()
        
        email_metrics = {
            "smtp_host": self.email_config.smtp_host,
            "smtp_port": self.email_config.smtp_port,
            "use_tls": self.email_config.use_tls,
            "support_html": self.email_config.support_html,
            "support_attachments": self.email_config.support_attachments,
            "max_recipients": self.email_config.max_recipients,
            "connection_failures": self.connection_manager._connection_failures
        }
        
        base_metrics.update(email_metrics)
        return base_metrics 