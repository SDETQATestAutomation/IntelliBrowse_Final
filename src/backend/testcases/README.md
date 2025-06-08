# Test Cases Module - IntelliBrowse

## Overview

The Test Cases module provides comprehensive test case management functionality for the IntelliBrowse platform. It implements atomic, reusable, testable units that serve as the building blocks for test automation, offering structured test design, intelligent tagging, lifecycle management, and seamless integration with test suites and test items.

### Key Features

- **Atomic Test Case Management**: Create, read, update, and delete test cases with full lifecycle control
- **Flexible Step Architecture**: Unified step schema supporting GENERIC, BDD, and MANUAL test types
- **Intelligent Tagging System**: Auto-completion, normalization, and usage tracking for enhanced organization
- **Advanced Validation**: Deep validation with cycle detection for test item references
- **Lifecycle Management**: Draft → Active → Deprecated → Archived status transitions
- **Owner-Based Access Control**: User-scoped access with JWT authentication
- **Performance Optimized**: <100ms list queries, <50ms single retrieval with strategic indexing

## Module Structure

```
src/backend/testcases/
├── models/                 # Data Models & Database Layer
│   ├── __init__.py        # Model exports
│   └── test_case_model.py # TestCaseModel, TestCaseStep, enums
├── schemas/               # Pydantic Schemas & Validation
│   ├── __init__.py        # Schema exports
│   └── test_case_schemas.py # Request/Response schemas
├── services/              # Business Logic Layer
│   ├── __init__.py        # Service exports
│   └── test_case_service.py # Core business logic, validation, tagging
├── controllers/           # HTTP Request Handling
│   ├── __init__.py        # Controller exports
│   └── test_case_controller.py # HTTP orchestration
├── routes/                # API Route Definitions
│   ├── __init__.py        # Route exports
│   └── test_case_routes.py # FastAPI routes
└── README.md             # This documentation
```

## Component Responsibilities

### Models Layer (`models/`)

**Primary Responsibility**: Database schema definition and MongoDB integration

- **TestCaseModel**: Main MongoDB document with embedded steps and metadata
- **TestCaseStep**: Unified step schema supporting multiple test types
- **Enums**: Status, priority, step types, and format hints
- **AttachmentRef**: File reference model for test artifacts
- **Index Strategy**: 6 optimized indexes for performance
- **BaseMongoModel Integration**: UTC timestamps and serialization

**Key Files**:
- `test_case_model.py`: Complete model implementation with validation

### Schemas Layer (`schemas/`)

**Primary Responsibility**: Request/response validation and API contracts

- **Request Schemas**: CreateTestCaseRequest, UpdateTestCaseRequest, FilterTestCasesRequest
- **Response Schemas**: TestCaseResponse, TestCaseListResponse, TestCaseStatsResponse
- **Flexible Field Inclusion**: Core + optional detailed fields for performance
- **Pagination Support**: PaginationMeta, FilterMeta, SortMeta
- **Type Safety**: Comprehensive typing with examples and documentation

**Key Files**:
- `test_case_schemas.py`: Complete schema definitions with validation

### Services Layer (`services/`)

**Primary Responsibility**: Business logic implementation and data processing

- **TestCaseService**: Main CRUD operations and lifecycle management
- **TestCaseValidationService**: Deep validation with DFS-based cycle detection
- **TestCaseTagService**: Intelligent tagging with normalization and auto-complete
- **TestCaseResponseBuilder**: Flexible response construction with field inclusion
- **Performance Features**: Async operations, connection pooling, query optimization

**Key Files**:
- `test_case_service.py`: Complete service implementation

### Controllers Layer (`controllers/`)

**Primary Responsibility**: HTTP request/response orchestration

- **TestCaseController**: HTTP request handling with authentication integration
- **Request Processing**: Validation and transformation of HTTP requests
- **Response Formatting**: Consistent BaseResponse patterns
- **Error Handling**: HTTP-specific exception handling with appropriate status codes
- **Input Validation**: ObjectId format validation and pagination parameters

**Key Files**:
- `test_case_controller.py`: Complete controller implementation

### Routes Layer (`routes/`)

**Primary Responsibility**: API endpoint definitions and OpenAPI documentation

- **FastAPI Routes**: RESTful API endpoints with proper HTTP methods
- **Authentication Integration**: JWT token validation on all endpoints
- **OpenAPI Documentation**: Rich Swagger documentation with examples
- **Response Models**: Type-safe response model definitions

**Key Files**:
- `test_case_routes.py`: Complete route definitions

## Integration Points

### Test Item System Integration

