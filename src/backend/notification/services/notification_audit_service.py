"""
IntelliBrowse Notification Engine - Audit & Compliance Service

This module provides comprehensive audit trail management, security compliance,
and data protection capabilities for the notification system with GDPR support
and sensitive data masking.

Classes:
    - NotificationAuditService: Core audit and compliance service
    - DataMaskingEngine: Sensitive data identification and masking
    - ComplianceReporter: Compliance reporting and data retention
    - SecurityEventDetector: Security event detection and alerting

Author: IntelliBrowse Team
Created: Phase 3 - Security & Compliance Implementation
"""

import logging
import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Pattern
from enum import Enum

from bson import ObjectId
from pydantic import BaseModel, Field
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from ..schemas.audit_schemas import (
    AuditLogEntry,
    SecurityEvent,
    ComplianceReport,
    DataRetentionPolicy,
    MaskingConfiguration
)

# Configure logging
logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Audit event types for comprehensive tracking"""
    NOTIFICATION_SENT = "notification_sent"
    NOTIFICATION_FAILED = "notification_failed"
    PREFERENCE_CHANGED = "preference_changed"
    USER_OPTED_OUT = "user_opted_out"
    USER_OPTED_IN = "user_opted_in"
    DATA_ACCESSED = "data_accessed"
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"
    SECURITY_VIOLATION = "security_violation"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class SecurityEventSeverity(str, Enum):
    """Security event severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DataMaskingEngine:
    """
    Engine for identifying and masking sensitive data in audit logs
    
    Provides configurable patterns for detecting sensitive information
    and applying appropriate masking strategies for compliance.
    """
    
    def __init__(self):
        """Initialize masking engine with default patterns"""
        self.sensitive_patterns: Dict[str, Pattern] = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'\b\d{3}-?\d{3}-?\d{4}\b'),
            'ssn': re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
            'credit_card': re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
            'ip_address': re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
            'api_key': re.compile(r'(?i)(api[_-]?key|token|secret)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?'),
            'password': re.compile(r'(?i)(password|pwd)["\']?\s*[:=]\s*["\']?([^\s"\']{8,})["\']?'),
            'webhook_secret': re.compile(r'(?i)(webhook[_-]?secret|secret)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]{16,})["\']?')
        }
        
        self.masking_strategies = {
            'partial': self._partial_mask,
            'hash': self._hash_mask,
            'redact': self._redact_mask,
            'preserve_format': self._preserve_format_mask
        }
        
        logger.debug("DataMaskingEngine initialized with default patterns")
    
    def mask_sensitive_data(
        self,
        data: Any,
        masking_config: Optional[MaskingConfiguration] = None
    ) -> Any:
        """
        Mask sensitive data based on configuration
        
        Args:
            data: Data to mask (string, dict, list, or primitive)
            masking_config: Optional masking configuration
            
        Returns:
            Data with sensitive information masked
        """
        if isinstance(data, str):
            return self._mask_string(data, masking_config)
        elif isinstance(data, dict):
            return self._mask_dict(data, masking_config)
        elif isinstance(data, list):
            return [self.mask_sensitive_data(item, masking_config) for item in data]
        else:
            return data
    
    def _mask_string(self, text: str, config: Optional[MaskingConfiguration]) -> str:
        """Mask sensitive patterns in a string"""
        masked_text = text
        
        for pattern_name, pattern in self.sensitive_patterns.items():
            strategy = 'partial'  # Default strategy
            if config and pattern_name in config.pattern_strategies:
                strategy = config.pattern_strategies[pattern_name]
            
            masking_func = self.masking_strategies.get(strategy, self._partial_mask)
            
            def replace_match(match):
                return masking_func(match.group(0), pattern_name)
            
            masked_text = pattern.sub(replace_match, masked_text)
        
        return masked_text
    
    def _mask_dict(self, data: Dict[str, Any], config: Optional[MaskingConfiguration]) -> Dict[str, Any]:
        """Mask sensitive data in dictionary"""
        masked = {}
        sensitive_keys = {
            'password', 'api_key', 'secret', 'token', 'webhook_secret',
            'auth_token', 'private_key', 'ssn', 'credit_card', 'phone',
            'email', 'personal_info'
        }
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key indicates sensitive data
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                if isinstance(value, str) and len(value) > 0:
                    masked[key] = "[REDACTED]"
                else:
                    masked[key] = value
            else:
                masked[key] = self.mask_sensitive_data(value, config)
        
        return masked
    
    def _partial_mask(self, value: str, pattern_name: str) -> str:
        """Partially mask value showing first and last characters"""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
    
    def _hash_mask(self, value: str, pattern_name: str) -> str:
        """Replace value with SHA-256 hash"""
        return f"[HASH:{hashlib.sha256(value.encode()).hexdigest()[:16]}]"
    
    def _redact_mask(self, value: str, pattern_name: str) -> str:
        """Completely redact the value"""
        return "[REDACTED]"
    
    def _preserve_format_mask(self, value: str, pattern_name: str) -> str:
        """Mask while preserving format (for things like phone numbers)"""
        if pattern_name == 'phone':
            return re.sub(r'\d', '*', value)
        elif pattern_name == 'credit_card':
            return re.sub(r'\d', '*', value[:-4]) + value[-4:]
        else:
            return self._partial_mask(value, pattern_name)


