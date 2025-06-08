"""
Scheduled Task Runner Engine - Main Package

Implements a comprehensive scheduled task runner for IntelliBrowse with support
for time-based, event-driven, and dependency-based triggers. Provides full
HTTP API interface with JWT authentication and comprehensive monitoring.

Key Components:
- Models: Database models and enums for triggers and jobs
- Schemas: Pydantic request/response schemas with validation
- Services: Business logic layer with async/await patterns
- Controllers: HTTP orchestration layer with error handling
- Routes: FastAPI endpoints with OpenAPI documentation
- Engines: Core orchestration engine for task execution

Architecture:
- Clean separation of concerns across layers
- Async/await patterns throughout
- Comprehensive error handling and logging
- JWT authentication and authorization
- MongoDB integration with optimized indexing
"""

# Core models and enums
from .models import (
    ScheduledTriggerModel,
    ScheduledJobModel,
    ExecutionLockModel,
    TaskStatus,
    ExecutionStatus,
    TriggerType
)

# Request/response schemas
from .schemas import (
    CreateScheduledTriggerRequest,
    UpdateScheduledTriggerRequest,
    ScheduledTriggerResponse,
    ExecutionStatusResponse,
    ExecutionHistoryResponse,
    BaseResponseSchema
)

# Business logic services
from .services import (
    SchedulerService,
    SchedulerServiceFactory,
    BaseSchedulerService,
    TriggerEngineService,
    LockManagerService,
    JobExecutionService
)

# HTTP controllers
from .controllers import (
    SchedulerController,
    SchedulerControllerFactory
)

# FastAPI routes
from .routes import router

# Core orchestration engine
from .engines import (
    TaskOrchestrationEngine,
    create_task_orchestration_engine,
    task_orchestration_engine_context
)

__all__ = [
    # Models and enums
    "ScheduledTriggerModel",
    "ScheduledJobModel", 
    "ExecutionLockModel",
    "TaskStatus",
    "ExecutionStatus",
    "TriggerType",
    
    # Schemas
    "CreateScheduledTriggerRequest",
    "UpdateScheduledTriggerRequest",
    "ScheduledTriggerResponse",
    "ExecutionStatusResponse",
    "ExecutionHistoryResponse",
    "BaseResponseSchema",
    
    # Services
    "SchedulerService",
    "SchedulerServiceFactory",
    "BaseSchedulerService",
    "TriggerEngineService",
    "LockManagerService",
    "JobExecutionService",
    
    # Controllers
    "SchedulerController",
    "SchedulerControllerFactory",
    
    # Routes
    "router",
    
    # Engines
    "TaskOrchestrationEngine",
    "create_task_orchestration_engine",
    "task_orchestration_engine_context"
] 