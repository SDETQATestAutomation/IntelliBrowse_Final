# IntelliBrowse

A modern enterprise-grade Test Management tool with a specific emphasis on test automation.

## Overview

IntelliBrowse is a comprehensive full-stack web application designed to achieve complete test automation for projects under test, ensuring comprehensive test coverage. The platform provides advanced test case management, test suite orchestration, and automation capabilities through a clean, modern interface built with cutting-edge web technologies.

## Key Features

- **Test Case Management**: Comprehensive test case creation, organization, and management
- **Test Automation**: Complete test automation framework with comprehensive coverage
- **Test Suite Orchestration**: Advanced test suite management and execution
- **Enterprise-Grade Architecture**: Scalable, secure, and maintainable codebase
- **Modern UI/UX**: Responsive design with modern interface patterns
- **Real-time Monitoring**: Live test execution monitoring and reporting

## Technology Stack

### Backend
- **Python 3.9+** with **FastAPI**
- **MongoDB** for data persistence
- Clean layered architecture (routes/controllers/services/schemas/models/utils)
- Async/await for IO operations
- Pydantic schemas for validation and serialization
- Dependency injection pattern
- Comprehensive logging and error handling

### Frontend  
- **TypeScript** with **React 18+**
- Functional components and React Hooks
- **TailwindCSS** for responsive styling
- React Hook Form + Yup for form validation
- Axios for API communication
- State management with Zustand/Redux

## Project Structure

```
IntelliBrowse/
├── src/
│   ├── backend/              # Python FastAPI backend
│   │   ├── auth/            # Authentication and authorization
│   │   ├── testcases/       # Test case management
│   │   ├── testsuites/      # Test suite orchestration
│   │   ├── testtypes/       # Test type definitions
│   │   ├── testitems/       # Test item management
│   │   ├── routes/          # API route definitions
│   │   ├── controllers/     # Request handling logic
│   │   ├── services/        # Business logic layer
│   │   ├── schemas/         # Pydantic data models
│   │   ├── models/          # Database models
│   │   ├── utils/           # Utility functions
│   │   └── config/          # Configuration management
│   └── frontend/            # React TypeScript frontend
├── tests/
│   ├── backend/             # Backend test suites
│   └── scripts/             # Testing utilities and scripts
├── memory-bank/             # Project documentation and context
│   ├── creative/            # Creative phase documentation
│   ├── reflection/          # Reflection documentation
│   └── archive/             # Archived task documentation
├── docs/                    # Additional documentation
├── requirements.txt         # Python dependencies
├── .gitignore              # Git ignore patterns
├── .env.example            # Environment variables template
└── README.md               # This file
```

## Development Lifecycle

IntelliBrowse follows a structured development approach with these lifecycle stages:

- **VAN**: Initialize project and determine complexity
- **PLAN**: Create detailed implementation plan
- **CREATIVE**: Explore design options for complex components
- **IMPLEMENT**: Systematically build planned components
- **REFLECT**: Review and document lessons learned
- **ARCHIVE**: Create comprehensive documentation

## Development Setup

### Prerequisites
- Python 3.9+
- Node.js 16+
- MongoDB 5.0+
- npm or yarn

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Kill any existing processes on development ports
lsof -i :8000 -t | xargs -r kill -9
lsof -i :3000 -t | xargs -r kill -9
```

### Backend Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn src.backend.main:app --reload --host=127.0.0.1 --port=8000
```

### Frontend Setup
```bash
# Navigate to frontend directory and install dependencies
cd src/frontend
npm install

# Start development server
npm start
```

### Development Ports
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Development Principles

- **Clean Architecture**: SOLID, DRY, and KISS principles
- **Enterprise-Grade**: Scalable, secure, and maintainable architecture
- **Type Safety**: TypeScript for frontend, Pydantic for backend
- **Testing Pyramid**: Unit > integration > e2e testing
- **Code Quality**: Linting with flake8 (Python), eslint (React)
- **Formatting**: black + isort (Python), prettier (React)
- **Security**: Authentication, rate limiting, input validation
- **Modular Design**: Component-based architecture for maintainability

## Memory Bank System

IntelliBrowse uses a comprehensive memory bank system to retain and recall implementation context across iterations:

- **Active Context**: Current development context and state
- **Progress Tracking**: Development milestones and completion status
- **Project Brief**: Core project vision and objectives
- **Technical Context**: Architecture decisions and patterns
- **Creative Decisions**: Design explorations and solutions
- **Reflection Documents**: Lessons learned and improvements

## Getting Started

1. Clone the repository
2. Set up the development environment using the setup instructions above
3. Review the `memory-bank/` documentation for project context
4. Follow the VAN -> PLAN -> CREATIVE -> IMPLEMENT -> REFLECT -> ARCHIVE lifecycle
5. Build components incrementally, one at a time

## Test Management Features

### Core Capabilities
- **Test Case Creation**: Rich test case authoring with step-by-step instructions
- **Test Suite Management**: Organize test cases into logical test suites
- **Test Execution**: Automated test execution with real-time monitoring
- **Test Reporting**: Comprehensive test reports and analytics
- **Test Coverage**: Track and ensure comprehensive test coverage
- **Integration Support**: API integrations for CI/CD pipelines

### Automation Focus
- **Full Automation**: Achieve complete test automation for projects under test
- **Coverage Analysis**: Ensure comprehensive test coverage across all components
- **Execution Monitoring**: Real-time test execution status and results
- **Failure Analysis**: Detailed failure reporting and debugging support

## Documentation

Project documentation and context can be found in the `memory-bank/` directory:
- `projectbrief.md` - Project overview and goals
- `techContext.md` - Technical architecture and decisions
- `systemPatterns.md` - Code patterns and conventions
- `productContext.md` - Product vision and user experience
- `style-guide.md` - Development style guide and conventions

## Contributing

Please follow the established development principles and lifecycle stages when contributing to IntelliBrowse. All contributions should adhere to the clean code standards and architectural patterns defined in the memory bank documentation.

## License

[License information to be added] 