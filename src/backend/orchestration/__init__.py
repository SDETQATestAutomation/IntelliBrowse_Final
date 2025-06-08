"""
Orchestration & Recovery Engine Module

Implements distributed test execution coordination with intelligent retry strategies,
fault-tolerant recovery, and seamless integration with existing IntelliBrowse modules.

Core components:
- Models: OrchestrationJobModel, RetryPolicyModel, RecoveryAuditModel
- Schemas: API validation and response schemas for all orchestration operations
- Services: JobSchedulerService, RetryManagerService, RecoveryProcessorService
- Engine: DAGExecutionEngine, NodeRunnerService, ExecutionStateTracker
- Base Infrastructure: Service framework with dependency injection and lifecycle management
"""

from .models import (
    OrchestrationJobModel,
    OrchestrationNodeModel,
    RetryPolicyModel,
    RecoveryAuditModel,
    JobStatus,
    NodeType,
    RetryStrategy,
    RecoveryAction
)

from .schemas import (
    CreateOrchestrationJobRequest,
    JobStatusResponse,
    CreateRetryPolicyRequest,
    RetryPolicyResponse,
    RecoveryAuditResponse,
    OrchestrationResponse
)

from .services import (
    BaseOrchestrationService,
    JobSchedulerService,
    RetryManagerService,
    RecoveryProcessorService,
    ServiceConfiguration,
    ServiceLifecycle
)

from .engine import (
    DAGExecutionEngine,
    NodeRunnerService,
    ExecutionStateTracker
)

from .controllers import (
    OrchestrationController,
    JobCancellationError,
    OrchestrationControllerFactory
)

from .routes import (
    router
)

__version__ = "1.0.0"
__author__ = "IntelliBrowse Team"
__module__ = "orchestration"

__all__ = [
    # Models
    "OrchestrationJobModel",
    "OrchestrationNodeModel", 
    "RetryPolicyModel",
    "RecoveryAuditModel",
    "JobStatus",
    "NodeType",
    "RetryStrategy",
    "RecoveryAction",
    
    # Schemas
    "CreateOrchestrationJobRequest",
    "JobStatusResponse",
    "CreateRetryPolicyRequest", 
    "RetryPolicyResponse",
    "RecoveryAuditResponse",
    "OrchestrationResponse",
    
    # Services
    "BaseOrchestrationService",
    "JobSchedulerService",
    "RetryManagerService",
    "RecoveryProcessorService",
    "ServiceConfiguration",
    "ServiceLifecycle",
    
    # Engine Components
    "DAGExecutionEngine",
    "NodeRunnerService",
    "ExecutionStateTracker",
    
    # Controllers
    "OrchestrationController",
    "JobCancellationError",
    "OrchestrationControllerFactory",
    
    # Routes
    "router",
] 