class ComplianceReporter:
    """
    Compliance reporting and data retention management
    
    Provides GDPR, CCPA, and other compliance reporting capabilities
    with configurable data retention policies and automated cleanup.
    """
    
    def __init__(self, collection: Collection):
        """Initialize compliance reporter with audit collection"""
        self.collection = collection
        logger.debug("ComplianceReporter initialized")
    
    async def generate_compliance_report(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        report_type: str = "gdpr"
    ) -> ComplianceReport:
        """
        Generate compliance report for auditing purposes
        
        Args:
            user_id: Specific user ID for user-focused reports
            start_date: Report start date
            end_date: Report end date
            report_type: Type of compliance report (gdpr, ccpa, etc.)
            
        Returns:
            Comprehensive compliance report
        """
        try:
            # Build query
            query = {}
            if user_id:
                query["user_id"] = user_id
            
            if start_date or end_date:
                date_filter = {}
                if start_date:
                    date_filter["$gte"] = start_date
                if end_date:
                    date_filter["$lte"] = end_date
                query["timestamp"] = date_filter
            
            # Aggregate compliance data
            pipeline = [
                {"$match": query},
                {
                    "$group": {
                        "_id": "$event_type",
                        "count": {"$sum": 1},
                        "users_affected": {"$addToSet": "$user_id"},
                        "earliest_event": {"$min": "$timestamp"},
                        "latest_event": {"$max": "$timestamp"}
                    }
                }
            ]
            
            results = await self._execute_aggregation(pipeline)
            
            # Process results
            event_summary = {}
            total_events = 0
            users_affected = set()
            
            for result in results:
                event_type = result["_id"]
                count = result["count"]
                total_events += count
                users_affected.update(result["users_affected"])
                
                event_summary[event_type] = {
                    "count": count,
                    "users_affected": len(result["users_affected"]),
                    "earliest_event": result["earliest_event"],
                    "latest_event": result["latest_event"]
                }
            
            return ComplianceReport(
                report_id=str(ObjectId()),
                report_type=report_type,
                generated_at=datetime.utcnow(),
                user_id=user_id,
                date_range={
                    "start_date": start_date,
                    "end_date": end_date
                },
                total_events=total_events,
                unique_users_affected=len(users_affected),
                event_summary=event_summary,
                compliance_status="compliant"  # Would need actual compliance logic
            )
            
        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            raise RuntimeError(f"Failed to generate compliance report: {str(e)}")
    
    async def apply_data_retention_policy(
        self,
        policy: DataRetentionPolicy
    ) -> Dict[str, int]:
        """
        Apply data retention policy and cleanup old records
        
        Args:
            policy: Data retention policy configuration
            
        Returns:
            Summary of records processed and deleted
        """
        try:
            summary = {
                "records_processed": 0,
                "records_deleted": 0,
                "records_anonymized": 0,
                "errors": 0
            }
            
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)
            
            # Find records to process
            query = {"timestamp": {"$lt": cutoff_date}}
            records = await self.collection.find(query).to_list(length=None)
            
            for record in records:
                try:
                    summary["records_processed"] += 1
                    
                    if policy.action == "delete":
                        await self.collection.delete_one({"_id": record["_id"]})
                        summary["records_deleted"] += 1
                    
                    elif policy.action == "anonymize":
                        # Anonymize sensitive fields
                        anonymized_record = self._anonymize_record(record)
                        await self.collection.replace_one(
                            {"_id": record["_id"]},
                            anonymized_record
                        )
                        summary["records_anonymized"] += 1
                
                except Exception as e:
                    logger.warning(f"Error processing record {record.get('_id')}: {e}")
                    summary["errors"] += 1
            
            logger.info(
                f"Applied retention policy: {summary['records_deleted']} deleted, "
                f"{summary['records_anonymized']} anonymized"
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Error applying data retention policy: {e}")
            raise RuntimeError(f"Failed to apply retention policy: {str(e)}")
    
    def _anonymize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize a record by removing/hashing PII"""
        anonymized = record.copy()
        
        # Hash user ID to maintain referential integrity
        if "user_id" in anonymized:
            anonymized["user_id"] = hashlib.sha256(
                anonymized["user_id"].encode()
            ).hexdigest()[:16]
        
        # Remove other PII fields
        pii_fields = ["ip_address", "user_agent", "email", "phone"]
        for field in pii_fields:
            if field in anonymized:
                anonymized[field] = "[ANONYMIZED]"
        
        # Mask sensitive data in nested structures
        if "event_data" in anonymized:
            anonymized["event_data"] = self._mask_event_data(anonymized["event_data"])
        
        return anonymized
    
    def _mask_event_data(self, data: Any) -> Any:
        """Mask sensitive data in event data"""
        if isinstance(data, dict):
            masked = {}
            for key, value in data.items():
                if key.lower() in ["email", "phone", "address", "name"]:
                    masked[key] = "[ANONYMIZED]"
                else:
                    masked[key] = self._mask_event_data(value)
            return masked
        elif isinstance(data, list):
            return [self._mask_event_data(item) for item in data]
        else:
            return data
    
    async def _execute_aggregation(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute aggregation pipeline"""
        try:
            cursor = self.collection.aggregate(pipeline)
            return await cursor.to_list(length=None)
        except PyMongoError as e:
            logger.error(f"Error executing aggregation: {e}")
            raise


class SecurityEventDetector:
    """
    Security event detection and alerting system
    
    Monitors audit logs for suspicious patterns, security violations,
    and compliance issues with configurable thresholds and alerting.
    """
    
    def __init__(self):
        """Initialize security event detector"""
        self.detection_rules = {
            'failed_auth_threshold': 5,
            'rate_limit_threshold': 100,
            'suspicious_access_patterns': True,
            'data_export_monitoring': True
        }
        logger.debug("SecurityEventDetector initialized")
    
    def detect_security_events(
        self,
        audit_entries: List[AuditLogEntry]
    ) -> List[SecurityEvent]:
        """
        Detect security events from audit entries
        
        Args:
            audit_entries: List of audit log entries to analyze
            
        Returns:
            List of detected security events
        """
        events = []
        
        # Group entries by user and time window
        user_activities = self._group_activities_by_user(audit_entries)
        
        for user_id, activities in user_activities.items():
            # Check for authentication failures
            auth_failures = [
                a for a in activities
                if a.event_type == AuditEventType.AUTHENTICATION_FAILED
            ]
            
            if len(auth_failures) >= self.detection_rules['failed_auth_threshold']:
                events.append(SecurityEvent(
                    event_id=str(ObjectId()),
                    user_id=user_id,
                    event_type="authentication_failure_threshold",
                    severity=SecurityEventSeverity.HIGH,
                    description=f"User {user_id} had {len(auth_failures)} failed authentication attempts",
                    timestamp=datetime.utcnow(),
                    related_audit_entries=[a.id for a in auth_failures]
                ))
            
            # Check for rate limit violations
            rate_limit_events = [
                a for a in activities
                if a.event_type == AuditEventType.RATE_LIMIT_EXCEEDED
            ]
            
            if len(rate_limit_events) >= self.detection_rules['rate_limit_threshold']:
                events.append(SecurityEvent(
                    event_id=str(ObjectId()),
                    user_id=user_id,
                    event_type="rate_limit_abuse",
                    severity=SecurityEventSeverity.MEDIUM,
                    description=f"User {user_id} exceeded rate limits {len(rate_limit_events)} times",
                    timestamp=datetime.utcnow(),
                    related_audit_entries=[a.id for a in rate_limit_events]
                ))
            
            # Check for suspicious data access patterns
            if self.detection_rules['suspicious_access_patterns']:
                data_access_events = [
                    a for a in activities
                    if a.event_type == AuditEventType.DATA_ACCESSED
                ]
                
                if self._is_suspicious_access_pattern(data_access_events):
                    events.append(SecurityEvent(
                        event_id=str(ObjectId()),
                        user_id=user_id,
                        event_type="suspicious_data_access",
                        severity=SecurityEventSeverity.HIGH,
                        description=f"Suspicious data access pattern detected for user {user_id}",
                        timestamp=datetime.utcnow(),
                        related_audit_entries=[a.id for a in data_access_events]
                    ))
        
        return events
    
    def _group_activities_by_user(
        self,
        audit_entries: List[AuditLogEntry]
    ) -> Dict[str, List[AuditLogEntry]]:
        """Group audit entries by user ID"""
        user_activities = {}
        
        for entry in audit_entries:
            user_id = entry.user_id
            if user_id not in user_activities:
                user_activities[user_id] = []
            user_activities[user_id].append(entry)
        
        return user_activities
    
    def _is_suspicious_access_pattern(self, access_events: List[AuditLogEntry]) -> bool:
        """Detect suspicious data access patterns"""
        if len(access_events) < 10:  # Minimum threshold
            return False
        
        # Check for rapid sequential access
        timestamps = [event.timestamp for event in access_events]
        timestamps.sort()
        
        rapid_access_count = 0
        for i in range(1, len(timestamps)):
            time_diff = (timestamps[i] - timestamps[i-1]).total_seconds()
            if time_diff < 1:  # Less than 1 second between accesses
                rapid_access_count += 1
        
        # If more than 50% of accesses are rapid, flag as suspicious
        return rapid_access_count > len(access_events) * 0.5


class NotificationAuditService:
    """
    Core audit and compliance service for the notification system
    
    Provides comprehensive audit trail management, security compliance,
    data protection, and automated compliance reporting capabilities.
    """
    
    def __init__(
        self,
        audit_collection: Collection,
        security_events_collection: Collection,
        masking_config: Optional[MaskingConfiguration] = None
    ):
        """
        Initialize the audit service
        
        Args:
            audit_collection: MongoDB collection for audit logs
            security_events_collection: Collection for security events
            masking_config: Optional data masking configuration
        """
        self.audit_collection = audit_collection
        self.security_events_collection = security_events_collection
        
        self.masking_engine = DataMaskingEngine()
        self.compliance_reporter = ComplianceReporter(audit_collection)
        self.security_detector = SecurityEventDetector()
        self.masking_config = masking_config
        
        logger.info("NotificationAuditService initialized")
    
    async def log_audit_event(
        self,
        user_id: str,
        event_type: AuditEventType,
        actor_id: str,
        event_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log an audit event with security compliance
        
        Args:
            user_id: User ID associated with the event
            event_type: Type of audit event
            actor_id: ID of the user/system performing the action
            event_data: Event-specific data
            context: Additional context (IP, user agent, etc.)
            
        Returns:
            Audit log entry ID
        """
        try:
            # Mask sensitive data
            masked_event_data = self.masking_engine.mask_sensitive_data(
                event_data, self.masking_config
            ) if event_data else None
            
            masked_context = self.masking_engine.mask_sensitive_data(
                context, self.masking_config
            ) if context else None
            
            # Create audit log entry
            audit_entry = {
                "_id": ObjectId(),
                "user_id": user_id,
                "event_type": event_type.value,
                "actor_id": actor_id,
                "event_data": masked_event_data,
                "context": masked_context,
                "timestamp": datetime.utcnow(),
                "trace_id": context.get("trace_id") if context else None,
                "correlation_id": context.get("correlation_id") if context else None,
                "ip_address": context.get("ip_address") if context else None,
                "user_agent": context.get("user_agent") if context else None
            }
            
            await self.audit_collection.insert_one(audit_entry)
            audit_id = str(audit_entry["_id"])
            
            logger.info(f"Logged audit event {event_type.value} for user {user_id}")
            
            return audit_id
            
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
            raise RuntimeError(f"Failed to log audit event: {str(e)}")
    
    async def get_user_audit_trail(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """
        Get audit trail for a specific user
        
        Args:
            user_id: User ID for audit trail
            start_date: Optional start date filter
            end_date: Optional end date filter
            event_types: Optional event types filter
            limit: Maximum number of entries
            
        Returns:
            List of audit log entries for the user
        """
        try:
            # Build query
            query = {"user_id": user_id}
            
            if start_date or end_date:
                date_filter = {}
                if start_date:
                    date_filter["$gte"] = start_date
                if end_date:
                    date_filter["$lte"] = end_date
                query["timestamp"] = date_filter
            
            if event_types:
                query["event_type"] = {"$in": event_types}
            
            # Execute query
            cursor = self.audit_collection.find(query).sort("timestamp", -1).limit(limit)
            entries = await cursor.to_list(length=limit)
            
            # Convert to response models
            audit_entries = []
            for entry in entries:
                audit_entry = AuditLogEntry(
                    id=str(entry["_id"]),
                    user_id=entry["user_id"],
                    event_type=entry["event_type"],
                    actor_id=entry["actor_id"],
                    event_data=entry.get("event_data"),
                    context=entry.get("context"),
                    timestamp=entry["timestamp"],
                    trace_id=entry.get("trace_id"),
                    correlation_id=entry.get("correlation_id")
                )
                audit_entries.append(audit_entry)
            
            logger.info(f"Retrieved {len(audit_entries)} audit entries for user {user_id}")
            
            return audit_entries
            
        except Exception as e:
            logger.error(f"Error getting audit trail for user {user_id}: {e}")
            raise RuntimeError(f"Failed to get audit trail: {str(e)}")
    
    async def detect_and_log_security_events(
        self,
        time_window_hours: int = 24
    ) -> List[SecurityEvent]:
        """
        Detect security events from recent audit logs
        
        Args:
            time_window_hours: Time window for event detection
            
        Returns:
            List of detected security events
        """
        try:
            # Get recent audit entries
            start_time = datetime.utcnow() - timedelta(hours=time_window_hours)
            recent_entries = await self.get_user_audit_trail(
                user_id="*",  # All users
                start_date=start_time,
                limit=10000  # Large limit for detection
            )
            
            # Detect security events
            security_events = self.security_detector.detect_security_events(recent_entries)
            
            # Log detected security events
            for event in security_events:
                await self.security_events_collection.insert_one(event.dict())
            
            logger.info(f"Detected {len(security_events)} security events")
            
            return security_events
            
        except Exception as e:
            logger.error(f"Error detecting security events: {e}")
            raise RuntimeError(f"Failed to detect security events: {str(e)}")
    
    async def generate_compliance_report(
        self,
        user_id: Optional[str] = None,
        report_type: str = "gdpr"
    ) -> ComplianceReport:
        """Generate compliance report"""
        return await self.compliance_reporter.generate_compliance_report(
            user_id=user_id,
            report_type=report_type
        )
    
    async def apply_data_retention(
        self,
        retention_policy: DataRetentionPolicy
    ) -> Dict[str, int]:
        """Apply data retention policy"""
        return await self.compliance_reporter.apply_data_retention_policy(retention_policy)


# Export the service class and related models
__all__ = [
    "NotificationAuditService",
    "DataMaskingEngine",
    "ComplianceReporter",
    "SecurityEventDetector",
    "AuditEventType",
    "SecurityEventSeverity"
] 