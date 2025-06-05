# IntelliBrowse

A modern enterprise-grade full-stack web application for intelligent browsing and data management.

## Overview

IntelliBrowse provides enhanced navigation, content discovery, and information organization capabilities through a clean, modern interface built with cutting-edge web technologies.

## Technology Stack

### Backend
- **Python 3.8+** with **FastAPI**
- Clean layered architecture (routes/controllers/services/schemas/models/utils)
- Async/await for IO operations
- Pydantic schemas for validation
- Dependency injection pattern

### Frontend  
- **TypeScript** with **React 18+**
- Functional components and React Hooks
- **TailwindCSS** for responsive styling
- React Hook Form + Yup for form validation
- Axios for API communication

## Project Structure

```
IntelliBrowse/
├── src/
│   ├── backend/          # Python FastAPI backend
│   └── frontend/         # React TypeScript frontend
├── test/scripts/         # Development and testing utilities
├── memory-bank/          # Project documentation and context
├── requirements.txt      # Python dependencies
├── .gitignore           # Git ignore patterns
├── .env.example         # Environment variables template
└── README.md            # This file
```

## Development Setup

### Prerequisites
- Python 3.8+
- Node.js 14+
- npm or yarn

### Backend Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (when available)
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

## Development Principles

- **Clean Architecture**: SOLID, DRY, and KISS principles
- **Type Safety**: TypeScript for frontend, Pydantic for backend
- **Testing**: Unit, integration, and e2e testing
- **Code Quality**: Linting, formatting, and code reviews
- **Security**: Authentication, input validation, and secure defaults

## Getting Started

1. Clone the repository
2. Set up the development environment using the setup instructions above
3. Review the `memory-bank/` documentation for project context
4. Start with backend or frontend development based on your focus area

## Documentation

Project documentation and context can be found in the `memory-bank/` directory:
- `projectbrief.md` - Project overview and goals
- `techContext.md` - Technical architecture and decisions
- `systemPatterns.md` - Code patterns and conventions
- `productContext.md` - Product vision and user experience

## License

[License information to be added]

## Contributing

[Contributing guidelines to be added] 