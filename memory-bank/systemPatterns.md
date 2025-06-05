# System Patterns - IntelliBrowse

## Architectural Patterns

### Overall Architecture
- **Pattern**: Clean Architecture with Layered Design
- **Backend**: FastAPI with dependency injection
- **Frontend**: Component-based React architecture
- **Communication**: RESTful API with JSON responses

### Backend Patterns

#### Layer Separation
```
┌─────────────────┐
│    Routes       │ ← HTTP endpoints, request/response
├─────────────────┤
│  Controllers    │ ← Business flow coordination
├─────────────────┤
│   Services      │ ← Business logic implementation
├─────────────────┤
│   Models        │ ← Data structures and validation
└─────────────────┘
```

#### Dependency Injection Pattern
```python
# Example pattern for FastAPI dependency injection
async def get_user_service() -> UserService:
    return UserService()

@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    user_service: UserService = Depends(get_user_service)
):
    return await user_service.get_user(user_id)
```

#### Response Pattern
```python
# Standardized API response structure
{
    "success": true|false,
    "data": {...},
    "message": "string",
    "timestamp": "ISO string"
}
```

### Frontend Patterns

#### Component Organization
```
src/frontend/
├── features/           # Feature-based modules
│   ├── user/          
│   │   ├── components/
│   │   ├── hooks/
│   │   └── services/
├── components/         # Shared UI components
│   ├── ui/            # Basic UI elements
│   └── forms/         # Form components
└── services/          # API integration layer
```

#### State Management Pattern
- **Local State**: React useState for component-level state
- **Global State**: Zustand for application-wide state
- **Server State**: React Query for API data caching
- **Form State**: React Hook Form for form management

#### API Service Pattern
```typescript
// Centralized API service pattern
class ApiService {
  private baseURL = 'http://localhost:8000';
  
  async get<T>(endpoint: string): Promise<T> {
    // Standardized GET requests
  }
  
  async post<T>(endpoint: string, data: any): Promise<T> {
    // Standardized POST requests
  }
}
```

## Error Handling Patterns

### Backend Error Handling
```python
# Structured exception handling
try:
    result = await service.perform_operation()
    return {"success": True, "data": result}
except ValidationError as e:
    raise HTTPException(status_code=400, detail=str(e))
except NotFoundError as e:
    raise HTTPException(status_code=404, detail=str(e))
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise HTTPException(status_code=500, detail="Internal server error")
```

### Frontend Error Handling
```typescript
// Error boundary and try-catch patterns
const handleApiCall = async () => {
  try {
    const data = await apiService.getData();
    setData(data);
  } catch (error) {
    setError(error.message);
    logError(error);
  }
};
```

## Security Patterns

### Authentication Pattern
- **JWT Tokens**: For stateless authentication
- **Route Protection**: Middleware for protected endpoints
- **Role-Based Access**: Permission checking at service layer

### Input Validation Pattern
- **Backend**: Pydantic schemas for automatic validation
- **Frontend**: Yup schemas with React Hook Form
- **Sanitization**: Input cleaning at multiple layers

## Development Patterns

### Testing Pattern
```
test/
├── unit/              # Individual component/function tests
├── integration/       # API endpoint tests
└── e2e/              # End-to-end user flow tests
```

### Logging Pattern
```python
# Structured logging throughout application
import logging

logger = logging.getLogger(__name__)

def service_method():
    logger.info("Starting operation", extra={"user_id": user.id})
    try:
        # operation
        logger.info("Operation completed successfully")
    except Exception as e:
        logger.error("Operation failed", extra={"error": str(e)})
```

## File Organization Patterns

### Configuration Pattern
- **Environment Variables**: `.env` files for configuration
- **Settings Classes**: Pydantic Settings for structured config
- **Development vs Production**: Environment-specific configurations

### Import Pattern
```python
# Backend imports
from src.services.user_service import UserService
from src.schemas.user_schema import UserCreateSchema

# Frontend imports
import { UserService } from '@/services/UserService';
import { UserForm } from '@/components/UserForm';
```

## Current Implementation Status
**VAN Mode**: Establishing foundational patterns for clean, maintainable architecture. 