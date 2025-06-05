"""
Centralized constants for IntelliBrowse backend application.
"""

# Application metadata
APP_NAME = "IntelliBrowse"
APP_DESCRIPTION = "A modern enterprise-grade full-stack web application for intelligent browsing and data management"
APP_VERSION = "1.0.0"

# Server configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

# API configuration
API_V1_PREFIX = "/api/v1"
DOCS_URL = "/docs"
REDOC_URL = "/redoc"
OPENAPI_URL = "/openapi.json"

# CORS configuration
CORS_ORIGINS = [
    "http://localhost:3000",  # React frontend development
    "http://127.0.0.1:3000",  # Alternative localhost
]

# Logging configuration
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
LOG_ROTATION = "10 MB"
LOG_RETENTION = "7 days"
LOG_LEVEL_CONSOLE = "INFO"
LOG_LEVEL_FILE = "DEBUG"

# Health check configuration
HEALTH_CHECK_ENDPOINT = "/health"
SYSTEM_STATUS_HEALTHY = "healthy"
SYSTEM_STATUS_DEGRADED = "degraded"
SYSTEM_STATUS_UNHEALTHY = "unhealthy"

# Response messages
HEALTH_MESSAGE_RUNNING = f"{APP_NAME} backend is running"
HEALTH_MESSAGE_DEGRADED = f"{APP_NAME} backend is experiencing issues"
HEALTH_MESSAGE_UNHEALTHY = f"{APP_NAME} backend is not functioning properly" 