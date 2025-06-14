"""
Authentication middleware and RBAC implementation for IntelliBrowse MCP Server.

This module provides OAuth 2.0 authentication, JWT token validation, and
role-based access control for MCP tools and resources.
"""

import jwt
import httpx
import asyncio
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from ..config.settings import get_settings
from ..schemas.context_schemas import UserContext
from ..core.exceptions import AuthenticationError, AuthorizationError


@dataclass
class AuthenticationResult:
    """Result of authentication attempt."""
    success: bool
    user_context: Optional[UserContext] = None
    error_message: Optional[str] = None
    
    @property
    def is_authenticated(self) -> bool:
        """Check if authentication was successful."""
        return self.success and self.user_context is not None


class MCPAuthMiddleware:
    """
    OAuth 2.0 authentication middleware for MCP server.
    
    Provides JWT token validation, user context extraction, and integration
    with role-based access control system.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.rbac_manager = RBACManager()
        
    async def authenticate_token(self, token: str) -> AuthenticationResult:
        """
        Authenticate JWT token and extract user context.
        
        Args:
            token: JWT token string
            
        Returns:
            AuthenticationResult: Authentication result with user context
        """
        try:
            # Decode and verify JWT token
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "require": ["sub", "exp", "iat"]
                }
            )
            
            # Extract user information
            user_id = payload.get("sub")
            username = payload.get("username", "")
            email = payload.get("email", "")
            roles = payload.get("roles", [])
            tenant_id = payload.get("tenant_id")
            
            # Get permissions from roles
            permissions = self.rbac_manager.get_permissions(roles)
            
            # Create user context
            user_context = UserContext(
                user_id=user_id,
                username=username,
                email=email,
                roles=roles,
                permissions=permissions,
                tenant_id=tenant_id,
                authenticated_at=datetime.utcnow()
            )
            
            return AuthenticationResult(
                success=True,
                user_context=user_context
            )
            
        except jwt.ExpiredSignatureError:
            return AuthenticationResult(
                success=False,
                error_message="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            return AuthenticationResult(
                success=False,
                error_message=f"Invalid token: {str(e)}"
            )
        except Exception as e:
            return AuthenticationResult(
                success=False,
                error_message=f"Authentication error: {str(e)}"
            )
    
    async def validate_tool_access(
        self, 
        user_context: UserContext, 
        tool_name: str
    ) -> bool:
        """
        Validate user access to specific tool.
        
        Args:
            user_context: Authenticated user context
            tool_name: Name of the tool to access
            
        Returns:
            bool: True if access is granted
        """
        required_permission = f"tool:{tool_name}"
        return self.rbac_manager.check_permission(
            user_context.roles, 
            required_permission
        )
    
    async def validate_resource_access(
        self, 
        user_context: UserContext, 
        resource_uri: str
    ) -> bool:
        """
        Validate user access to specific resource.
        
        Args:
            user_context: Authenticated user context
            resource_uri: URI of the resource to access
            
        Returns:
            bool: True if access is granted
        """
        # Extract resource type from URI (e.g., "dom" from "dom://session/123")
        try:
            resource_type = resource_uri.split("://")[0]
            required_permission = f"resource:{resource_type}"
            return self.rbac_manager.check_permission(
                user_context.roles, 
                required_permission
            )
        except (IndexError, ValueError):
            return False
    
    async def validate_admin_access(self, user_context: UserContext) -> bool:
        """
        Validate admin-level access.
        
        Args:
            user_context: Authenticated user context
            
        Returns:
            bool: True if admin access is granted
        """
        return self.rbac_manager.check_permission(
            user_context.roles, 
            "admin:access"
        )


class RBACManager:
    """
    Role-Based Access Control manager.
    
    Manages user roles, permissions, and access control policies
    for MCP tools and resources.
    """
    
    def __init__(self):
        self.role_definitions = self._load_role_definitions()
        self.permission_cache: Dict[str, Set[str]] = {}
    
    def _load_role_definitions(self) -> Dict[str, List[str]]:
        """Load role definitions with permissions."""
        return {
            # Administrator - Full access
            "admin": [
                "tool:*",
                "resource:*",
                "audit:read",
                "audit:write",
                "config:read",
                "config:write",
                "admin:access"
            ],
            
            # Test Engineer - Full testing capabilities
            "test_engineer": [
                "tool:generate_bdd_scenario",
                "tool:generate_element_locator", 
                "tool:generate_test_step",
                "tool:heal_broken_selector",
                "tool:analyze_test_failure",
                "resource:dom",
                "resource:execution",
                "resource:schema",
                "audit:read"
            ],
            
            # QA Analyst - Read-only access with basic tools
            "qa_analyst": [
                "tool:generate_bdd_scenario",
                "tool:generate_element_locator",
                "resource:dom",
                "resource:execution",
                "audit:read"
            ],
            
            # Developer - Development and debugging tools
            "developer": [
                "tool:generate_test_step",
                "tool:heal_broken_selector", 
                "tool:analyze_test_failure",
                "resource:dom",
                "resource:execution",
                "resource:schema"
            ],
            
            # Viewer - Read-only access
            "viewer": [
                "resource:dom",
                "resource:execution",
                "audit:read"
            ]
        }
    
    def get_permissions(self, roles: List[str]) -> List[str]:
        """
        Get combined permissions for multiple roles.
        
        Args:
            roles: List of role names
            
        Returns:
            List[str]: Combined list of permissions
        """
        # Check cache first
        cache_key = "|".join(sorted(roles))
        if cache_key in self.permission_cache:
            return list(self.permission_cache[cache_key])
        
        # Combine permissions from all roles
        permissions = set()
        for role in roles:
            if role in self.role_definitions:
                permissions.update(self.role_definitions[role])
        
        # Cache result
        self.permission_cache[cache_key] = permissions
        return list(permissions)
    
    def check_permission(self, user_roles: List[str], required_permission: str) -> bool:
        """
        Check if user roles include required permission.
        
        Args:
            user_roles: List of user's roles
            required_permission: Permission to check (e.g., "tool:generate_bdd_scenario")
            
        Returns:
            bool: True if permission is granted
        """
        user_permissions = self.get_permissions(user_roles)
        
        # Check exact match
        if required_permission in user_permissions:
            return True
        
        # Check wildcard permissions
        for permission in user_permissions:
            if permission.endswith("*"):
                prefix = permission[:-1]
                if required_permission.startswith(prefix):
                    return True
        
        return False
    
    def get_available_tools(self, user_roles: List[str]) -> List[str]:
        """
        Get list of tools available to user based on roles.
        
        Args:
            user_roles: List of user's roles
            
        Returns:
            List[str]: List of available tool names
        """
        permissions = self.get_permissions(user_roles)
        tools = []
        
        for permission in permissions:
            if permission.startswith("tool:"):
                tool_name = permission[5:]  # Remove "tool:" prefix
                if tool_name != "*":
                    tools.append(tool_name)
                else:
                    # Wildcard permission - return all tools
                    return [
                        "generate_bdd_scenario",
                        "generate_element_locator",
                        "generate_test_step", 
                        "heal_broken_selector",
                        "analyze_test_failure"
                    ]
        
        return tools
    
    def get_available_resources(self, user_roles: List[str]) -> List[str]:
        """
        Get list of resources available to user based on roles.
        
        Args:
            user_roles: List of user's roles
            
        Returns:
            List[str]: List of available resource types
        """
        permissions = self.get_permissions(user_roles)
        resources = []
        
        for permission in permissions:
            if permission.startswith("resource:"):
                resource_type = permission[9:]  # Remove "resource:" prefix
                if resource_type != "*":
                    resources.append(resource_type)
                else:
                    # Wildcard permission - return all resources
                    return ["dom", "execution", "schema"]
        
        return resources
    
    def validate_tenant_access(
        self, 
        user_tenant_id: Optional[str], 
        resource_tenant_id: Optional[str]
    ) -> bool:
        """
        Validate tenant isolation for multi-tenant deployments.
        
        Args:
            user_tenant_id: User's tenant ID
            resource_tenant_id: Resource's tenant ID
            
        Returns:
            bool: True if access is allowed
        """
        # No tenant isolation if both are None
        if user_tenant_id is None and resource_tenant_id is None:
            return True
        
        # Must match for tenant isolation
        return user_tenant_id == resource_tenant_id


class AuditLogger:
    """
    Audit logging for authentication and authorization events.
    
    Provides comprehensive audit trail for security events, tool usage,
    and resource access in the MCP server.
    """
    
    def __init__(self):
        self.settings = get_settings()
    
    async def log_authentication_attempt(
        self, 
        user_id: Optional[str], 
        success: bool, 
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log authentication attempt."""
        event = {
            "event_type": "authentication",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "success": success,
            "error_message": error_message,
            "ip_address": ip_address
        }
        
        # TODO: Implement audit log storage (file, database, external service)
        print(f"AUDIT: {event}")
    
    async def log_tool_access(
        self, 
        user_context: UserContext, 
        tool_name: str, 
        success: bool,
        request_data: Optional[Dict[str, Any]] = None
    ):
        """Log tool access attempt."""
        event = {
            "event_type": "tool_access",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_context.user_id,
            "username": user_context.username,
            "tenant_id": user_context.tenant_id,
            "tool_name": tool_name,
            "success": success,
            "request_data": request_data
        }
        
        # TODO: Implement audit log storage
        print(f"AUDIT: {event}")
    
    async def log_resource_access(
        self, 
        user_context: UserContext, 
        resource_uri: str, 
        success: bool
    ):
        """Log resource access attempt."""
        event = {
            "event_type": "resource_access",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_context.user_id,
            "username": user_context.username,
            "tenant_id": user_context.tenant_id,
            "resource_uri": resource_uri,
            "success": success
        }
        
        # TODO: Implement audit log storage
        print(f"AUDIT: {event}") 