**Relationship**: Test cases can reference test items for step reuse and execution logic

```python
# Example test case with test item references
{
    "test_item_references": [
        {
            "test_item_id": "507f1f77bcf86cd799439011",
            "reference_type": "execution",
            "context": "Automated execution step"
        }
    ]
}
```

**Integration Features**:
- Reference validation to ensure test items exist
- Circular dependency detection
- Execution context mapping

### Test Suite System Integration

**Relationship**: Test cases can be included in multiple test suites

```python
# Test suites can reference test cases
{
    "test_cases": [
        {
            "test_case_id": "507f1f77bcf86cd799439012",
            "execution_order": 1,
            "is_required": true
        }
    ]
}
```

**Integration Features**:
- Suite composition with test cases
- Execution order management
- Required vs optional test case designation

### Authentication System Integration

**Relationship**: All test case operations require authenticated users

```python
# User context in all operations
user_context = {
    "user_id": "507f1f77bcf86cd799439013",
    "username": "test_user@example.com",
    "roles": ["test_designer", "test_executor"]
}
```

**Integration Features**:
- JWT token validation on all endpoints
- User-scoped access control
- Owner-based permissions

## Async Patterns & Performance Guidelines

### Async/Await Implementation

All I/O operations use async/await patterns for optimal performance:

```python
# Service layer async patterns
async def create_test_case(
    self, 
    request: CreateTestCaseRequest, 
    user_id: str
) -> TestCaseResponse:
    # Async database operations
    existing_case = await self.db.test_cases.find_one({
        "title": request.title,
        "owner_id": user_id
    })
    
    if existing_case:
        raise ValueError("Test case with this title already exists")
    
    # Async creation
    result = await self.db.test_cases.insert_one(test_case_dict)
    return await self._build_response(result.inserted_id, include_steps=True)
```

### Performance Optimization Strategies

**Database Indexing**:
```python
# Strategic indexes for optimal query performance
INDEXES = [
    ("owner_id", 1),                    # User scoping
    ("status", 1),                      # Status filtering
    ("tags", 1),                        # Tag-based searches
    ("created_at", -1),                 # Chronological sorting
    ("title", "text"),                  # Text search
    ("owner_id", 1, "title", 1)        # Compound unique constraint
]
```

**Query Optimization**:
- Projection-based field selection
- Pagination with skip/limit
- Index-aware filtering
- Response caching where appropriate

**Performance Targets**:
- List queries: <100ms
- Single retrieval: <50ms
- Complex operations: <200ms

## Configuration Requirements

### Environment Variables

```bash
# MongoDB Configuration
MONGODB_URL=mongodb://localhost:27017/intellibrowse
MONGODB_DATABASE=intellibrowse

# JWT Authentication
JWT_SECRET_KEY=your_jwt_secret_key_here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# CORS Configuration
CORS_ORIGINS=["http://localhost:3000", "https://yourdomain.com"]
CORS_CREDENTIALS=true
CORS_METHODS=["GET", "POST", "PUT", "DELETE"]
CORS_HEADERS=["*"]

# API Configuration
API_V1_PREFIX=/api/v1
ENABLE_DOCS=true
```

### MongoDB Setup

```python
# Database indexes are automatically created on startup
# Ensure MongoDB is running and accessible
# Collections: test_cases, tag_index

# Required MongoDB version: 5.0+
# Required features: Text search, compound indexes
```

### Authentication Setup

```python
# JWT token must include:
{
    "user_id": "string",        # Required: User identifier
    "username": "string",       # Required: Username/email
    "exp": 1234567890,         # Required: Expiration timestamp
    "roles": ["string"]        # Optional: User roles
}
```

## Developer Usage Instructions

### 1. Creating Test Cases

```python
# POST /api/v1/testcases/
{
    "title": "User Login Validation",
    "description": "Verify user can log in with valid credentials",
    "test_type": "GENERIC",
    "priority": "HIGH",
    "tags": ["authentication", "login", "security"],
    "steps": [
        {
            "step_number": 1,
            "step_type": "ACTION",
            "description": "Navigate to login page",
            "expected_result": "Login form is displayed"
        },
        {
            "step_number": 2,
            "step_type": "ACTION",
            "description": "Enter valid credentials",
            "expected_result": "User is redirected to dashboard"
        }
    ]
}
```

### 2. Retrieving Test Cases

```python
# GET /api/v1/testcases/{test_case_id}?include_fields=steps,statistics
# Response includes flexible field inclusion
{
    "success": true,
    "data": {
        "id": "507f1f77bcf86cd799439011",
        "title": "User Login Validation",
        "status": "ACTIVE",
        "steps": [...],           # Included due to include_fields
        "statistics": {...}       # Included due to include_fields
    }
}
```

