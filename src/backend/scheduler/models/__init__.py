"""
Scheduled Task Runner Engine - Models Package

Implements the foundation data models for scheduled tasks, trigger management,
execution tracking, and distributed locking. Designed for MongoDB storage with
optimized indexing for time-series operations and concurrent execution.

Key Models:
- ScheduledTriggerModel: Task scheduling and trigger definitions
- ScheduledJobModel: Job execution metadata and lifecycle management  
- ExecutionLockModel: Distributed locking for multi-instance coordination
"""

from .trigger_model import (
    ScheduledTriggerModel,
    ScheduledJobModel, 
    ExecutionLockModel,
    TaskStatus,
    ExecutionStatus,
    TriggerType,
    SchedulerException,
    InvalidTriggerConfigError,
    LockAcquisitionError
)

__all__ = [
    "ScheduledTriggerModel",
    "ScheduledJobModel",
    "ExecutionLockModel", 
    "TaskStatus",
    "ExecutionStatus",
    "TriggerType",
    "SchedulerException",
    "InvalidTriggerConfigError",
    "LockAcquisitionError"
] 