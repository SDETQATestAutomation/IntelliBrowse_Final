"""
Context schemas for MCP session, task, and user management.

These schemas define the context structures for maintaining state
across MCP tool invocations and sessions.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class UserContext(BaseModel):
    """User context information for MCP operations."""
    
    user_id: str = Field(description="Unique user identifier")
    username: Optional[str] = Field(default=None, description="Username")
    email: Optional[str] = Field(default=None, description="User email")
    roles: List[str] = Field(default=[], description="User roles for RBAC")
    permissions: List[str] = Field(default=[], description="User permissions")
    tenant_id: Optional[str] = Field(default=None, description="Multi-tenant namespace")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "username": "john.doe",
                "email": "john.doe@example.com",
                "roles": ["test_engineer", "bdd_writer"],
                "permissions": ["tools:execute", "resources:read"],
                "tenant_id": "tenant_abc"
            }
        }


class TaskContext(BaseModel):
    """Task context for tracking test automation workflows."""
    
    task_id: str = Field(description="Unique task identifier")
    task_type: str = Field(description="Type of task (bdd_generation, locator_creation, etc.)")
    test_suite_id: Optional[str] = Field(default=None, description="Associated test suite")
    test_case_id: Optional[str] = Field(default=None, description="Associated test case")
    
    # Workflow state
    workflow_step: str = Field(default="initial", description="Current workflow step")
    previous_steps: List[str] = Field(default=[], description="Previous workflow steps")
    
    # Task metadata
    priority: str = Field(default="medium", description="Task priority (low, medium, high)")
    tags: List[str] = Field(default=[], description="Task tags")
    metadata: Dict[str, Any] = Field(default={}, description="Additional task metadata")
    
    # Browser context
    browser_session_id: Optional[str] = Field(default=None, description="Browser session ID")
    current_url: Optional[str] = Field(default=None, description="Current browser URL")
    page_title: Optional[str] = Field(default=None, description="Current page title")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_456",
                "task_type": "bdd_generation",
                "test_suite_id": "suite_789",
                "test_case_id": "case_101",
                "workflow_step": "generating_scenarios",
                "previous_steps": ["requirements_analysis"],
                "priority": "high",
                "tags": ["e2e", "login_flow"],
                "metadata": {"feature": "user_authentication"},
                "browser_session_id": "browser_session_123",
                "current_url": "https://app.example.com/login",
                "page_title": "Login - Example App"
            }
        }


class SessionContext(BaseModel):
    """Session context for MCP operations."""
    
    session_id: str = Field(description="Unique session identifier")
    user_context: UserContext = Field(description="User context")
    task_context: Optional[TaskContext] = Field(default=None, description="Current task context")
    
    # Session state
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation time")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity time")
    expires_at: Optional[datetime] = Field(default=None, description="Session expiration time")
    
    # Tool history
    tool_invocations: List[Dict[str, Any]] = Field(default=[], description="History of tool invocations")
    resource_access_log: List[Dict[str, Any]] = Field(default=[], description="Resource access history")
    
    # Session configuration
    preferences: Dict[str, Any] = Field(default={}, description="User session preferences")
    metadata: Dict[str, Any] = Field(default={}, description="Session metadata including current URL, browser state, etc.")
    
    # Memory and state
    session_memory: Dict[str, Any] = Field(default={}, description="Session memory for context")
    workflow_state: Dict[str, Any] = Field(default={}, description="Workflow state tracking")
    
    # Performance tracking
    total_requests: int = Field(default=0, description="Total requests in session")
    total_tokens_used: int = Field(default=0, description="Total tokens consumed")
    
    def add_tool_invocation(self, tool_name: str, request_data: Dict[str, Any], response_data: Dict[str, Any]):
        """Add a tool invocation to the session history."""
        invocation = {
            "timestamp": datetime.utcnow().isoformat(),
            "tool_name": tool_name,
            "request": request_data,
            "response": response_data
        }
        self.tool_invocations.append(invocation)
        self.last_activity = datetime.utcnow()
        self.total_requests += 1
    
    def add_resource_access(self, resource_uri: str, access_type: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a resource access to the session log."""
        access_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "resource_uri": resource_uri,
            "access_type": access_type,
            "metadata": metadata or {}
        }
        self.resource_access_log.append(access_log)
        self.last_activity = datetime.utcnow()
    
    def update_memory(self, key: str, value: Any):
        """Update session memory with a key-value pair."""
        self.session_memory[key] = value
        self.last_activity = datetime.utcnow()
    
    def get_memory(self, key: str, default: Any = None) -> Any:
        """Get a value from session memory."""
        return self.session_memory.get(key, default)
    
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_789",
                "user_context": {
                    "user_id": "user_123",
                    "username": "john.doe",
                    "email": "john.doe@example.com",
                    "roles": ["test_engineer"],
                    "permissions": ["tools:execute"],
                    "tenant_id": "tenant_abc"
                },
                "task_context": {
                    "task_id": "task_456",
                    "task_type": "bdd_generation",
                    "workflow_step": "generating_scenarios"
                },
                "created_at": "2024-01-08T10:00:00Z",
                "last_activity": "2024-01-08T10:30:00Z",
                "expires_at": "2024-01-08T11:00:00Z",
                "total_requests": 5,
                "total_tokens_used": 1250,
                "preferences": {"language": "en", "timezone": "UTC"},
                "session_memory": {"last_generated_bdd": "scenario_123"}
            }
        } 