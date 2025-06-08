"""
Execution Reporting Routes Package

FastAPI route definitions for the Execution Reporting Module.
Provides RESTful API endpoints for reporting, analytics, dashboards,
alerts, and data export functionality.
"""

from .execution_reporting_routes import router

__all__ = ["router"]
