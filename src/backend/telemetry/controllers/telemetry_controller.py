"""
Telemetry Controller Module

This module implements the TelemetryController class which acts as the HTTP boundary
for the telemetry engine. It handles request validation, user authentication, and
telemetry data processing operations. This controller connects external agents and
systems to the Telemetry Service via FastAPI-compatible endpoints.

Key Features:
- JWT-based authentication for all endpoints
- Comprehensive request/response validation using Pydantic schemas
- Integration with TelemetryService for business logic
- Structured error handling with FastAPI HTTPException
- Audit logging with correlation tracking and user context
- SRP compliance with dependency injection pattern
- Async operations optimized for high-throughput telemetry ingestion
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from fastapi import HTTPException, status, Depends

from ..schemas.telemetry_schemas import (
    HeartbeatRequestSchema,
    SystemMetricsRequestSchema,
    HeartbeatResponseSchema,
    SystemMetricsResponseSchema,
    UptimeStatusResponseSchema,
    HealthCheckRequestSchema,
    HealthStatusResponseSchema,
    TelemetryIngestionBatchSchema,
    TelemetryIngestionResultSchema
)
from ..services.telemetry_service import TelemetryService, TelemetryServiceException
from ..models.telemetry_models import (
    InvalidTelemetryDataError,
    HealthCheckFailedError,
    TelemetryException
)
from ...auth.dependencies.auth_dependencies import get_current_user
from ...auth.schemas.auth_responses import UserResponse
from ...config.logging import get_logger

logger = get_logger(__name__)


class TelemetryController:
    """
    HTTP controller for telemetry engine operations.
    
    This controller acts as the FastAPI boundary layer for telemetry operations,
    handling request validation, authentication, and routing to appropriate services.
    It follows SRP by delegating all business logic to the TelemetryService.
    
    Responsibilities:
    - HTTP request/response handling for telemetry operations
    - Request validation using Pydantic schemas
    - JWT authentication enforcement
    - Error handling and HTTP status code mapping
    - Audit logging with correlation tracking and user context
    - Integration with telemetry service layer
    """
    
    def __init__(self, telemetry_service: TelemetryService):
        """
        Initialize the telemetry controller.
        
        Args:
            telemetry_service: Telemetry service for business logic operations
        """
        self.telemetry_service = telemetry_service
        self.logger = logger.bind(controller="TelemetryController")
    
    async def record_heartbeat(
        self,
        request: HeartbeatRequestSchema,
        current_user: UserResponse = Depends(get_current_user)
    ) -> HeartbeatResponseSchema:
        """
        Record agent heartbeat with health metrics.
        
        This handler validates the incoming heartbeat request, extracts user information
        from the JWT token, and forwards the validated request to the TelemetryService
        for processing. It handles health assessment, alert generation, and uptime tracking.
        
        Args:
            request: Heartbeat request with agent metrics and health data
            current_user: Authenticated user from JWT token
            
        Returns:
            HeartbeatResponseSchema: Heartbeat processing results with health assessment
            
        Raises:
            HTTPException: 400 for validation errors, 401 for auth errors,
                          422 for data quality issues, 500 for internal errors
        """
        correlation_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        bound_logger = self.logger.bind(
            operation="record_heartbeat",
            agent_id=request.agent_info.agent_id,
            user_id=current_user.id,
            correlation_id=correlation_id
        )
        
        bound_logger.info("Processing heartbeat request")
        
        try:
            # Validate user has permission to submit telemetry for this agent
            await self._validate_agent_access(request.agent_info.agent_id, current_user, bound_logger)
            
            # Process heartbeat through service layer
            response = await self.telemetry_service.ingest_heartbeat(request)
            
            # Calculate request latency
            end_time = datetime.now(timezone.utc)
            latency_ms = (end_time - start_time).total_seconds() * 1000
            
            bound_logger.info("Heartbeat processed successfully", extra={
                "heartbeat_id": response.heartbeat_id,
                "calculated_health": response.calculated_health,
                "health_score": response.health_score,
                "alerts_count": len(response.alerts_generated),
                "latency_ms": latency_ms
            })
            
            return response
            
        except InvalidTelemetryDataError as e:
            bound_logger.warning("Heartbeat validation failed", extra={
                "error": str(e),
                "field_name": getattr(e, 'field_name', None)
            })
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid heartbeat data: {str(e)}"
            )
            
        except PermissionError as e:
            bound_logger.warning("Heartbeat access denied", extra={
                "error": str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for agent: {str(e)}"
            )
            
        except TelemetryServiceException as e:
            bound_logger.error("Heartbeat service error", extra={
                "error": str(e),
                "error_code": getattr(e, 'error_code', None),
                "operation": getattr(e, 'operation', None)
            })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process heartbeat: {str(e)}"
            )
            
        except Exception as e:
            bound_logger.error("Unexpected heartbeat error", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error processing heartbeat"
            )
    
    async def record_system_metrics(
        self,
        request: SystemMetricsRequestSchema,
        current_user: UserResponse = Depends(get_current_user)
    ) -> SystemMetricsResponseSchema:
        """
        Record system performance metrics with threshold analysis.
        
        This handler validates the incoming metrics request, extracts user information
        from the JWT token, and forwards the validated request to the TelemetryService
        for processing. It handles data quality assessment, outlier detection, and
        threshold-based alerting.
        
        Args:
            request: System metrics request with performance data
            current_user: Authenticated user from JWT token
            
        Returns:
            SystemMetricsResponseSchema: Metrics processing results with quality assessment
            
        Raises:
            HTTPException: 400 for validation errors, 401 for auth errors,
                          422 for data quality issues, 500 for internal errors
        """
        correlation_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        bound_logger = self.logger.bind(
            operation="record_system_metrics",
            system_id=request.system_id,
            metrics_count=len(request.metrics),
            user_id=current_user.id,
            correlation_id=correlation_id
        )
        
        bound_logger.info("Processing system metrics request")
        
        try:
            # Validate user has permission to submit metrics for this system
            await self._validate_system_access(request.system_id, current_user, bound_logger)
            
            # Process metrics through service layer
            response = await self.telemetry_service.record_metrics(request)
            
            # Calculate request latency
            end_time = datetime.now(timezone.utc)
            latency_ms = (end_time - start_time).total_seconds() * 1000
            
            bound_logger.info("System metrics processed successfully", extra={
                "metrics_processed": response.metrics_processed,
                "metrics_failed": len(request.metrics) - response.metrics_processed,
                "validation_errors_count": len(response.validation_errors),
                "alerts_count": len(response.alerts_generated),
                "outliers_count": len(response.outliers_detected),
                "latency_ms": latency_ms
            })
            
            return response
            
        except InvalidTelemetryDataError as e:
            bound_logger.warning("Metrics validation failed", extra={
                "error": str(e),
                "field_name": getattr(e, 'field_name', None)
            })
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid metrics data: {str(e)}"
            )
            
        except PermissionError as e:
            bound_logger.warning("Metrics access denied", extra={
                "error": str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for system: {str(e)}"
            )
            
        except TelemetryServiceException as e:
            bound_logger.error("Metrics service error", extra={
                "error": str(e),
                "error_code": getattr(e, 'error_code', None),
                "operation": getattr(e, 'operation', None)
            })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process metrics: {str(e)}"
            )
            
        except Exception as e:
            bound_logger.error("Unexpected metrics error", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error processing metrics"
            )
    
    async def get_uptime_status(
        self,
        agent_id: str,
        time_range_hours: int = 24,
        current_user: UserResponse = Depends(get_current_user)
    ) -> UptimeStatusResponseSchema:
        """
        Get comprehensive uptime status and availability metrics for an agent.
        
        This handler validates the agent access permissions, extracts user information
        from the JWT token, and forwards the request to the TelemetryService for
        uptime calculation. It provides uptime percentage, health assessment, and
        SLA compliance analysis.
        
        Args:
            agent_id: Target agent identifier
            time_range_hours: Analysis time range in hours (default 24h)
            current_user: Authenticated user from JWT token
            
        Returns:
            UptimeStatusResponseSchema: Comprehensive uptime analysis
            
        Raises:
            HTTPException: 400 for validation errors, 401 for auth errors,
                          404 for agent not found, 500 for internal errors
        """
        correlation_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        bound_logger = self.logger.bind(
            operation="get_uptime_status",
            agent_id=agent_id,
            time_range_hours=time_range_hours,
            user_id=current_user.id,
            correlation_id=correlation_id
        )
        
        bound_logger.info("Processing uptime status request")
        
        try:
            # Validate user has permission to view this agent's uptime
            await self._validate_agent_access(agent_id, current_user, bound_logger)
            
            # Validate time range parameters
            if time_range_hours < 1 or time_range_hours > 8760:  # 1 hour to 1 year
                raise ValueError("Time range must be between 1 and 8760 hours")
            
            # Calculate uptime through service layer
            response = await self.telemetry_service.calculate_uptime(agent_id, time_range_hours)
            
            # Calculate request latency
            end_time = datetime.now(timezone.utc)
            latency_ms = (end_time - start_time).total_seconds() * 1000
            
            bound_logger.info("Uptime status calculated successfully", extra={
                "uptime_percentage": response.uptime_percentage,
                "overall_health": response.health_assessment.overall_health,
                "health_score": response.health_assessment.health_score,
                "sla_compliance": response.sla_compliance,
                "data_quality_score": response.data_quality_score,
                "latency_ms": latency_ms
            })
            
            return response
            
        except ValueError as e:
            bound_logger.warning("Uptime request validation failed", extra={
                "error": str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid request parameters: {str(e)}"
            )
            
        except PermissionError as e:
            bound_logger.warning("Uptime access denied", extra={
                "error": str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for agent: {str(e)}"
            )
            
        except HealthCheckFailedError as e:
            bound_logger.warning("Uptime calculation failed - no data", extra={
                "error": str(e),
                "target_id": getattr(e, 'target_id', None),
                "health_status": getattr(e, 'health_status', None)
            })
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No telemetry data found for agent: {str(e)}"
            )
            
        except TelemetryServiceException as e:
            bound_logger.error("Uptime service error", extra={
                "error": str(e),
                "error_code": getattr(e, 'error_code', None),
                "operation": getattr(e, 'operation', None)
            })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to calculate uptime: {str(e)}"
            )
            
        except Exception as e:
            bound_logger.error("Unexpected uptime error", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error calculating uptime"
            )
    
    async def perform_health_check(
        self,
        request: HealthCheckRequestSchema,
        current_user: UserResponse = Depends(get_current_user)
    ) -> HealthStatusResponseSchema:
        """
        Perform comprehensive health check assessment for a target system or agent.
        
        This handler validates the health check request, extracts user information
        from the JWT token, and performs health assessment based on recent telemetry
        data. It provides comprehensive health evaluation including component analysis.
        
        Args:
            request: Health check request with target and assessment parameters
            current_user: Authenticated user from JWT token
            
        Returns:
            HealthStatusResponseSchema: Comprehensive health assessment results
            
        Raises:
            HTTPException: 400 for validation errors, 401 for auth errors,
                          404 for target not found, 500 for internal errors
        """
        correlation_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        bound_logger = self.logger.bind(
            operation="perform_health_check",
            target_id=request.target_id,
            target_type=request.target_type,
            assessment_type=request.assessment_type,
            user_id=current_user.id,
            correlation_id=correlation_id
        )
        
        bound_logger.info("Processing health check request")
        
        try:
            # Validate user has permission to perform health check on this target
            if request.target_type == "agent":
                await self._validate_agent_access(request.target_id, current_user, bound_logger)
            else:
                await self._validate_system_access(request.target_id, current_user, bound_logger)
            
            # For now, redirect to uptime calculation as comprehensive health check
            # This is a simplified implementation that uses uptime calculation
            time_range_hours = 24
            if request.time_range:
                # Calculate hours from time range
                time_diff = request.time_range.end_time - request.time_range.start_time
                time_range_hours = int(time_diff.total_seconds() / 3600)
                time_range_hours = max(1, min(time_range_hours, 8760))  # 1 hour to 1 year
            
            uptime_response = await self.telemetry_service.calculate_uptime(
                request.target_id, 
                time_range_hours
            )
            
            # Convert uptime response to health status response
            assessment_id = str(uuid.uuid4())
            
            response = HealthStatusResponseSchema(
                target_id=request.target_id,
                assessment_id=assessment_id,
                assessment_completed_at=datetime.now(timezone.utc),
                health_assessment=uptime_response.health_assessment,
                uptime_percentage=uptime_response.uptime_percentage,
                downtime_duration=f"PT{uptime_response.total_downtime_minutes:.1f}M",
                uptime_sessions=[],  # Simplified for now
                sla_target=uptime_response.sla_target,
                sla_compliance=uptime_response.sla_compliance,
                sla_breach_risk=uptime_response.sla_breach_risk,
                performance_trends={},  # Simplified for now
                failure_patterns=uptime_response.failure_patterns,
                health_recommendations=uptime_response.health_recommendations,
                maintenance_suggestions=[]  # Could be expanded based on assessment type
            )
            
            # Calculate request latency
            end_time = datetime.now(timezone.utc)
            latency_ms = (end_time - start_time).total_seconds() * 1000
            
            bound_logger.info("Health check completed successfully", extra={
                "assessment_id": assessment_id,
                "overall_health": response.health_assessment.overall_health,
                "health_score": response.health_assessment.health_score,
                "uptime_percentage": response.uptime_percentage,
                "sla_compliance": response.sla_compliance,
                "latency_ms": latency_ms
            })
            
            return response
            
        except ValueError as e:
            bound_logger.warning("Health check validation failed", extra={
                "error": str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid health check parameters: {str(e)}"
            )
            
        except PermissionError as e:
            bound_logger.warning("Health check access denied", extra={
                "error": str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied for target: {str(e)}"
            )
            
        except HealthCheckFailedError as e:
            bound_logger.warning("Health check failed - no data", extra={
                "error": str(e),
                "target_id": getattr(e, 'target_id', None),
                "health_status": getattr(e, 'health_status', None)
            })
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No telemetry data found for target: {str(e)}"
            )
            
        except TelemetryServiceException as e:
            bound_logger.error("Health check service error", extra={
                "error": str(e),
                "error_code": getattr(e, 'error_code', None),
                "operation": getattr(e, 'operation', None)
            })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to perform health check: {str(e)}"
            )
            
        except Exception as e:
            bound_logger.error("Unexpected health check error", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error performing health check"
            )
    
    async def ingest_telemetry_batch(
        self,
        request: TelemetryIngestionBatchSchema,
        current_user: UserResponse = Depends(get_current_user)
    ) -> TelemetryIngestionResultSchema:
        """
        Ingest batch telemetry data for high-throughput operations.
        
        This handler validates batch telemetry requests containing multiple heartbeats
        and metrics, processes them efficiently through the service layer, and returns
        comprehensive processing results including success/failure counts and error details.
        
        Args:
            request: Batch telemetry request with heartbeats and metrics
            current_user: Authenticated user from JWT token
            
        Returns:
            TelemetryIngestionResultSchema: Batch processing results
            
        Raises:
            HTTPException: 400 for validation errors, 401 for auth errors,
                          422 for data quality issues, 500 for internal errors
        """
        correlation_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        bound_logger = self.logger.bind(
            operation="ingest_telemetry_batch",
            batch_id=request.batch_id,
            heartbeats_count=len(request.heartbeats),
            metrics_count=len(request.metrics),
            user_id=current_user.id,
            correlation_id=correlation_id
        )
        
        bound_logger.info("Processing telemetry batch request")
        
        try:
            # Process heartbeats
            processed_heartbeats = 0
            failed_heartbeats = 0
            total_alerts = 0
            validation_errors = []
            processing_errors = []
            
            for heartbeat in request.heartbeats:
                try:
                    await self._validate_agent_access(heartbeat.agent_info.agent_id, current_user, bound_logger)
                    response = await self.telemetry_service.ingest_heartbeat(heartbeat)
                    processed_heartbeats += 1
                    total_alerts += len(response.alerts_generated)
                except Exception as e:
                    failed_heartbeats += 1
                    processing_errors.append(f"Heartbeat {heartbeat.agent_info.agent_id}: {str(e)}")
            
            # Process metrics
            processed_metrics = 0
            failed_metrics = 0
            
            for metrics in request.metrics:
                try:
                    await self._validate_system_access(metrics.system_id, current_user, bound_logger)
                    response = await self.telemetry_service.record_metrics(metrics)
                    processed_metrics += response.metrics_processed
                    failed_metrics += len(metrics.metrics) - response.metrics_processed
                    total_alerts += len(response.alerts_generated)
                    validation_errors.extend(response.validation_errors)
                except Exception as e:
                    failed_metrics += len(metrics.metrics)
                    processing_errors.append(f"Metrics {metrics.system_id}: {str(e)}")
            
            # Calculate processing metrics
            end_time = datetime.now(timezone.utc)
            processing_time_ms = (end_time - start_time).total_seconds() * 1000
            total_items = processed_heartbeats + processed_metrics + failed_heartbeats + failed_metrics
            throughput_per_second = total_items / (processing_time_ms / 1000) if processing_time_ms > 0 else 0
            
            # Calculate overall data quality score
            total_processed = processed_heartbeats + processed_metrics
            total_items_attempted = len(request.heartbeats) + sum(len(m.metrics) for m in request.metrics)
            data_quality_score = total_processed / total_items_attempted if total_items_attempted > 0 else 0
            
            response = TelemetryIngestionResultSchema(
                success=total_processed > 0,
                batch_id=request.batch_id,
                processed_at=end_time,
                total_heartbeats=len(request.heartbeats),
                processed_heartbeats=processed_heartbeats,
                failed_heartbeats=failed_heartbeats,
                total_metrics=sum(len(m.metrics) for m in request.metrics),
                processed_metrics=processed_metrics,
                failed_metrics=failed_metrics,
                processing_time_ms=processing_time_ms,
                throughput_per_second=throughput_per_second,
                validation_errors=validation_errors,
                processing_errors=processing_errors,
                alerts_generated=total_alerts,
                data_quality_score=data_quality_score
            )
            
            bound_logger.info("Telemetry batch processed successfully", extra={
                "total_processed": total_processed,
                "total_failed": failed_heartbeats + failed_metrics,
                "processing_time_ms": processing_time_ms,
                "throughput_per_second": throughput_per_second,
                "data_quality_score": data_quality_score,
                "alerts_generated": total_alerts
            })
            
            return response
            
        except Exception as e:
            bound_logger.error("Unexpected batch processing error", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error processing telemetry batch"
            )
    
    # Private helper methods for validation
    
    async def _validate_agent_access(self, agent_id: str, user: UserResponse, logger) -> None:
        """
        Validate that the user has permission to access data for the specified agent.
        
        Args:
            agent_id: Agent identifier to validate access for
            user: Current authenticated user
            logger: Bound logger for context
            
        Raises:
            PermissionError: If user doesn't have access to the agent
        """
        # For now, implement basic validation
        # In a production system, this would check user permissions against agent ownership
        # or organization membership
        
        if not agent_id or not agent_id.strip():
            raise PermissionError("Invalid agent identifier")
        
        # Basic user validation
        if not user or not user.id:
            raise PermissionError("Invalid user authentication")
        
        # For MVP, allow all authenticated users to access all agents
        # This should be replaced with proper authorization logic
        logger.debug("Agent access validated", extra={
            "agent_id": agent_id,
            "user_id": user.id
        })
    
    async def _validate_system_access(self, system_id: str, user: UserResponse, logger) -> None:
        """
        Validate that the user has permission to access data for the specified system.
        
        Args:
            system_id: System identifier to validate access for
            user: Current authenticated user
            logger: Bound logger for context
            
        Raises:
            PermissionError: If user doesn't have access to the system
        """
        # For now, implement basic validation
        # In a production system, this would check user permissions against system ownership
        # or organization membership
        
        if not system_id or not system_id.strip():
            raise PermissionError("Invalid system identifier")
        
        # Basic user validation
        if not user or not user.id:
            raise PermissionError("Invalid user authentication")
        
        # For MVP, allow all authenticated users to access all systems
        # This should be replaced with proper authorization logic
        logger.debug("System access validated", extra={
            "system_id": system_id,
            "user_id": user.id
        })


class TelemetryControllerFactory:
    """Factory for creating TelemetryController instances with dependency injection."""
    
    @staticmethod
    async def create_controller(
        telemetry_service: TelemetryService = Depends()
    ) -> TelemetryController:
        """
        Create a TelemetryController instance with injected dependencies.
        
        Args:
            telemetry_service: Injected telemetry service instance
            
        Returns:
            TelemetryController: Configured controller instance
        """
        return TelemetryController(telemetry_service) 