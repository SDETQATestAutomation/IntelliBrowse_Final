# Technical Context - IntelliBrowse

## Technology Stack

### Backend Technology
- **Language**: Python 3.8+
- **Framework**: FastAPI
- **Architecture**: Clean layered structure (routes/controllers/services/schemas/models/utils)
- **Async Support**: Full async/await for IO operations
- **Validation**: Pydantic schemas with versioning
- **Dependency Injection**: FastAPI `Depends()`

### Frontend Technology  
- **Language**: TypeScript
- **Framework**: React 18+
- **Component Style**: Functional components with React Hooks
- **Styling**: TailwindCSS with responsive design
- **Form Handling**: React Hook Form + Yup validation
- **API Layer**: Axios service layer
- **State Management**: Zustand or Redux (TBD)

### Development Environment
- **Python Environment**: Virtual environment (.venv)
- **Package Management**: pip with requirements.txt
- **Node Environment**: Node.js 14+ with npm/yarn
- **Development Ports**: Backend (8000), Frontend (3000)

### Development Tools
- **Python Linting**: flake8
- **Python Formatting**: black + isort
- **JavaScript Linting**: eslint
- **JavaScript Formatting**: prettier
- **Testing**: Jest + React Testing Library

### Infrastructure Requirements
- **Environment Variables**: python-dotenv for configuration
- **Security**: Authentication and rate limiting required
- **Documentation**: Auto-generated API docs via FastAPI
- **Git**: Conventional Commits standard

## Project Structure Standards

### Backend Structure
```
src/backend/
├── routes/          # API endpoint definitions
├── controllers/     # Request/response handling
├── services/        # Business logic implementation
├── schemas/         # Pydantic input/output schemas
├── models/          # Data models and database entities
├── utils/           # Shared utilities and helpers
└── main.py          # FastAPI application entry point
```

### Frontend Structure
```
src/frontend/
├── features/        # Feature-based organization
├── components/      # Reusable UI components
├── hooks/           # Custom React hooks
├── services/        # API service layer
├── utils/           # Frontend utilities
└── App.tsx          # React application entry point
```

## Development Conventions

### Code Standards
- **Naming**: PascalCase (classes), camelCase (methods/JS), snake_case (Python)
- **Methods**: Single responsibility, max 30 lines
- **Variables**: Descriptive, intention-revealing names
- **Error Handling**: Structured exception handling with logging

### Architecture Principles
- **SOLID Principles**: Single Responsibility, Open/Closed, etc.
- **DRY Principle**: Don't Repeat Yourself
- **KISS Principle**: Keep It Simple, Stupid
- **Clean Architecture**: Separation of concerns across layers

## Current Implementation Phase
**VAN Mode**: Setting up basic infrastructure and development environment foundation. 