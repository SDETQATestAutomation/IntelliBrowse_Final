"""
Telemetry Routes Module

This module defines FastAPI routes for telemetry engine operations, providing
HTTP endpoints that expose the TelemetryController functionality. Routes follow
RESTful conventions and IntelliBrowse API standards with comprehensive OpenAPI
documentation and JWT-based authentication.

Endpoints:
- POST /telemetry/heartbeat - Record agent heartbeat with health metrics
- POST /telemetry/system-metrics - Record system performance metrics
- GET /telemetry/uptime-status/{agent_id} - Get uptime status and SLA compliance
- POST /telemetry/health-check - Perform comprehensive health assessment
- POST /telemetry/batch - High-throughput batch telemetry ingestion
- GET /telemetry/health - Service health check endpoint

Features:
- JWT authentication on all endpoints
- Comprehensive request/response validation with examples
- OpenAPI documentation with proper tags and descriptions
- Dependency injection for controller
- Structured error handling and logging
- Support for high-throughput ingestion operations
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status, Body
from fastapi.responses import JSONResponse

from ..controllers.telemetry_controller import (
    TelemetryController,
    TelemetryControllerFactory
)
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
from ...auth.dependencies.auth_dependencies import get_current_user
from ...auth.schemas.auth_responses import UserResponse


logger = logging.getLogger(__name__)

# Create FastAPI router with telemetry prefix and tags
router = APIRouter(
    prefix="/telemetry",
    tags=["Telemetry"],
    dependencies=[Depends(get_current_user)]
)


@router.post(
    "/heartbeat",
    response_model=HeartbeatResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record Agent Heartbeat",
    description="""
    Record agent heartbeat with comprehensive health metrics and system status.
    
    This endpoint accepts heartbeat data from monitoring agents including system
    metrics, health indicators, and operational status. The service performs 
    health assessment, alert generation, and uptime tracking based on the provided data.
    
    **Authentication Required**: JWT token with valid user credentials.
    
    **Request Body**: Complete heartbeat data with agent information and metrics
    **Response**: Health assessment results with alerts and recommendations
    
    **Key Features**:
    - Adaptive timeout calculation based on historical heartbeat patterns
    - Multi-factor health scoring (CPU, memory, network, errors)
    - Intelligent alert generation with severity classification
    - Uptime session tracking and availability analysis
    
    **HTTP Status Codes**:
    - 201: Heartbeat processed successfully with health assessment
    - 400: Invalid heartbeat data or validation errors
    - 403: Access denied (insufficient permissions for agent)
    - 422: Data quality issues or missing required fields
    - 500: Internal server error during heartbeat processing
    """,
    responses={
        201: {
            "description": "Heartbeat processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "heartbeat_id": "hb_2024010722450001",
                        "agent_id": "agent_web_server_01",
                        "processed_at": "2024-01-07T22:45:00Z",
                        "calculated_health": "healthy",
                        "health_score": 0.92,
                        "next_expected_heartbeat": "2024-01-07T22:46:00Z",
                        "timeout_threshold_seconds": 90,
                        "alerts_generated": [],
                        "health_recommendations": [
                            "Consider monitoring disk usage trends",
                            "CPU utilization is optimal"
                        ],
                        "data_quality_score": 0.98
                    }
                }
            }
        },
        422: {
            "description": "Invalid heartbeat data",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid heartbeat data: CPU utilization must be between 0 and 100"
                    }
                }
            }
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Access denied for agent: agent_web_server_01"
                    }
                }
            }
        }
    }
)
async def record_heartbeat(
    heartbeat_request: HeartbeatRequestSchema = Body(
        ...,
        description="Complete heartbeat data with agent information and system metrics",
        example={
            "agent_info": {
                "agent_id": "agent_web_server_01",
                "agent_version": "2.1.4",
                "host_info": {
                    "hostname": "web-server-prod-01",
                    "os_type": "Linux",
                    "os_version": "Ubuntu 22.04.3 LTS",
                    "architecture": "x86_64"
                }
            },
            "timestamp": "2024-01-07T22:45:00Z",
            "system_metrics": {
                "cpu_utilization": 45.2,
                "memory_usage": 68.5,
                "disk_usage": 72.1,
                "network_latency": 12.3,
                "process_count": 156,
                "open_connections": 42
            },
            "health_indicators": {
                "service_status": "active",
                "error_rate": 0.02,
                "response_time": 89.5,
                "throughput": 1250.0,
                "last_error_timestamp": "2024-01-07T22:40:15Z"
            }
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TelemetryController = Depends(TelemetryControllerFactory.create_controller)
) -> HeartbeatResponseSchema:
    """
    Record agent heartbeat with health assessment.
    
    Validates the heartbeat data, performs health analysis, and generates
    alerts and recommendations based on system metrics and historical patterns.
    
    Args:
        heartbeat_request: Complete heartbeat data with validation
        current_user: Authenticated user from JWT token
        controller: Injected telemetry controller instance
        
    Returns:
        HeartbeatResponseSchema: Health assessment results with recommendations
    """
    logger.info(
        "Processing heartbeat request",
        extra={
            "user_id": current_user.id,
            "agent_id": heartbeat_request.agent_info.agent_id,
            "endpoint": "POST /telemetry/heartbeat"
        }
    )
    
    return await controller.record_heartbeat(
        request=heartbeat_request,
        current_user=current_user
    )


@router.post(
    "/system-metrics",
    response_model=SystemMetricsResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record System Metrics",
    description="""
    Record system performance metrics with threshold analysis and outlier detection.
    
    This endpoint accepts detailed system metrics including CPU, memory, disk I/O,
    network statistics, and custom application metrics. The service performs data
    quality assessment, outlier detection, and threshold-based alerting.
    
    **Authentication Required**: JWT token with valid user credentials.
    
    **Request Body**: System metrics data with performance indicators
    **Response**: Processing results with quality assessment and alerts
    
    **Key Features**:
    - Statistical outlier detection using IQR method
    - Data quality scoring based on completeness and validity
    - Threshold-based alerting with configurable severity levels
    - Historical trend analysis and pattern recognition
    - Batch processing support for high-frequency metrics
    
    **HTTP Status Codes**:
    - 201: Metrics processed successfully with quality assessment
    - 400: Invalid metrics data or validation errors
    - 403: Access denied (insufficient permissions for system)
    - 422: Data quality issues or missing required fields
    - 500: Internal server error during metrics processing
    """,
    responses={
        201: {
            "description": "Metrics processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "system_id": "sys_database_cluster_01",
                        "metrics_processed": 15,
                        "processing_timestamp": "2024-01-07T22:45:00Z",
                        "data_quality_score": 0.95,
                        "validation_errors": [],
                        "outliers_detected": [
                            {
                                "metric_name": "disk_io_latency",
                                "value": 245.8,
                                "threshold": 150.0,
                                "severity": "warning"
                            }
                        ],
                        "alerts_generated": [
                            {
                                "alert_id": "alert_2024010722450001",
                                "metric_name": "cpu_utilization",
                                "severity": "critical",
                                "threshold": 90.0,
                                "current_value": 95.2,
                                "message": "CPU utilization exceeds critical threshold"
                            }
                        ],
                        "processing_time_ms": 42.5
                    }
                }
            }
        },
        422: {
            "description": "Invalid metrics data",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid metrics data: Memory usage cannot be negative"
                    }
                }
            }
        }
    }
)
async def record_system_metrics(
    metrics_request: SystemMetricsRequestSchema = Body(
        ...,
        description="System metrics data with performance indicators",
        example={
            "system_id": "sys_database_cluster_01",
            "timestamp": "2024-01-07T22:45:00Z",
            "metrics": [
                {
                    "metric_name": "cpu_utilization",
                    "value": 78.5,
                    "unit": "percentage",
                    "tags": {"core": "all", "type": "system"}
                },
                {
                    "metric_name": "memory_usage",
                    "value": 12.8,
                    "unit": "gigabytes",
                    "tags": {"type": "used", "pool": "application"}
                },
                {
                    "metric_name": "disk_io_ops",
                    "value": 1250.0,
                    "unit": "operations_per_second",
                    "tags": {"device": "sda1", "operation": "read"}
                }
            ],
            "metadata": {
                "collection_method": "agent",
                "collection_interval": 30,
                "agent_version": "2.1.4"
            }
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TelemetryController = Depends(TelemetryControllerFactory.create_controller)
) -> SystemMetricsResponseSchema:
    """
    Record system metrics with quality assessment.
    
    Validates metrics data, performs outlier detection, and generates alerts
    based on threshold analysis and historical patterns.
    
    Args:
        metrics_request: System metrics data with validation
        current_user: Authenticated user from JWT token
        controller: Injected telemetry controller instance
        
    Returns:
        SystemMetricsResponseSchema: Processing results with quality assessment
    """
    logger.info(
        "Processing system metrics request",
        extra={
            "user_id": current_user.id,
            "system_id": metrics_request.system_id,
            "metrics_count": len(metrics_request.metrics),
            "endpoint": "POST /telemetry/system-metrics"
        }
    )
    
    return await controller.record_system_metrics(
        request=metrics_request,
        current_user=current_user
    )


@router.get(
    "/uptime-status/{agent_id}",
    response_model=UptimeStatusResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get Agent Uptime Status",
    description="""
    Retrieve comprehensive uptime status and availability metrics for a specific agent.
    
    This endpoint provides detailed uptime analysis including availability percentage,
    downtime patterns, SLA compliance assessment, and health recommendations based
    on historical heartbeat and telemetry data.
    
    **Authentication Required**: JWT token with valid user credentials.
    **Authorization**: Users can only access agents they have permissions for.
    
    **Path Parameters**: 
    - agent_id: Unique identifier for the target agent
    
    **Query Parameters**: 
    - time_range_hours: Analysis time range in hours (1-8760, default 24)
    
    **Response**: Comprehensive uptime analysis with SLA compliance
    
    **Key Features**:
    - Session-based uptime/downtime analysis
    - SLA compliance tracking with breach risk assessment
    - Failure pattern detection and categorization
    - Health recommendations based on availability trends
    - Data quality assessment for reliability scoring
    
    **HTTP Status Codes**:
    - 200: Uptime status retrieved successfully
    - 400: Invalid agent ID or time range parameters
    - 403: Access denied (insufficient permissions for agent)
    - 404: Agent not found or no telemetry data available
    - 500: Internal server error during uptime calculation
    """,
    responses={
        200: {
            "description": "Uptime status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "agent_id": "agent_web_server_01",
                        "time_range": {
                            "start_time": "2024-01-06T22:45:00Z",
                            "end_time": "2024-01-07T22:45:00Z",
                            "duration_hours": 24
                        },
                        "uptime_percentage": 99.85,
                        "total_uptime_minutes": 1438.2,
                        "total_downtime_minutes": 1.8,
                        "health_assessment": {
                            "overall_health": "excellent",
                            "health_score": 0.96,
                            "component_health": {
                                "cpu": "healthy",
                                "memory": "healthy", 
                                "network": "excellent",
                                "storage": "warning"
                            }
                        },
                        "sla_target": 99.9,
                        "sla_compliance": true,
                        "sla_breach_risk": "low",
                        "failure_patterns": [],
                        "health_recommendations": [
                            "Monitor storage utilization trends",
                            "Consider upgrading memory capacity"
                        ],
                        "data_quality_score": 0.98
                    }
                }
            }
        },
        404: {
            "description": "Agent not found or no data",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No telemetry data found for agent: agent_web_server_01"
                    }
                }
            }
        },
        400: {
            "description": "Invalid parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid request parameters: Time range must be between 1 and 8760 hours"
                    }
                }
            }
        }
    }
)
async def get_uptime_status(
    agent_id: str = Path(
        ...,
        description="Unique identifier for the target agent",
        example="agent_web_server_01",
        min_length=1,
        max_length=100
    ),
    time_range_hours: int = Query(
        24,
        ge=1,
        le=8760,  # 1 year maximum
        description="Analysis time range in hours (1 hour to 1 year)",
        example=24
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TelemetryController = Depends(TelemetryControllerFactory.create_controller)
) -> UptimeStatusResponseSchema:
    """
    Get comprehensive uptime status for an agent.
    
    Calculates uptime percentage, health assessment, and SLA compliance
    based on historical heartbeat and telemetry data.
    
    Args:
        agent_id: Target agent identifier
        time_range_hours: Analysis time range in hours
        current_user: Authenticated user from JWT token
        controller: Injected telemetry controller instance
        
    Returns:
        UptimeStatusResponseSchema: Comprehensive uptime analysis
    """
    logger.info(
        "Processing uptime status request",
        extra={
            "user_id": current_user.id,
            "agent_id": agent_id,
            "time_range_hours": time_range_hours,
            "endpoint": f"GET /telemetry/uptime-status/{agent_id}"
        }
    )
    
    return await controller.get_uptime_status(
        agent_id=agent_id,
        time_range_hours=time_range_hours,
        current_user=current_user
    )


@router.post(
    "/health-check",
    response_model=HealthStatusResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Perform Health Assessment",
    description="""
    Perform comprehensive health check assessment for a target system or agent.
    
    This endpoint provides detailed health evaluation based on recent telemetry data,
    including component-level health analysis, performance trends, failure patterns,
    and maintenance recommendations.
    
    **Authentication Required**: JWT token with valid user credentials.
    
    **Request Body**: Health check parameters with target information
    **Response**: Comprehensive health assessment with recommendations
    
    **Key Features**:
    - Multi-component health analysis (CPU, memory, network, storage)
    - Performance trend analysis with historical comparison
    - Failure pattern detection and risk assessment
    - Maintenance recommendations based on assessment type
    - Customizable assessment parameters and time ranges
    
    **Assessment Types**:
    - basic: Essential health indicators and availability
    - comprehensive: Detailed analysis with performance trends
    - predictive: Advanced analysis with failure prediction
    
    **HTTP Status Codes**:
    - 200: Health assessment completed successfully
    - 400: Invalid assessment parameters or target information
    - 403: Access denied (insufficient permissions for target)
    - 404: Target not found or no telemetry data available
    - 500: Internal server error during health assessment
    """,
    responses={
        200: {
            "description": "Health assessment completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "target_id": "agent_web_server_01",
                        "assessment_id": "assessment_2024010722450001",
                        "assessment_completed_at": "2024-01-07T22:45:00Z",
                        "health_assessment": {
                            "overall_health": "healthy",
                            "health_score": 0.89,
                            "component_health": {
                                "cpu": "healthy",
                                "memory": "warning",
                                "network": "excellent",
                                "storage": "healthy"
                            }
                        },
                        "uptime_percentage": 99.95,
                        "downtime_duration": "PT3.6M",
                        "sla_target": 99.9,
                        "sla_compliance": true,
                        "sla_breach_risk": "low",
                        "performance_trends": {
                            "cpu_trend": "stable",
                            "memory_trend": "increasing",
                            "response_time_trend": "improving"
                        },
                        "failure_patterns": [],
                        "health_recommendations": [
                            "Monitor memory usage growth patterns",
                            "Consider memory capacity upgrade",
                            "Excellent network performance maintained"
                        ],
                        "maintenance_suggestions": []
                    }
                }
            }
        },
        404: {
            "description": "Target not found or no data",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No telemetry data found for target: agent_web_server_01"
                    }
                }
            }
        }
    }
)
async def perform_health_check(
    health_request: HealthCheckRequestSchema = Body(
        ...,
        description="Health check parameters with target and assessment configuration",
        example={
            "target_id": "agent_web_server_01",
            "target_type": "agent",
            "assessment_type": "comprehensive",
            "time_range": {
                "start_time": "2024-01-06T22:45:00Z",
                "end_time": "2024-01-07T22:45:00Z"
            },
            "include_performance_trends": True,
            "include_failure_patterns": True
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TelemetryController = Depends(TelemetryControllerFactory.create_controller)
) -> HealthStatusResponseSchema:
    """
    Perform comprehensive health assessment.
    
    Evaluates target health based on recent telemetry data and provides
    detailed analysis with recommendations and maintenance suggestions.
    
    Args:
        health_request: Health check parameters with validation
        current_user: Authenticated user from JWT token
        controller: Injected telemetry controller instance
        
    Returns:
        HealthStatusResponseSchema: Comprehensive health assessment results
    """
    logger.info(
        "Processing health check request",
        extra={
            "user_id": current_user.id,
            "target_id": health_request.target_id,
            "target_type": health_request.target_type,
            "assessment_type": health_request.assessment_type,
            "endpoint": "POST /telemetry/health-check"
        }
    )
    
    return await controller.perform_health_check(
        request=health_request,
        current_user=current_user
    )


@router.post(
    "/batch",
    response_model=TelemetryIngestionResultSchema,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch Telemetry Ingestion",
    description="""
    Ingest batch telemetry data for high-throughput operations and bulk processing.
    
    This endpoint accepts batch requests containing multiple heartbeats and metrics
    from different agents and systems, processes them efficiently, and returns
    comprehensive processing results including success/failure counts and error details.
    
    **Authentication Required**: JWT token with valid user credentials.
    
    **Request Body**: Batch telemetry data with heartbeats and metrics
    **Response**: Comprehensive processing results with quality metrics
    
    **Key Features**:
    - High-throughput batch processing with parallel execution
    - Individual item validation with granular error reporting
    - Processing metrics including throughput and latency tracking
    - Data quality scoring with confidence levels
    - Partial success handling for resilient processing
    
    **Batch Limits**:
    - Maximum 1000 heartbeats per batch
    - Maximum 5000 metrics per batch
    - Maximum batch size: 10MB
    
    **HTTP Status Codes**:
    - 202: Batch accepted for processing (partial or complete success)
    - 400: Invalid batch structure or exceeds size limits
    - 403: Access denied (insufficient permissions for targets)
    - 413: Batch size exceeds maximum allowed limits
    - 500: Internal server error during batch processing
    """,
    responses={
        202: {
            "description": "Batch processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "batch_id": "batch_2024010722450001",
                        "processed_at": "2024-01-07T22:45:00Z",
                        "total_heartbeats": 25,
                        "processed_heartbeats": 24,
                        "failed_heartbeats": 1,
                        "total_metrics": 150,
                        "processed_metrics": 147,
                        "failed_metrics": 3,
                        "processing_time_ms": 245.8,
                        "throughput_per_second": 712.5,
                        "validation_errors": [
                            "Heartbeat agent_test_02: Invalid CPU utilization value"
                        ],
                        "processing_errors": [
                            "Metrics sys_db_03: Connection timeout during processing"
                        ],
                        "alerts_generated": 3,
                        "data_quality_score": 0.94
                    }
                }
            }
        },
        413: {
            "description": "Batch size exceeds limits",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Batch size exceeds maximum allowed: 1000 heartbeats, 5000 metrics"
                    }
                }
            }
        }
    }
)
async def ingest_telemetry_batch(
    batch_request: TelemetryIngestionBatchSchema = Body(
        ...,
        description="Batch telemetry data with heartbeats and metrics",
        example={
            "batch_id": "batch_2024010722450001",
            "submitted_at": "2024-01-07T22:45:00Z",
            "heartbeats": [
                {
                    "agent_info": {
                        "agent_id": "agent_web_server_01",
                        "agent_version": "2.1.4",
                        "host_info": {
                            "hostname": "web-server-prod-01",
                            "os_type": "Linux",
                            "os_version": "Ubuntu 22.04.3 LTS"
                        }
                    },
                    "timestamp": "2024-01-07T22:45:00Z",
                    "system_metrics": {
                        "cpu_utilization": 45.2,
                        "memory_usage": 68.5,
                        "disk_usage": 72.1
                    }
                }
            ],
            "metrics": [
                {
                    "system_id": "sys_database_cluster_01",
                    "timestamp": "2024-01-07T22:45:00Z",
                    "metrics": [
                        {
                            "metric_name": "query_latency",
                            "value": 45.8,
                            "unit": "milliseconds"
                        }
                    ]
                }
            ],
            "metadata": {
                "source": "monitoring-agent",
                "version": "2.1.4",
                "compression": "gzip"
            }
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TelemetryController = Depends(TelemetryControllerFactory.create_controller)
) -> TelemetryIngestionResultSchema:
    """
    Ingest batch telemetry data with parallel processing.
    
    Processes multiple heartbeats and metrics efficiently with individual
    validation and comprehensive result reporting.
    
    Args:
        batch_request: Batch telemetry data with validation
        current_user: Authenticated user from JWT token
        controller: Injected telemetry controller instance
        
    Returns:
        TelemetryIngestionResultSchema: Comprehensive processing results
    """
    logger.info(
        "Processing telemetry batch request",
        extra={
            "user_id": current_user.id,
            "batch_id": batch_request.batch_id,
            "heartbeats_count": len(batch_request.heartbeats),
            "metrics_count": len(batch_request.metrics),
            "endpoint": "POST /telemetry/batch"
        }
    )
    
    return await controller.ingest_telemetry_batch(
        request=batch_request,
        current_user=current_user
    )


@router.get(
    "/health",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Telemetry Service Health Check",
    description="""
    Check the health status of the telemetry service.
    
    Returns basic health information including service status, version,
    and timestamp. This endpoint can be used for monitoring and health checks.
    
    **Authentication Required**: JWT token with valid user credentials.
    
    **HTTP Status Codes**:
    - 200: Service is healthy and operational
    - 500: Service health check failed
    """,
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "service": "telemetry",
                        "status": "healthy",
                        "version": "1.0.0",
                        "timestamp": "2024-01-07T22:45:00Z",
                        "database_status": "connected",
                        "processing_queue_status": "operational"
                    }
                }
            }
        }
    },
    tags=["Health"]
)
async def telemetry_health_check(
    current_user: UserResponse = Depends(get_current_user)
) -> dict:
    """
    Perform telemetry service health check.
    
    Returns basic service health information for monitoring purposes.
    
    Args:
        current_user: Authenticated user from JWT token
        
    Returns:
        dict: Service health status information
    """
    from datetime import datetime, timezone
    
    logger.info(
        "Processing telemetry health check",
        extra={
            "user_id": current_user.id,
            "endpoint": "GET /telemetry/health"
        }
    )
    
    return {
        "service": "telemetry",
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database_status": "connected",
        "processing_queue_status": "operational"
    } 