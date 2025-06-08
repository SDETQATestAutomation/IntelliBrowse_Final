"""
Notification Engine Health Check Routes
Provides monitoring and observability endpoints for notification system health.
Part of Phase 6 - Final Integration & Testing
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
import asyncio
from datetime import datetime, timezone

from ..controllers.notification_controller import NotificationController
from ...auth.dependencies.auth_dependency import get_current_user_from_context
from ...schemas.response import create_success_response
from ..schemas.notification_schemas import NotificationHealthResponse

router = APIRouter(
    prefix="/health",
    tags=["Notification Health"],
    responses={
        500: {"description": "Internal server error"},
        503: {"description": "Service unavailable"},
    }
)


@router.get(
    "/status",
    response_model=Dict[str, Any],
    summary="Notification Engine Health Status",
    description="Get comprehensive health status of the notification engine and all components",
    responses={
        200: {
            "description": "Health status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Notification engine health status retrieved",
                        "data": {
                            "overall_status": "healthy",
                            "timestamp": "2025-01-06T20:00:00Z",
                            "components": {
                                "delivery_daemon": {"status": "healthy", "last_check": "2025-01-06T19:59:45Z"},
                                "email_adapter": {"status": "healthy", "success_rate": 99.5},
                                "websocket_adapter": {"status": "healthy", "active_connections": 150},
                                "database": {"status": "healthy", "latency_ms": 12}
                            },
                            "metrics": {
                                "notifications_sent_24h": 1250,
                                "success_rate": 99.2,
                                "average_delivery_time_ms": 450
                            }
                        }
                    }
                }
            }
        }
    }
)
async def get_notification_health_status(
    controller: NotificationController = Depends(NotificationController)
) -> Dict[str, Any]:
    """
    Get comprehensive health status of notification engine.
    
    Returns:
        Dict containing health status of all notification components
    """
    try:
        health_status = await controller.get_health_status()
        
        return create_success_response(
            message="Notification engine health status retrieved",
            data=health_status
        ).model_dump()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to retrieve health status: {str(e)}"
        )


@router.get(
    "/metrics",
    response_model=Dict[str, Any],
    summary="Notification Engine Performance Metrics",
    description="Get detailed performance metrics for notification delivery and system performance",
    responses={
        200: {
            "description": "Performance metrics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Notification performance metrics retrieved",
                        "data": {
                            "delivery_metrics": {
                                "total_sent": 1250,
                                "successful": 1240,
                                "failed": 10,
                                "pending": 5,
                                "success_rate": 99.2
                            },
                            "channel_performance": {
                                "email": {"sent": 800, "success_rate": 99.5, "avg_delivery_ms": 2500},
                                "websocket": {"sent": 400, "success_rate": 99.8, "avg_delivery_ms": 50},
                                "webhook": {"sent": 50, "success_rate": 98.0, "avg_delivery_ms": 1200}
                            },
                            "time_period": "24h"
                        }
                    }
                }
            }
        }
    }
)
async def get_notification_metrics(
    controller: NotificationController = Depends(NotificationController)
) -> Dict[str, Any]:
    """
    Get detailed performance metrics for notification system.
    
    Returns:
        Dict containing performance metrics and delivery statistics
    """
    try:
        metrics = await controller.get_performance_metrics()
        
        return create_success_response(
            message="Notification performance metrics retrieved",
            data=metrics
        ).model_dump()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to retrieve performance metrics: {str(e)}"
        )


@router.get(
    "/daemon",
    response_model=Dict[str, Any],
    summary="Delivery Daemon Status",
    description="Get specific status and health information for the notification delivery daemon",
    responses={
        200: {
            "description": "Daemon status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Delivery daemon status retrieved",
                        "data": {
                            "daemon_status": "running",
                            "uptime_seconds": 3600,
                            "last_heartbeat": "2025-01-06T19:59:55Z",
                            "processing_queue_size": 15,
                            "concurrent_workers": 5,
                            "failed_deliveries_1h": 2,
                            "health_checks": {
                                "database": True,
                                "email_service": True,
                                "webhook_endpoints": True
                            }
                        }
                    }
                }
            }
        }
    }
)
async def get_daemon_status(
    controller: NotificationController = Depends(NotificationController)
) -> Dict[str, Any]:
    """
    Get detailed status of the notification delivery daemon.
    
    Returns:
        Dict containing daemon status and operational metrics
    """
    try:
        daemon_status = await controller.get_daemon_status()
        
        return create_success_response(
            message="Delivery daemon status retrieved",
            data=daemon_status
        ).model_dump()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to retrieve daemon status: {str(e)}"
        )


@router.post(
    "/restart-daemon",
    response_model=Dict[str, Any],
    summary="Restart Delivery Daemon",
    description="Restart the notification delivery daemon (admin only)",
    dependencies=[Depends(get_current_user_from_context)],
    responses={
        200: {
            "description": "Daemon restart initiated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Delivery daemon restart initiated",
                        "data": {
                            "restart_initiated": True,
                            "timestamp": "2025-01-06T20:00:00Z",
                            "estimated_downtime_seconds": 30
                        }
                    }
                }
            }
        }
    }
)
async def restart_delivery_daemon(
    user_context = Depends(get_current_user_from_context),
    controller: NotificationController = Depends(NotificationController)
) -> Dict[str, Any]:
    """
    Restart the notification delivery daemon.
    Requires admin privileges.
    
    Returns:
        Dict containing restart status and timing information
    """
    try:
        # Verify admin privileges
        if not user_context.get("is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required to restart daemon"
            )
        
        restart_result = await controller.restart_daemon()
        
        return create_success_response(
            message="Delivery daemon restart initiated",
            data=restart_result
        ).model_dump()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart daemon: {str(e)}"
        )


@router.get(
    "/channels",
    response_model=Dict[str, Any],
    summary="Channel Adapter Status",
    description="Get status and health information for all notification channel adapters",
    responses={
        200: {
            "description": "Channel status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Channel adapter status retrieved",
                        "data": {
                            "channels": {
                                "email": {
                                    "status": "healthy",
                                    "provider": "sendgrid",
                                    "last_success": "2025-01-06T19:58:30Z",
                                    "error_rate": 0.5
                                },
                                "websocket": {
                                    "status": "healthy",
                                    "active_connections": 150,
                                    "last_success": "2025-01-06T19:59:45Z",
                                    "error_rate": 0.2
                                },
                                "webhook": {
                                    "status": "degraded",
                                    "active_endpoints": 8,
                                    "last_success": "2025-01-06T19:57:20Z",
                                    "error_rate": 2.0
                                }
                            }
                        }
                    }
                }
            }
        }
    }
)
async def get_channel_status(
    controller: NotificationController = Depends(NotificationController)
) -> Dict[str, Any]:
    """
    Get status of all notification channel adapters.
    
    Returns:
        Dict containing status of each channel adapter
    """
    try:
        channel_status = await controller.get_channel_status()
        
        return create_success_response(
            message="Channel adapter status retrieved",
            data=channel_status
        ).model_dump()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to retrieve channel status: {str(e)}"
        ) 