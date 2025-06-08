# Scheduled Task Runner Module

## Overview

The Scheduled Task Runner module provides comprehensive distributed task scheduling capabilities for the IntelliBrowse platform. This Level 4 complex system enables automated test execution, scheduled maintenance, and workflow automation with high reliability and performance.

## Module Scope

- **Distributed task scheduling** with cron and interval-based triggers
- **High-performance execution** supporting 1000+ concurrent tasks
- **Hybrid priority queue** architecture for optimal performance and reliability
- **MongoDB TTL-based distributed locking** for race-condition prevention
- **RESTful API interface** with comprehensive authentication and validation
- **Integration framework** for external service communication
- **Performance monitoring** and metrics collection

## Folder and File Structure

```
src/backend/scheduler/
├── models/
│   └── trigger_model.py          # Data models (ScheduledTriggerModel, ScheduledJobModel, ExecutionLockModel)
├── schemas/
│   └── trigger_schemas.py        # Request/response schemas and validation
├── services/
│   ├── base_scheduler_service.py # Abstract base services and interfaces
│   └── scheduler_service.py      # Concrete business logic implementation
├── engines/
│   └── task_orchestration_engine.py # Core orchestration engine
├── controllers/
│   └── scheduler_controller.py   # HTTP request handling and validation
├── routes/
│   └── scheduler_routes.py       # FastAPI route definitions
└── __init__.py                   # Package initialization and exports
```

## Key Services and Controllers

### Core Engine
- **TaskOrchestrationEngine**: Central orchestration logic with hybrid priority queue
- **TriggerEngineService**: Abstract interface for trigger management
- **LockManagerService**: Abstract interface for distributed locking
- **JobExecutionService**: Abstract interface for job lifecycle management

### Business Logic Layer
- **SchedulerService**: Main business logic for trigger operations
- **SchedulerController**: HTTP request handling and validation

### Data Layer
- **ScheduledTriggerModel**: Trigger configuration and metadata
- **ScheduledJobModel**: Job execution tracking and history
- **ExecutionLockModel**: Distributed lock management with TTL

## Pydantic Schemas Used

### Request Schemas
- **CreateScheduledTriggerRequest**: New trigger creation with validation
- **UpdateScheduledTriggerRequest**: Trigger modification with partial updates
- **LockAcquisitionRequest**: Lock acquisition parameters
- **TriggerListParams**: Query parameters for trigger listing

### Response Schemas
- **ScheduledTriggerResponse**: Complete trigger information
- **ScheduledJobResponse**: Job execution details and status
- **ExecutionStatusResponse**: Manual trigger execution status
- **ExecutionHistoryResponse**: Paginated execution history
- **SystemHealthResponse**: Scheduler health and metrics

### Configuration Schemas
- **TriggerConfigSchema**: Trigger timing and execution configuration
- **ExecutionConfigSchema**: Job execution parameters and constraints
- **RetryPolicySchema**: Retry behavior and backoff configuration

## Trigger Types and Execution Flow

### Supported Trigger Types
- **CRON**: Traditional cron expression scheduling
- **INTERVAL**: Fixed interval repetition
- **MANUAL**: On-demand execution
- **EVENT**: Event-driven triggers (future enhancement)

### Execution Flow
1. **Trigger Evaluation**: Engine evaluates due triggers based on schedule
2. **Lock Acquisition**: Distributed lock prevents duplicate execution
3. **Job Dispatch**: Task dispatched to appropriate handler
4. **Execution Tracking**: Real-time status and metrics collection
5. **Result Processing**: Success/failure handling with retry logic
6. **Cleanup**: Lock release and resource cleanup

## Supported Scheduling Formats

### Cron Expressions
- Standard 5-field cron format: `minute hour day month dayofweek`
- Examples:
  - `0 2 * * *` - Daily at 2:00 AM
  - `*/15 * * * *` - Every 15 minutes
  - `0 9 * * 1-5` - Weekdays at 9:00 AM

### Interval Scheduling
- Fixed interval repetition with configurable units
- Supported units: seconds, minutes, hours, days
- Example: `{"interval": 3600, "unit": "seconds"}` - Every hour

### Manual Triggers
- On-demand execution via API endpoint
- Immediate execution with optional parameter override
- Status tracking and result reporting