### 3. Listing with Filters

```python
# GET /api/v1/testcases/?status=ACTIVE&tags=authentication&page=1&size=10
{
    "success": true,
    "data": {
        "items": [...],
        "pagination": {
            "total": 50,
            "page": 1,
            "size": 10,
            "pages": 5
        },
        "filters": {
            "status": "ACTIVE",
            "tags": ["authentication"]
        }
    }
}
```

### 4. Updating Test Cases

```python
# PUT /api/v1/testcases/{test_case_id}
{
    "title": "Updated Test Case Title",
    "description": "Updated description",
    "tags": ["new-tag", "updated-tag"]
}
```

### 5. Managing Lifecycle

```python
# POST /api/v1/testcases/{test_case_id}/status
{
    "status": "DEPRECATED",
    "reason": "Replaced by newer test case"
}
```

### 6. Working with Tags

```python
# GET /api/v1/testcases/tags/suggestions?prefix=auth
{
    "success": true,
    "data": {
        "suggestions": [
            {"tag": "authentication", "usage_count": 15},
            {"tag": "authorization", "usage_count": 8},
            {"tag": "auth-flow", "usage_count": 3}
        ]
    }
}

# GET /api/v1/testcases/tags/popular?limit=10
{
    "success": true,
    "data": {
        "popular_tags": [
            {"tag": "regression", "usage_count": 45},
            {"tag": "smoke", "usage_count": 32},
            {"tag": "integration", "usage_count": 28}
        ]
    }
}
```

## Testing & Validation

### Unit Testing

```bash
# Run test case module tests
pytest tests/backend/testcases/ -v

# Run with coverage
pytest tests/backend/testcases/ --cov=src.backend.testcases
```

### Integration Testing

```bash
# Test with actual MongoDB
pytest tests/backend/testcases/integration/ -v

# Test API endpoints
pytest tests/backend/testcases/api/ -v
```

### Manual Testing

```bash
# Start the development server
uvicorn src.backend.main:app --reload --host=127.0.0.1 --port=8000

# Access API documentation
# http://localhost:8000/docs

# Test health endpoint
curl http://localhost:8000/health
```

## Error Handling

The module implements comprehensive error handling:

```python
# Validation errors return 400
{
    "success": false,
    "message": "Validation error: Title already exists",
    "error_code": "VALIDATION_ERROR"
}

# Authentication errors return 401
{
    "success": false,
    "message": "Authentication required",
    "error_code": "AUTHENTICATION_REQUIRED"
}

# Authorization errors return 403
{
    "success": false,
    "message": "Access denied: Not authorized to modify this test case",
    "error_code": "ACCESS_DENIED"
}

# Not found errors return 404
{
    "success": false,
    "message": "Test case not found",
    "error_code": "RESOURCE_NOT_FOUND"
}
```

## Security Considerations

- **Authentication**: All endpoints require valid JWT tokens
- **Authorization**: Users can only access their own test cases
- **Input Validation**: All inputs validated using Pydantic schemas
- **SQL Injection Prevention**: MongoDB with proper query construction
- **Rate Limiting**: Implement at API gateway level
- **Data Sanitization**: User inputs sanitized and validated

## Monitoring & Observability

```python
# Structured logging for all operations
logger.info(
    "Test case created",
    extra={
        "user_id": user_id,
        "test_case_id": test_case_id,
        "title": request.title,
        "execution_time_ms": execution_time
    }
)

# Performance metrics tracking
# - Request/response times
# - Database query performance
# - Error rates and types
# - User activity patterns
```

## Future Enhancements

- **Version History**: Track changes for audit trails
- **Bulk Operations**: Bulk create, update, and status changes
- **Export/Import**: JSON/Excel export and import capabilities
- **Template System**: Test case templates for common patterns
- **Collaboration**: Comments, reviews, and approval workflows
- **Analytics**: Test case usage and effectiveness metrics
- **CI/CD Integration**: Automated test case execution triggers

## Support & Troubleshooting

### Common Issues

**Issue**: Test case creation fails with "Title already exists"
**Solution**: Check for existing test cases with the same title under your user account

**Issue**: 404 errors when accessing test cases
**Solution**: Verify JWT token is valid and user has access to the test case

**Issue**: Slow query performance
**Solution**: Ensure MongoDB indexes are created and query uses indexed fields

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with debug information
uvicorn src.backend.main:app --reload --log-level debug
```

For additional support, refer to the Memory Bank documentation in `memory-bank/` or contact the development team. 