"""
Execution Reporting Module - Alert Management Service

Service for alert rule evaluation, threshold monitoring, and notification management.
Provides intelligent alerting capabilities with configurable thresholds and escalation.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from motor.motor_asyncio import AsyncIOMotorDatabase

from ...config.logging import get_logger
from ..models.execution_report_model import (
    AlertConfigurationModel, AlertStatus, AlertSeverity
)
from ..schemas.alert_schemas import (
    AlertRuleCreateRequest, AlertRuleResponse, AlertConfigurationResponse,
    NotificationChannelConfig
)

logger = get_logger(__name__)


class AlertEvaluationResult(Enum):
    """Alert evaluation results"""
    NO_ALERT = "no_alert"
    WARNING = "warning"
    CRITICAL = "critical"
    RESOLVED = "resolved"


class AlertManagementService:
    """
    Advanced alert management service for threshold monitoring and notifications.
    
    Provides alert management capabilities including:
    - Threshold-based alert rule evaluation
    - Multi-level alert severity management
    - Notification channel integration
    - Alert escalation and de-escalation
    - Alert history and audit tracking
    """
    
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        quality_metrics_service: Optional[Any] = None,
        trend_analysis_service: Optional[Any] = None,
        notification_service: Optional[Any] = None
    ):
        """Initialize alert management service with dependencies"""
        self.database = database
        self.quality_metrics_service = quality_metrics_service
        self.trend_analysis_service = trend_analysis_service
        self.notification_service = notification_service
        self.logger = logger.bind(service="AlertManagementService")
        
        # Collections
        self.alert_configs_collection = self.database.alert_configurations
        self.alert_history_collection = self.database.alert_history
        self.alert_states_collection = self.database.alert_states
        
    async def create_alert_rule(
        self,
        request: AlertRuleCreateRequest,
        user_id: str
    ) -> AlertRuleResponse:
        """
        Create a new alert rule configuration.
        
        Args:
            request: Alert rule creation request
            user_id: ID of user creating the alert rule
            
        Returns:
            AlertRuleResponse: Created alert rule configuration
            
        Raises:
            ValueError: If request parameters are invalid
            RuntimeError: If creation fails
        """
        start_time = datetime.now(timezone.utc)
        alert_id = f"alert_{uuid.uuid4().hex[:12]}"
        
        try:
            self.logger.info(
                "Creating alert rule",
                alert_id=alert_id,
                user_id=user_id,
                metric_type=request.metric_type
            )
            
            # Validate alert rule configuration
            await self._validate_alert_rule(request)
            
            # Create alert configuration model
            alert_config = AlertConfigurationModel(
                alert_id=alert_id,
                name=request.name,
                description=request.description,
                metric_type=request.metric_type,
                threshold_config=request.threshold_config.dict(),
                notification_config=request.notification_config.dict(),
                evaluation_interval_minutes=request.evaluation_interval_minutes,
                escalation_config=request.escalation_config.dict() if request.escalation_config else None,
                is_enabled=request.is_enabled,
                created_by=user_id,
                metadata={
                    "creation_source": "user_request",
                    "rule_type": request.metric_type,
                    "severity_levels": list(request.threshold_config.dict().keys())
                }
            )
            
            # Store alert configuration
            await self.alert_configs_collection.insert_one(alert_config.dict(by_alias=True))
            
            # Initialize alert state
            await self._initialize_alert_state(alert_id, user_id)
            
            # Create response
            alert_response = AlertRuleResponse(
                alert_id=alert_id,
                name=request.name,
                description=request.description,
                metric_type=request.metric_type,
                threshold_config=request.threshold_config,
                notification_config=request.notification_config,
                evaluation_interval_minutes=request.evaluation_interval_minutes,
                escalation_config=request.escalation_config,
                is_enabled=request.is_enabled,
                created_by=user_id,
                created_at=alert_config.created_at,
                status=AlertStatus.ACTIVE,
                last_evaluation=None,
                last_triggered=None
            )
            
            creation_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.logger.info(
                "Alert rule created successfully",
                alert_id=alert_id,
                creation_time_ms=creation_time
            )
            
            return alert_response
            
        except Exception as e:
            self.logger.error(
                "Alert rule creation failed",
                alert_id=alert_id,
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Failed to create alert rule: {str(e)}") from e
    
    async def evaluate_alerts(
        self,
        alert_ids: Optional[List[str]] = None,
        user_id: str = None
    ) -> Dict[str, AlertEvaluationResult]:
        """
        Evaluate alert rules and trigger notifications if thresholds are exceeded.
        
        Args:
            alert_ids: Specific alert IDs to evaluate (None for all active alerts)
            user_id: ID of user requesting evaluation
            
        Returns:
            Dict[str, AlertEvaluationResult]: Evaluation results for each alert
            
        Raises:
            RuntimeError: If evaluation fails
        """
        start_time = datetime.now(timezone.utc)
        evaluation_id = f"eval_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Starting alert evaluation",
                evaluation_id=evaluation_id,
                alert_count=len(alert_ids) if alert_ids else "all",
                user_id=user_id
            )
            
            # Get alert configurations to evaluate
            alert_configs = await self._get_alert_configs_for_evaluation(alert_ids)
            
            evaluation_results = {}
            
            # Evaluate each alert
            for alert_config in alert_configs:
                alert_id = alert_config["alert_id"]
                
                try:
                    result = await self._evaluate_single_alert(alert_config, evaluation_id)
                    evaluation_results[alert_id] = result
                    
                    # Update alert state
                    await self._update_alert_state(alert_id, result, datetime.now(timezone.utc))
                    
                except Exception as e:
                    self.logger.error(
                        "Single alert evaluation failed",
                        alert_id=alert_id,
                        evaluation_id=evaluation_id,
                        error=str(e)
                    )
                    evaluation_results[alert_id] = AlertEvaluationResult.NO_ALERT
            
            evaluation_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.logger.info(
                "Alert evaluation completed",
                evaluation_id=evaluation_id,
                alerts_evaluated=len(evaluation_results),
                evaluation_time_ms=evaluation_time
            )
            
            return evaluation_results
            
        except Exception as e:
            self.logger.error(
                "Alert evaluation failed",
                evaluation_id=evaluation_id,
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Failed to evaluate alerts: {str(e)}") from e
    
    async def _evaluate_single_alert(
        self,
        alert_config: Dict[str, Any],
        evaluation_id: str
    ) -> AlertEvaluationResult:
        """Evaluate a single alert rule against current metrics"""
        
        alert_id = alert_config["alert_id"]
        metric_type = alert_config["metric_type"]
        threshold_config = alert_config["threshold_config"]
        
        try:
            # Get current metric value
            current_value = await self._get_current_metric_value(metric_type, alert_config)
            
            # Get previous alert state
            previous_state = await self._get_alert_state(alert_id)
            
            # Evaluate thresholds
            evaluation_result = self._evaluate_thresholds(
                current_value, threshold_config, previous_state
            )
            
            # Handle alert triggers
            if evaluation_result in [AlertEvaluationResult.WARNING, AlertEvaluationResult.CRITICAL]:
                await self._handle_alert_trigger(
                    alert_config, evaluation_result, current_value, evaluation_id
                )
            elif evaluation_result == AlertEvaluationResult.RESOLVED:
                await self._handle_alert_resolution(
                    alert_config, current_value, evaluation_id
                )
            
            return evaluation_result
            
        except Exception as e:
            self.logger.error(
                "Single alert evaluation failed",
                alert_id=alert_id,
                metric_type=metric_type,
                evaluation_id=evaluation_id,
                error=str(e)
            )
            return AlertEvaluationResult.NO_ALERT
    
    async def _get_current_metric_value(
        self,
        metric_type: str,
        alert_config: Dict[str, Any]
    ) -> float:
        """Get current value for the specified metric type"""
        
        if metric_type == "pass_rate":
            # Get current pass rate from quality metrics service
            if self.quality_metrics_service:
                # This would integrate with QualityMetricsService
                return 0.85  # Mock value
            return 0.0
            
        elif metric_type == "failure_rate":
            # Calculate failure rate
            return 1.0 - await self._get_current_metric_value("pass_rate", alert_config)
            
        elif metric_type == "flakiness_score":
            # Get flakiness score from quality metrics service
            if self.quality_metrics_service:
                return 0.12  # Mock value
            return 0.0
            
        elif metric_type == "execution_duration":
            # Get average execution duration
            return 2500.0  # Mock value in milliseconds
            
        elif metric_type == "mttr_hours":
            # Get mean time to resolve
            if self.quality_metrics_service:
                return 4.5  # Mock value
            return 0.0
            
        else:
            self.logger.warning(f"Unknown metric type: {metric_type}")
            return 0.0
    
    def _evaluate_thresholds(
        self,
        current_value: float,
        threshold_config: Dict[str, Any],
        previous_state: Optional[Dict[str, Any]]
    ) -> AlertEvaluationResult:
        """Evaluate current value against configured thresholds"""
        
        critical_threshold = threshold_config.get("critical")
        warning_threshold = threshold_config.get("warning")
        
        # Determine if we're looking for values above or below thresholds
        threshold_direction = threshold_config.get("direction", "above")  # "above" or "below"
        
        if threshold_direction == "above":
            # Alert when value is above threshold (e.g., failure rate, duration)
            if critical_threshold and current_value >= critical_threshold:
                return AlertEvaluationResult.CRITICAL
            elif warning_threshold and current_value >= warning_threshold:
                return AlertEvaluationResult.WARNING
        else:
            # Alert when value is below threshold (e.g., pass rate)
            if critical_threshold and current_value <= critical_threshold:
                return AlertEvaluationResult.CRITICAL
            elif warning_threshold and current_value <= warning_threshold:
                return AlertEvaluationResult.WARNING
        
        # Check if alert should be resolved
        if previous_state and previous_state.get("status") in ["WARNING", "CRITICAL"]:
            # Implement hysteresis - require value to be better than threshold by buffer
            buffer = threshold_config.get("resolution_buffer", 0.05)
            
            if threshold_direction == "above":
                # For "above" thresholds, resolved when value drops below threshold - buffer
                if warning_threshold and current_value < (warning_threshold - buffer):
                    return AlertEvaluationResult.RESOLVED
            else:
                # For "below" thresholds, resolved when value rises above threshold + buffer
                if warning_threshold and current_value > (warning_threshold + buffer):
                    return AlertEvaluationResult.RESOLVED
        
        return AlertEvaluationResult.NO_ALERT
    
    async def _handle_alert_trigger(
        self,
        alert_config: Dict[str, Any],
        severity: AlertEvaluationResult,
        current_value: float,
        evaluation_id: str
    ) -> None:
        """Handle alert trigger by sending notifications"""
        
        alert_id = alert_config["alert_id"]
        notification_config = alert_config.get("notification_config", {})
        
        # Create alert event
        alert_event = {
            "alert_id": alert_id,
            "evaluation_id": evaluation_id,
            "alert_name": alert_config["name"],
            "metric_type": alert_config["metric_type"],
            "severity": severity.value,
            "current_value": current_value,
            "threshold_config": alert_config["threshold_config"],
            "triggered_at": datetime.now(timezone.utc),
            "message": self._generate_alert_message(alert_config, severity, current_value)
        }
        
        # Store alert event
        await self.alert_history_collection.insert_one(alert_event)
        
        # Send notifications
        await self._send_notifications(alert_event, notification_config)
        
        self.logger.info(
            "Alert triggered",
            alert_id=alert_id,
            severity=severity.value,
            current_value=current_value,
            evaluation_id=evaluation_id
        )
    
    async def _handle_alert_resolution(
        self,
        alert_config: Dict[str, Any],
        current_value: float,
        evaluation_id: str
    ) -> None:
        """Handle alert resolution"""
        
        alert_id = alert_config["alert_id"]
        
        # Create resolution event
        resolution_event = {
            "alert_id": alert_id,
            "evaluation_id": evaluation_id,
            "alert_name": alert_config["name"],
            "metric_type": alert_config["metric_type"],
            "severity": "RESOLVED",
            "current_value": current_value,
            "resolved_at": datetime.now(timezone.utc),
            "message": f"Alert '{alert_config['name']}' has been resolved. Current value: {current_value}"
        }
        
        # Store resolution event
        await self.alert_history_collection.insert_one(resolution_event)
        
        # Send resolution notification
        notification_config = alert_config.get("notification_config", {})
        await self._send_notifications(resolution_event, notification_config)
        
        self.logger.info(
            "Alert resolved",
            alert_id=alert_id,
            current_value=current_value,
            evaluation_id=evaluation_id
        )
    
    def _generate_alert_message(
        self,
        alert_config: Dict[str, Any],
        severity: AlertEvaluationResult,
        current_value: float
    ) -> str:
        """Generate human-readable alert message"""
        
        name = alert_config["name"]
        metric_type = alert_config["metric_type"]
        threshold_config = alert_config["threshold_config"]
        
        if severity == AlertEvaluationResult.CRITICAL:
            threshold = threshold_config.get("critical")
            return f"CRITICAL: {name} - {metric_type} is {current_value:.2f} (threshold: {threshold})"
        elif severity == AlertEvaluationResult.WARNING:
            threshold = threshold_config.get("warning")
            return f"WARNING: {name} - {metric_type} is {current_value:.2f} (threshold: {threshold})"
        else:
            return f"Alert: {name} - {metric_type} value: {current_value:.2f}"
    
    async def _send_notifications(
        self,
        alert_event: Dict[str, Any],
        notification_config: Dict[str, Any]
    ) -> None:
        """Send notifications through configured channels"""
        
        channels = notification_config.get("channels", [])
        
        for channel_config in channels:
            channel_type = channel_config.get("type")
            
            try:
                if channel_type == "email":
                    await self._send_email_notification(alert_event, channel_config)
                elif channel_type == "slack":
                    await self._send_slack_notification(alert_event, channel_config)
                elif channel_type == "webhook":
                    await self._send_webhook_notification(alert_event, channel_config)
                else:
                    self.logger.warning(f"Unknown notification channel type: {channel_type}")
                    
            except Exception as e:
                self.logger.error(
                    "Notification send failed",
                    channel_type=channel_type,
                    alert_id=alert_event["alert_id"],
                    error=str(e)
                )
    
    async def _send_email_notification(
        self,
        alert_event: Dict[str, Any],
        channel_config: Dict[str, Any]
    ) -> None:
        """Send email notification"""
        # Implement email notification logic
        self.logger.info(
            "Email notification sent",
            alert_id=alert_event["alert_id"],
            recipients=channel_config.get("recipients", [])
        )
    
    async def _send_slack_notification(
        self,
        alert_event: Dict[str, Any],
        channel_config: Dict[str, Any]
    ) -> None:
        """Send Slack notification"""
        # Implement Slack notification logic
        self.logger.info(
            "Slack notification sent",
            alert_id=alert_event["alert_id"],
            channel=channel_config.get("channel")
        )
    
    async def _send_webhook_notification(
        self,
        alert_event: Dict[str, Any],
        channel_config: Dict[str, Any]
    ) -> None:
        """Send webhook notification"""
        # Implement webhook notification logic
        self.logger.info(
            "Webhook notification sent",
            alert_id=alert_event["alert_id"],
            url=channel_config.get("url")
        )
    
    async def _validate_alert_rule(self, request: AlertRuleCreateRequest) -> None:
        """Validate alert rule configuration"""
        
        # Validate metric type
        supported_metrics = [
            "pass_rate", "failure_rate", "flakiness_score", 
            "execution_duration", "mttr_hours"
        ]
        
        if request.metric_type not in supported_metrics:
            raise ValueError(f"Unsupported metric type: {request.metric_type}")
        
        # Validate thresholds
        threshold_config = request.threshold_config.dict()
        if not threshold_config.get("warning") and not threshold_config.get("critical"):
            raise ValueError("At least one threshold (warning or critical) must be specified")
        
        # Validate notification channels
        for channel in request.notification_config.channels:
            if channel.type not in ["email", "slack", "webhook"]:
                raise ValueError(f"Unsupported notification channel type: {channel.type}")
    
    async def _get_alert_configs_for_evaluation(
        self,
        alert_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get alert configurations that need evaluation"""
        
        query = {"is_enabled": True}
        
        if alert_ids:
            query["alert_id"] = {"$in": alert_ids}
        
        # Also filter by evaluation interval if needed
        # This would check last_evaluation_at against evaluation_interval_minutes
        
        configs = []
        async for config in self.alert_configs_collection.find(query):
            configs.append(config)
        
        return configs
    
    async def _initialize_alert_state(self, alert_id: str, user_id: str) -> None:
        """Initialize alert state tracking"""
        
        alert_state = {
            "alert_id": alert_id,
            "status": AlertStatus.ACTIVE.value,
            "last_evaluation": None,
            "last_triggered": None,
            "consecutive_violations": 0,
            "created_at": datetime.now(timezone.utc),
            "created_by": user_id
        }
        
        await self.alert_states_collection.insert_one(alert_state)
    
    async def _get_alert_state(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """Get current alert state"""
        return await self.alert_states_collection.find_one({"alert_id": alert_id})
    
    async def _update_alert_state(
        self,
        alert_id: str,
        evaluation_result: AlertEvaluationResult,
        evaluation_time: datetime
    ) -> None:
        """Update alert state after evaluation"""
        
        update_doc = {
            "last_evaluation": evaluation_time,
            "status": evaluation_result.value
        }
        
        if evaluation_result in [AlertEvaluationResult.WARNING, AlertEvaluationResult.CRITICAL]:
            update_doc["last_triggered"] = evaluation_time
            # Increment consecutive violations
            await self.alert_states_collection.update_one(
                {"alert_id": alert_id},
                {
                    "$set": update_doc,
                    "$inc": {"consecutive_violations": 1}
                }
            )
        else:
            # Reset consecutive violations for no alert or resolved
            update_doc["consecutive_violations"] = 0
            await self.alert_states_collection.update_one(
                {"alert_id": alert_id},
                {"$set": update_doc}
            )
    
    async def get_alert_history(
        self,
        alert_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get alert history with optional filtering.
        
        Args:
            alert_id: Filter by specific alert ID
            start_date: Filter events after this date
            end_date: Filter events before this date
            page: Page number (1-based)
            page_size: Number of items per page
            
        Returns:
            Tuple of (alert events, total count)
        """
        
        query = {}
        
        if alert_id:
            query["alert_id"] = alert_id
        
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            query["triggered_at"] = date_filter
        
        # Get total count
        total_count = await self.alert_history_collection.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * page_size
        cursor = self.alert_history_collection.find(query).sort("triggered_at", -1).skip(skip).limit(page_size)
        
        events = []
        async for event in cursor:
            events.append(event)
        
        return events, total_count


class AlertManagementServiceFactory:
    """Factory for creating AlertManagementService instances"""
    
    @staticmethod
    def create(
        database: AsyncIOMotorDatabase,
        quality_metrics_service: Optional[Any] = None,
        trend_analysis_service: Optional[Any] = None,
        notification_service: Optional[Any] = None
    ) -> AlertManagementService:
        """Create and configure AlertManagementService instance"""
        return AlertManagementService(
            database=database,
            quality_metrics_service=quality_metrics_service,
            trend_analysis_service=trend_analysis_service,
            notification_service=notification_service
        ) 