## Authentication & Authorization

### JWT Bearer Token Authentication
- All endpoints require valid JWT authentication
- User context preserved throughout execution chain
- Role-based access control for administrative operations

### User Scoping
- Triggers scoped to creating user by default
- Admin users can manage system-wide triggers
- User isolation prevents unauthorized access

### Security Headers
- CORS configuration for cross-origin requests
- Rate limiting on API endpoints
- Input validation and sanitization

## Sample Usage Scenarios

### Creating a Daily Backup Trigger
```python
POST /api/scheduler/triggers/
{
    "name": "daily-backup",
    "description": "Daily database backup",
    "trigger_config": {
        "cron_expression": "0 2 * * *",
        "timezone": "UTC"
    },
    "execution_config": {
        "task_type": "backup",
        "max_execution_time": 3600,
        "retry_policy": {
            "max_retries": 3,
            "backoff_multiplier": 2.0
        }
    }
}
```

### Scheduling Test Suite Execution
```python
POST /api/scheduler/triggers/
{
    "name": "nightly-tests",
    "description": "Nightly test suite execution",
    "trigger_config": {
        "cron_expression": "0 1 * * *",
        "timezone": "America/New_York"
    },
    "execution_config": {
        "task_type": "test_execution",
        "parameters": {
            "suite_id": "regression-suite",
            "environment": "staging"
        }
    }
}
```

### Manual Trigger Execution
```python
POST /api/scheduler/triggers/{trigger_id}/execute
{
    "parameters": {
        "force_execution": true,
        "override_config": {
            "environment": "production"
        }
    }
}
```

## Performance Characteristics

### Execution Latency
- **Target**: <5 seconds from trigger time to execution start
- **Architecture**: Hybrid priority queue with in-memory performance
- **Monitoring**: Real-time latency metrics and alerting

### Concurrency
- **Capacity**: 1000+ concurrent task executions
- **Control**: Configurable max concurrent executions per task type
- **Isolation**: Per-user and per-tenant execution isolation

### Reliability
- **Crash Recovery**: Database persistence with automatic queue rebuilding
- **Lock Management**: TTL-based distributed locking with automatic cleanup
- **Retry Logic**: Exponential backoff with jitter for failed executions

## Integration Points

### Test Execution Engine
- Direct API communication for test suite execution
- Status callbacks and result reporting
- Execution context preservation

### Notification Engine
- Event-driven messaging for execution status
- Alert generation for failed executions
- Escalation procedures for critical failures

### Orchestration Engine
- Complex workflow coordination
- Dependency management between scheduled tasks
- Cross-system integration patterns

### Execution Reporting
- Structured logging and metrics aggregation
- Performance monitoring and analytics
- Audit trail and compliance reporting

## Monitoring and Health Checks

### Health Endpoints
- `GET /api/scheduler/health` - Basic health status
- System resource utilization monitoring
- Queue depth and processing metrics

### Metrics Collection
- Execution latency and throughput
- Success/failure rates by task type
- Resource utilization and performance trends

### Alerting
- Failed execution notifications
- Performance degradation alerts
- System resource threshold alerts

## Configuration Management

### Environment Variables
- Database connection settings
- Performance tuning parameters
- Security configuration options

### Runtime Configuration
- Task handler registration
- Retry policy defaults
- Monitoring and logging levels

## Future Enhancements

### Advanced Scheduling
- Complex scheduling patterns and dependencies
- Calendar-based scheduling with holiday support
- Dynamic scheduling based on system load

### Multi-Tenant Support
- Complete tenant isolation for scheduled tasks
- Tenant-specific resource allocation
- Cross-tenant scheduling coordination

### AI-Powered Optimization
- Intelligent task scheduling optimization
- Predictive resource allocation
- Performance optimization through machine learning

## Support and Troubleshooting

### Common Issues
- Lock contention and deadlock prevention
- Performance tuning for high-volume scenarios
- Integration debugging and monitoring

### Diagnostic Tools
- Built-in diagnostic endpoints
- Performance profiling capabilities
- Comprehensive logging and tracing

### Documentation References
- API specification: `/docs/openapi/scheduler_openapi.yaml`
- Implementation details: `/docs/archive/scheduler-engine-archive.md`
- Memory bank documentation: `/memory-bank/reflection/` 