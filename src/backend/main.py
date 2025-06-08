"""
FastAPI application entry point for IntelliBrowse backend.
Integrates all components with clean architecture and proper configuration.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .config.constants import (
    APP_NAME,
    APP_DESCRIPTION,
    APP_VERSION,
    DOCS_URL,
    REDOC_URL,
    OPENAPI_URL,
)
from .config.env import get_settings
from .config.logging import (
    logger,
    log_request_start,
    log_request_end,
    log_error,
    log_security_event,
    setup_logging,
)
from .routes.health import router as health_router
from .auth import auth_router
from .schemas.response import create_error_response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    settings = get_settings()
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Initialize database connection
    try:
        from .auth.services.database_service import get_database_service
        db_service = get_database_service()
        await db_service.connect()
        
        # Store database reference in app state for dependency injection
        app.state.db = db_service.database
        
        logger.info("Database connection initialized successfully")
        
        # Initialize test item indexes for optimal performance
        try:
            from .testitems.services.test_item_service import TestItemService
            test_item_service = TestItemService(app.state.db)
            await test_item_service.ensure_indexes()
            logger.info("Test item collection indexes initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize test item indexes: {e}")
            # Don't fail startup for index issues
        
        # Initialize test suite indexes for optimal performance
        try:
            from .testsuites.models.indexes import ensure_test_suite_indexes
            # Get MongoDB client from database service
            mongo_client = db_service.client
            index_results = await ensure_test_suite_indexes(mongo_client)
            
            if index_results["success"]:
                logger.info(
                    f"Test suite collection indexes initialized successfully. "
                    f"Created: {len(index_results['indexes_created'])}, "
                    f"Skipped: {len(index_results['indexes_skipped'])}"
                )
            else:
                logger.warning(
                    f"Test suite index creation completed with errors: {index_results['errors']}"
                )
                
        except Exception as e:
            logger.warning(f"Failed to initialize test suite indexes: {e}")
            # Don't fail startup for index issues
        
        # Initialize test case indexes for optimal performance
        try:
            from .testcases.models.test_case_model import TestCaseModelOperations
            # Get MongoDB client from database service
            mongo_client = db_service.client
            await TestCaseModelOperations.ensure_indexes(mongo_client)
            logger.info("Test case collection indexes initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize test case indexes: {e}")
            # Don't fail startup for index issues
        
        # Initialize test execution indexes for optimal performance
        try:
            from .testexecution.models.execution_trace_model import ExecutionTraceModelOperations
            # Get MongoDB client from database service
            mongo_client = db_service.client
            await ExecutionTraceModelOperations.ensure_indexes(mongo_client)
            logger.info("Test execution collection indexes initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize test execution indexes: {e}")
            # Don't fail startup for index issues
        
        # Initialize notification indexes for optimal performance - PHASE 6 INTEGRATION
        try:
            from .notification.utils.mongodb_setup import ensure_notification_indexes
            # Get MongoDB client from database service  
            mongo_client = db_service.client
            await ensure_notification_indexes(mongo_client)
            logger.info("Notification collection indexes initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize notification indexes: {e}")
            # Don't fail startup for index issues
        
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {str(e)}")
        # Don't fail startup for database issues (allow app to start)
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {APP_NAME}")
    
    # Close database connection
    try:
        db_service = get_database_service()
        await db_service.disconnect()
        logger.info("Database connection closed successfully")
    except Exception as e:
        logger.error(f"Error closing database connection: {str(e)}")


# Create FastAPI application instance
def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()
    
    # Create FastAPI app with configuration
    app = FastAPI(
        title=APP_NAME,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        docs_url=DOCS_URL,
        redoc_url=REDOC_URL,
        openapi_url=OPENAPI_URL,
        debug=settings.debug,
        lifespan=lifespan,
    )
    
    # Configure middleware
    configure_middleware(app, settings)
    
    # Configure exception handlers
    configure_exception_handlers(app)
    
    # Configure request logging middleware
    configure_request_logging(app)
    
    # Configure routes
    configure_routes(app)
    
    return app


def configure_middleware(app: FastAPI, settings) -> None:
    """
    Configure FastAPI middleware.
    
    Args:
        app: FastAPI application instance
        settings: Application settings
    """
    # CORS middleware
    if settings.enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.get_cors_origins(),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )
        logger.info(f"CORS configured with origins: {settings.get_cors_origins()}")
    
    # Trusted host middleware (security)
    if settings.is_production():
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
        )
        logger.info("Trusted host middleware configured for production")


def configure_exception_handlers(app: FastAPI) -> None:
    """
    Configure global exception handlers.
    
    Args:
        app: FastAPI application instance
    """
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions with structured logging."""
        request_id = getattr(request.state, "request_id", "unknown")
        
        log_error(
            error=exc,
            context="http_exception",
            request_id=request_id,
            extra_details={
                "status_code": exc.status_code,
                "path": str(request.url),
                "method": request.method,
            }
        )
        
        error_response = create_error_response(
            message=exc.detail,
            error_code=f"HTTP_{exc.status_code}",
            error_details={
                "status_code": exc.status_code,
                "path": str(request.url),
                "method": request.method,
            }
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions with fallback response."""
        request_id = getattr(request.state, "request_id", "unknown")
        
        log_error(
            error=exc,
            context="general_exception",
            request_id=request_id,
            extra_details={
                "path": str(request.url),
                "method": request.method,
                "exception_type": type(exc).__name__,
            }
        )
        
        # Don't expose internal errors in production
        settings = get_settings()
        if settings.is_production():
            message = "An internal error occurred"
            error_details = None
        else:
            message = f"Internal server error: {str(exc)}"
            error_details = {
                "exception_type": type(exc).__name__,
                "path": str(request.url),
                "method": request.method,
            }
        
        error_response = create_error_response(
            message=message,
            error_code="INTERNAL_SERVER_ERROR",
            error_details=error_details
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump()
        )


def configure_request_logging(app: FastAPI) -> None:
    """
    Configure request/response logging middleware.
    
    Args:
        app: FastAPI application instance
    """
    
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        """Log requests and responses with timing."""
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Log request start
        start_time = time.time()
        log_request_start(
            request_id=request_id,
            method=request.method,
            path=str(request.url),
            client_ip=client_ip
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log request completion
            log_request_end(
                request_id=request_id,
                method=request.method,
                path=str(request.url),
                status_code=response.status_code,
                duration_ms=duration_ms
            )
            
            # Add request ID to response headers for debugging
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Log request error
            duration_ms = (time.time() - start_time) * 1000
            log_request_end(
                request_id=request_id,
                method=request.method,
                path=str(request.url),
                status_code=500,
                duration_ms=duration_ms
            )
            raise


def configure_routes(app: FastAPI) -> None:
    """
    Configure application routes.
    
    Args:
        app: FastAPI application instance
    """
    settings = get_settings()
    
    # Include health router (no prefix for health checks)
    app.include_router(health_router)
    logger.info("Health routes configured")
    
    # Include authentication router with API prefix
    app.include_router(auth_router, prefix=settings.api_prefix)
    logger.info(f"Authentication routes configured with prefix: {settings.api_prefix}/auth")
    
    # Include test item router with API prefix
    try:
        from .testitems.routes.test_item_routes import router as test_item_router
        app.include_router(test_item_router, prefix=settings.api_prefix)
        logger.info(f"Test item routes configured with prefix: {settings.api_prefix}/test-items")
    except Exception as e:
        logger.error(f"Failed to configure test item routes: {e}")
        # Don't fail startup for route configuration issues
    
    # Include test suite router with API prefix
    try:
        from .testsuites.routes.test_suite_routes import router as test_suite_router
        app.include_router(test_suite_router, prefix=settings.api_prefix)
        logger.info(f"Test suite routes configured with prefix: {settings.api_prefix}/suites")
    except Exception as e:
        logger.error(f"Failed to configure test suite routes: {e}")
        # Don't fail startup for route configuration issues
    
    # Include test case router with API prefix
    try:
        from .testcases.routes.test_case_routes import router as test_case_router
        app.include_router(test_case_router, prefix=settings.api_prefix)
        logger.info(f"Test case routes configured with prefix: {settings.api_prefix}/testcases")
    except Exception as e:
        logger.error(f"Failed to configure test case routes: {e}")
        # Don't fail startup for route configuration issues
    
    # Include test execution router with API prefix
    try:
        from .testexecution.routes.execution_routes import router as execution_router
        app.include_router(execution_router, prefix=settings.api_prefix)
        logger.info(f"Test execution routes configured with prefix: {settings.api_prefix}/executions")
    except Exception as e:
        logger.error(f"Failed to configure test execution routes: {e}")
        # Don't fail startup for route configuration issues
    
    # Include execution reporting router with API prefix
    try:
        from .executionreporting.routes.execution_reporting_routes import router as reporting_router
        app.include_router(reporting_router, prefix=settings.api_prefix)
        logger.info(f"Execution reporting routes configured with prefix: {settings.api_prefix}/execution-reporting")
    except Exception as e:
        logger.error(f"Failed to configure execution reporting routes: {e}")
        # Don't fail startup for route configuration issues

    # Include notification router with API prefix - PHASE 6 INTEGRATION
    try:
        from .notification.routes.notification_routes import router as notification_router
        app.include_router(notification_router, prefix=settings.api_prefix)
        logger.info(f"Notification routes configured with prefix: {settings.api_prefix}/notifications")
    except Exception as e:
        logger.error(f"Failed to configure notification routes: {e}")
        # Don't fail startup for route configuration issues


# Create the application instance
app = create_application()


# Root endpoint for basic API information
@app.get(
    "/",
    summary="API Root",
    description="Get basic API information and status",
    responses={
        200: {
            "description": "API information",
            "content": {
                "application/json": {
                    "example": {
                        "name": "IntelliBrowse",
                        "version": "1.0.0",
                        "description": "A modern enterprise-grade full-stack web application",
                        "status": "running",
                        "docs_url": "/docs",
                        "health_url": "/health"
                    }
                }
            }
        }
    },
)
async def root():
    """
    Get basic API information.
    
    Returns:
        dict: Basic API information and helpful links
    """
    settings = get_settings()
    
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "description": APP_DESCRIPTION,
        "status": "running",
        "environment": settings.environment,
        "docs_url": DOCS_URL,
        "health_url": "/health",
        "timestamp": time.time(),
    }


if __name__ == "__main__":
    import uvicorn
    
    # Run the application directly
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    ) 