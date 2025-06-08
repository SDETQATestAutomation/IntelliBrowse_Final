"""
Scheduled Task Runner Engine - Schemas Package

Implements Pydantic schemas for request/response validation, OpenAPI documentation,
and type-safe API contracts. Provides comprehensive validation with detailed
error messages and examples for the scheduler API endpoints.

Key Schemas:
- TriggerSchemas: CRUD operations for scheduled triggers
- JobSchemas: Job execution tracking and status updates
- LockSchemas: Distributed lock management operations
"""

from .trigger_schemas import (
    # Base Response Schema
    BaseResponseSchema,
    
    # Trigger Management Schemas
    CreateScheduledTriggerRequest,
    UpdateScheduledTriggerRequest,
    ScheduledTriggerResponse,
    ScheduledTriggerListResponse,
    
    # Job Management Schemas  
    ScheduledJobResponse,
    ScheduledJobListResponse,
    JobExecutionRequest,
    JobStatusUpdateRequest,
    
    # Execution Status and History
    ExecutionStatusResponse,
    ExecutionHistoryResponse,
    
    # Lock Management Schemas
    LockAcquisitionRequest,
    LockAcquisitionResponse,
    LockStatusResponse,
    
    # Configuration Schemas
    TriggerConfigSchema,
    ExecutionConfigSchema,
    RetryPolicySchema,
    
    # Status and Statistics
    TriggerStatsResponse,
    ExecutionStatsResponse,
    SystemHealthResponse
)

__all__ = [
    # Base Response
    "BaseResponseSchema",
    
    # Trigger Management
    "CreateScheduledTriggerRequest",
    "UpdateScheduledTriggerRequest", 
    "ScheduledTriggerResponse",
    "ScheduledTriggerListResponse",
    
    # Job Management
    "ScheduledJobResponse",
    "ScheduledJobListResponse",
    "JobExecutionRequest",
    "JobStatusUpdateRequest",
    
    # Execution Status and History
    "ExecutionStatusResponse",
    "ExecutionHistoryResponse",
    
    # Lock Management
    "LockAcquisitionRequest",
    "LockAcquisitionResponse", 
    "LockStatusResponse",
    
    # Configuration
    "TriggerConfigSchema",
    "ExecutionConfigSchema",
    "RetryPolicySchema",
    
    # Statistics and Health
    "TriggerStatsResponse",
    "ExecutionStatsResponse",
    "SystemHealthResponse"
] 