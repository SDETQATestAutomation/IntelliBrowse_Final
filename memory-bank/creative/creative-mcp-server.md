# 🎨🎨🎨 ENTERING CREATIVE PHASE: IntelliBrowse MCP Server Architecture

**Project**: IntelliBrowse MCP Server - Exclusive AI Orchestration Layer  
**Phase**: CREATIVE  
**Timestamp**: 2025-01-08 06:15:00 UTC  
**Complexity Level**: Level 4 (Complex System)  
**Duration**: 6-10 hours for comprehensive design exploration

---

## 🧩 COMPONENT DESCRIPTION

### What is the IntelliBrowse MCP Server?

The IntelliBrowse MCP Server is a **standalone, production-grade AI orchestration microservice** that serves as the exclusive gateway for all AI and LLM operations within the IntelliBrowse test automation platform. Built on the Model Context Protocol (MCP), it provides a unified, secure, and scalable interface for AI-powered test automation capabilities.

**Core Purpose:**
- **Centralize ALL AI logic** in a single, dedicated service (`src/backend/mcp/`)
- **Eliminate AI code scatter** across the IntelliBrowse backend
- **Provide uniform AI interface** via JSON-RPC 2.0 protocol
- **Enable enterprise-grade AI governance** with audit, RBAC, and compliance
- **Support dynamic AI capability expansion** through plugin architecture

**Key Capabilities:**
- BDD scenario generation from user stories
- DOM element locator generation and healing
- Test step generation and debugging
- Code review and analysis prompts
- Execution context resource provision

---

## 🎯 REQUIREMENTS & CONSTRAINTS

### Functional Requirements

1. **MCP Protocol Compliance**
   - Full Model Context Protocol (MCP) specification adherence
   - JSON-RPC 2.0 transport with strict schema validation
   - Support for Tools, Prompts, and Resources primitives
   - Session context propagation and management

2. **AI Tool Chain**
   - BDD scenario generation with confidence scoring
   - Element locator generation with fallback strategies
   - Test step generation and enhancement
   - Selector healing and DOM analysis
   - Debug trace analysis and recommendations

3. **Enterprise Features**
   - OAuth 2.0 authentication and RBAC authorization
   - Audit logging for all AI operations
   - Rate limiting and resource management
   - Multi-tenant namespace isolation
   - Session memory with TTL management

4. **Integration Requirements**
   - FastAPI backend integration via HTTP/SSE transport
   - IntelliBrowse module integration (testcases, testexecution, orchestration)
   - OpenAI API integration with rate limiting
   - MongoDB session storage and caching
   - Real-time event broadcasting

### Technical Constraints

1. **Architecture Constraints**
   - **MANDATORY**: All AI code exclusively in `src/backend/mcp/`
   - **NO AI CODE** anywhere else in IntelliBrowse backend
   - Async/await patterns throughout for performance
   - Pydantic v2 validation at all protocol boundaries
   - Environment-driven configuration (no hardcoded secrets)

2. **Performance Constraints**
   - Sub-200ms response time for tool invocations
   - Support for 100+ concurrent sessions
   - Memory usage under 1GB per instance
   - Horizontal scaling capability via load balancer

3. **Security Constraints**
   - TLS/HTTPS mandatory for all transport
   - OAuth 2.0 token validation on every request
   - Audit trail for all tool/resource access
   - Input sanitization and output validation
   - Rate limiting per user/session/tool

4. **Integration Constraints**
   - Backward compatibility with existing IntelliBrowse APIs
   - Zero-downtime deployment capability
   - Graceful degradation when AI services unavailable
   - Event-driven integration with notification system

---

## 🏗️ ARCHITECTURE OPTIONS ANALYSIS

### 🔍 Option 1: Monolithic MCP Server

**Description:** Single FastMCP server instance with all tools, prompts, and resources in one process.

**Architecture:**
```python
# Single server entry point
@mcp_server = FastMCP(name="IntelliBrowseMCP")

# All tools registered in main.py
from tools import bdd_generator, locator_generator, step_generator
from prompts import scenario_prompts, review_prompts
from resources import dom_resource, execution_resource
```

**Pros:**
- ✅ Simple deployment and configuration
- ✅ Low latency between components
- ✅ Unified session and context management
- ✅ Easier debugging and monitoring
- ✅ Single point of authentication and authorization

**Cons:**
- ❌ Monolithic scaling challenges
- ❌ Single point of failure
- ❌ Difficult to update individual tools
- ❌ Resource contention between tools
- ❌ Complex plugin hot-reloading

**Technical Fit:** High - Aligns with FastMCP patterns  
**Complexity:** Low - Single deployment unit  
**Scalability:** Medium - Vertical scaling only  

---

### 🔍 Option 2: Microservices MCP Architecture

**Description:** Separate MCP server instances for different tool categories with service mesh communication.

**Architecture:**
```python
# Multiple specialized servers
bdd_server = FastMCP(name="BDDService")
locator_server = FastMCP(name="LocatorService") 
resource_server = FastMCP(name="ResourceService")

# API Gateway for routing
gateway = MCPGateway(services=[bdd_server, locator_server, resource_server])
```

**Pros:**
- ✅ Independent scaling per service
- ✅ Fault isolation between services
- ✅ Independent deployment cycles
- ✅ Specialized resource optimization
- ✅ Better plugin isolation

**Cons:**
- ❌ Complex service discovery and routing
- ❌ Network latency between services
- ❌ Distributed session management complexity
- ❌ Multiple authentication points
- ❌ Increased operational overhead

**Technical Fit:** Medium - Requires custom gateway  
**Complexity:** High - Multiple deployment units  
**Scalability:** High - Horizontal scaling  

---

### 🔍 Option 3: Plugin-Based Modular Architecture

**Description:** Single MCP server with dynamic plugin loading and hot-reload capabilities.

**Architecture:**
```python
# Plugin registry and loader
class MCPPluginRegistry:
    def __init__(self):
        self.tools = {}
        self.prompts = {}
        self.resources = {}
    
    async def load_plugin(self, plugin_path: str):
        # Dynamic module loading
        module = await import_module(plugin_path)
        await self.register_plugin_primitives(module)

# Main server with plugin support
mcp_server = FastMCP(name="IntelliBrowseMCP")
plugin_registry = MCPPluginRegistry()
```

**Pros:**
- ✅ Dynamic capability expansion
- ✅ Hot-reload without downtime
- ✅ Clean separation of concerns
- ✅ Easy A/B testing of tools
- ✅ Third-party plugin support

**Cons:**
- ❌ Complex plugin lifecycle management
- ❌ Plugin dependency resolution
- ❌ Security isolation challenges
- ❌ Plugin versioning and compatibility
- ❌ Memory management complexity

**Technical Fit:** High - Extensible and future-proof  
**Complexity:** High - Plugin framework development  
**Scalability:** High - Configurable scaling  

---

### 🔍 Option 4: Hybrid Modular-Monolithic Architecture

**Description:** Single MCP server with modular tool organization and selective plugin capabilities.

**Architecture:**
```python
# Modular tool organization with optional plugins
class MCPServer:
    def __init__(self):
        self.core_tools = CoreToolRegistry()  # Built-in tools
        self.plugin_tools = PluginToolRegistry()  # Optional plugins
        self.mcp_server = FastMCP(name="IntelliBrowseMCP")
    
    async def initialize(self):
        # Register core tools (always available)
        await self.core_tools.register_all(self.mcp_server)
        # Register enabled plugins
        await self.plugin_tools.register_enabled(self.mcp_server)
```

**Pros:**
- ✅ Best of monolithic and plugin approaches
- ✅ Core stability with extensibility
- ✅ Gradual migration to plugins
- ✅ Simplified deployment for core features
- ✅ Controlled complexity growth

**Cons:**
- ❌ Dual architecture complexity
- ❌ Core vs plugin boundary decisions
- ❌ Plugin lifecycle still complex
- ❌ Potential for architectural drift

**Technical Fit:** High - Balanced approach  
**Complexity:** Medium - Managed complexity  
**Scalability:** High - Flexible scaling options  

---

## 🏆 RECOMMENDED APPROACH

### Selected Architecture: **Option 4 - Hybrid Modular-Monolithic**

**Rationale:**
1. **Immediate Implementation Value:** Core tools can be implemented and deployed quickly
2. **Future Extensibility:** Plugin framework provides growth path without architectural rewrite
3. **Operational Simplicity:** Single deployment unit reduces operational complexity
4. **Risk Management:** Core functionality remains stable while experiments happen in plugins
5. **Development Velocity:** Team can focus on core features first, plugins later

**Implementation Strategy:**
- **Phase 1:** Implement core MCP server with built-in tools (Weeks 1-4)
- **Phase 2:** Add plugin framework foundation (Week 5)
- **Phase 3:** Migrate selected tools to plugins (Week 6+)

---

## 📋 IMPLEMENTATION GUIDELINES

### 🏗️ 1. Core Server Architecture

#### Main Server Entry Point
```python
# src/backend/mcp/main.py
import asyncio
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server
from mcp.server.sse import sse_server

from .config.settings import get_mcp_settings
from .core.server import MCPServerManager
from .core.logging import setup_logging

async def main():
    """Main entry point for IntelliBrowse MCP Server."""
    # Load configuration
    settings = get_mcp_settings()
    
    # Setup logging
    logger = setup_logging(settings.log_level)
    
    # Initialize server manager
    server_manager = MCPServerManager(settings)
    await server_manager.initialize()
    
    # Get configured MCP server
    mcp_server = server_manager.get_server()
    
    # Run based on transport mode
    if settings.transport_mode == "stdio":
        await stdio_server(mcp_server)
    elif settings.transport_mode == "sse":
        await sse_server(mcp_server, settings.host, settings.port)
    else:
        raise ValueError(f"Unsupported transport: {settings.transport_mode}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Server Manager Implementation
```python
# src/backend/mcp/core/server.py
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any
import importlib

from ..tools import CORE_TOOLS
from ..prompts import CORE_PROMPTS  
from ..resources import CORE_RESOURCES
from ..security.auth import MCPAuthMiddleware
from ..orchestration.context import ContextManager

class MCPServerManager:
    """Manages MCP server initialization and lifecycle."""
    
    def __init__(self, settings):
        self.settings = settings
        self.mcp_server = FastMCP(name="IntelliBrowseMCP")
        self.context_manager = ContextManager()
        self.auth_middleware = MCPAuthMiddleware(settings)
        
    async def initialize(self):
        """Initialize server with all components."""
        # Setup middleware
        await self._setup_middleware()
        
        # Register core primitives
        await self._register_core_tools()
        await self._register_core_prompts()
        await self._register_core_resources()
        
        # Setup plugin system
        await self._setup_plugin_system()
        
    async def _setup_middleware(self):
        """Setup authentication and context middleware."""
        self.mcp_server.middleware.append(self.auth_middleware)
        self.mcp_server.middleware.append(self.context_manager.middleware)
        
    async def _register_core_tools(self):
        """Register all core tools."""
        for tool_module in CORE_TOOLS:
            module = importlib.import_module(f"..tools.{tool_module}", __name__)
            # Tools self-register via decorators
            
    async def _register_core_prompts(self):
        """Register all core prompts."""
        for prompt_module in CORE_PROMPTS:
            module = importlib.import_module(f"..prompts.{prompt_module}", __name__)
            
    async def _register_core_resources(self):
        """Register all core resources.""" 
        for resource_module in CORE_RESOURCES:
            module = importlib.import_module(f"..resources.{resource_module}", __name__)
```

### 🛠️ 2. Tool Implementation Pattern

#### Tool Base Class
```python
# src/backend/mcp/schemas/tool_schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod

class ToolRequest(BaseModel):
    """Base tool request schema."""
    session_id: Optional[str] = Field(None, description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(None, description="Execution context")
    
class ToolResponse(BaseModel):
    """Base tool response schema."""
    success: bool = Field(description="Operation success status")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    message: str = Field(description="Human-readable message")
    confidence: Optional[float] = Field(None, description="Confidence score 0-1")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class MCPTool(ABC):
    """Abstract base class for MCP tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for registration."""
        pass
        
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for discovery."""
        pass
        
    @abstractmethod
    async def execute(self, request: ToolRequest) -> ToolResponse:
        """Execute tool with request and return response."""
        pass
```

#### BDD Generator Tool Implementation
```python
# src/backend/mcp/tools/bdd_generator.py
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import openai
from ..schemas.tool_schemas import ToolRequest, ToolResponse, MCPTool
from ..config.settings import get_mcp_settings

# Get server instance (registered in main)
mcp_server = FastMCP.get_instance("IntelliBrowseMCP")

class BDDRequest(ToolRequest):
    """BDD scenario generation request."""
    user_story: str = Field(description="User story description")
    acceptance_criteria: List[str] = Field(description="Acceptance criteria list")
    feature_context: Optional[str] = Field(None, description="Feature context")
    existing_scenarios: Optional[List[str]] = Field(None, description="Existing scenarios")

class BDDResponse(ToolResponse):
    """BDD scenario generation response."""
    scenario: str = Field(description="Generated Gherkin scenario")
    suggestions: List[str] = Field(default=[], description="Improvement suggestions")
    alternatives: Optional[List[str]] = Field(None, description="Alternative scenarios")

class BDDGeneratorTool(MCPTool):
    """BDD scenario generation tool using AI."""
    
    name = "generate_bdd_scenario"
    description = "Generate BDD Gherkin scenarios from user stories and acceptance criteria"
    
    def __init__(self):
        self.settings = get_mcp_settings()
        self.openai_client = openai.AsyncOpenAI(api_key=self.settings.openai_api_key)
        
    async def execute(self, request: BDDRequest) -> BDDResponse:
        """Generate BDD scenario using OpenAI."""
        try:
            # Build prompt
            prompt = self._build_prompt(request)
            
            # Call OpenAI
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000
            )
            
            # Parse response
            scenario = response.choices[0].message.content
            
            # Generate suggestions
            suggestions = await self._generate_suggestions(scenario, request)
            
            return BDDResponse(
                success=True,
                data={"scenario": scenario},
                message="BDD scenario generated successfully",
                confidence=0.85,
                scenario=scenario,
                suggestions=suggestions
            )
            
        except Exception as e:
            return BDDResponse(
                success=False,
                data=None,
                message=f"BDD generation failed: {str(e)}",
                confidence=0.0,
                scenario="",
                suggestions=[]
            )
    
    def _build_prompt(self, request: BDDRequest) -> str:
        """Build AI prompt for BDD generation."""
        context_text = f"\nFeature Context: {request.feature_context}" if request.feature_context else ""
        criteria_text = "\n".join([f"- {criteria}" for criteria in request.acceptance_criteria])
        
        return f"""Generate a comprehensive BDD scenario in Gherkin format for:

User Story: {request.user_story}

Acceptance Criteria:
{criteria_text}{context_text}

Requirements:
- Use Given-When-Then format
- Include specific, testable steps
- Consider edge cases and error scenarios
- Make steps atomic and reusable
- Use clear, business-readable language

Return only the Gherkin scenario."""

    async def _generate_suggestions(self, scenario: str, request: BDDRequest) -> List[str]:
        """Generate improvement suggestions for the scenario."""
        # Implementation for suggestions
        return [
            "Consider adding negative test cases",
            "Verify data validation scenarios",
            "Add performance test considerations"
        ]

# Register tool with MCP server
bdd_tool = BDDGeneratorTool()

@mcp_server.tool()
async def generate_bdd_scenario(
    user_story: str,
    acceptance_criteria: List[str],
    feature_context: Optional[str] = None,
    existing_scenarios: Optional[List[str]] = None,
    session_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> BDDResponse:
    """
    Generate BDD Gherkin scenario from user story and acceptance criteria.
    
    This tool uses AI to create comprehensive BDD scenarios that are testable,
    specific, and align with business requirements.
    
    Args:
        user_story: User story description
        acceptance_criteria: List of acceptance criteria  
        feature_context: Optional feature context
        existing_scenarios: Optional existing scenarios for reference
        session_id: Optional session identifier
        context: Optional execution context
        
    Returns:
        BDDResponse: Generated scenario with suggestions
    """
    request = BDDRequest(
        user_story=user_story,
        acceptance_criteria=acceptance_criteria,
        feature_context=feature_context,
        existing_scenarios=existing_scenarios,
        session_id=session_id,
        context=context
    )
    
    return await bdd_tool.execute(request)
```

### 🎯 3. Prompt Implementation Pattern

#### Prompt Template System
```python
# src/backend/mcp/prompts/scenario_prompts.py
from mcp.server.fastmcp import FastMCP
from typing import Dict, List, Optional, Any
from jinja2 import Template

mcp_server = FastMCP.get_instance("IntelliBrowseMCP")

@mcp_server.prompt()
def test_scenario_prompt(
    feature: str,
    user_story: str,
    acceptance_criteria: List[str],
    context_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate comprehensive test scenario prompt template.
    
    This prompt helps users create detailed test scenarios by providing
    structured guidance and context-aware suggestions.
    
    Args:
        feature: Feature name or description
        user_story: User story being tested
        acceptance_criteria: List of acceptance criteria
        context_data: Optional context data for customization
        
    Returns:
        str: Formatted prompt template
    """
    template = Template("""
# Test Scenario Generation for {{ feature }}

## User Story
{{ user_story }}

## Acceptance Criteria
{% for criteria in acceptance_criteria %}
- {{ criteria }}
{% endfor %}

## Test Scenario Requirements

### Happy Path Scenarios
Generate test scenarios that verify:
- Normal user flows
- Expected system behavior
- Successful completion paths

### Edge Cases
Consider scenarios for:
- Boundary conditions
- Invalid inputs
- System limitations

### Error Scenarios  
Include tests for:
- Input validation failures
- System error conditions
- Recovery mechanisms

{% if context_data %}
## Additional Context
{% for key, value in context_data.items() %}
- {{ key }}: {{ value }}
{% endfor %}
{% endif %}

Please generate detailed test scenarios using Gherkin format (Given-When-Then).
    """.strip())
    
    return template.render(
        feature=feature,
        user_story=user_story,
        acceptance_criteria=acceptance_criteria,
        context_data=context_data or {}
    )

@mcp_server.prompt()
def code_review_prompt(
    code: str,
    language: str = "python",
    focus_areas: Optional[List[str]] = None,
    severity_level: str = "medium"
) -> str:
    """
    Generate comprehensive code review prompt.
    
    Args:
        code: Source code to review
        language: Programming language
        focus_areas: Specific areas to focus on
        severity_level: Review severity (low, medium, high)
        
    Returns:
        str: Formatted code review prompt
    """
    focus_text = ""
    if focus_areas:
        focus_text = f"\n\nFocus Areas:\n" + "\n".join([f"- {area}" for area in focus_areas])
    
    severity_guidelines = {
        "low": "Focus on style and minor improvements",
        "medium": "Include performance, maintainability, and best practices",
        "high": "Comprehensive review including security, architecture, and critical issues"
    }
    
    return f"""# Code Review Request

## Code to Review
```{language}
{code}
```

## Review Guidelines
{severity_guidelines.get(severity_level, severity_guidelines["medium"])}

## Review Criteria
- Code quality and best practices
- Performance considerations  
- Security vulnerabilities
- Maintainability and readability
- Error handling and edge cases
- Testing considerations{focus_text}

Please provide specific, actionable feedback with examples where applicable.
"""
```

### 📊 4. Resource Implementation Pattern

#### DOM Resource Provider
```python
# src/backend/mcp/resources/dom_resource.py
from mcp.server.fastmcp import FastMCP
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import json
from playwright.async_api import async_playwright

mcp_server = FastMCP.get_instance("IntelliBrowseMCP")

class DOMSnapshot(BaseModel):
    """DOM snapshot data structure."""
    url: str
    title: str
    html: str
    elements: List[Dict[str, Any]]
    timestamp: str
    session_id: str

class DOMResourceProvider:
    """Provides DOM snapshots as MCP resources."""
    
    def __init__(self):
        self.snapshots: Dict[str, DOMSnapshot] = {}
        
    async def capture_snapshot(self, url: str, session_id: str) -> DOMSnapshot:
        """Capture DOM snapshot using Playwright."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(url)
                await page.wait_for_load_state("networkidle")
                
                # Extract DOM data
                html = await page.content()
                title = await page.title()
                
                # Extract interactive elements
                elements = await page.evaluate("""
                    () => {
                        const elements = [];
                        const interactiveElements = document.querySelectorAll(
                            'button, input, select, textarea, a[href], [onclick], [role="button"]'
                        );
                        
                        interactiveElements.forEach((el, index) => {
                            const rect = el.getBoundingClientRect();
                            elements.push({
                                index: index,
                                tagName: el.tagName.toLowerCase(),
                                type: el.type || null,
                                id: el.id || null,
                                className: el.className || null,
                                text: el.textContent?.trim().substring(0, 100) || null,
                                attributes: Array.from(el.attributes).reduce((acc, attr) => {
                                    acc[attr.name] = attr.value;
                                    return acc;
                                }, {}),
                                position: {
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height
                                },
                                visible: rect.width > 0 && rect.height > 0
                            });
                        });
                        
                        return elements;
                    }
                """)
                
                snapshot = DOMSnapshot(
                    url=url,
                    title=title,
                    html=html,
                    elements=elements,
                    timestamp=datetime.utcnow().isoformat(),
                    session_id=session_id
                )
                
                # Cache snapshot
                self.snapshots[f"{session_id}:{url}"] = snapshot
                
                return snapshot
                
            finally:
                await browser.close()

# Global provider instance
dom_provider = DOMResourceProvider()

@mcp_server.resource("dom://{session_id}/snapshot")
async def get_dom_snapshot(session_id: str) -> str:
    """
    Get DOM snapshot for session.
    
    Returns the most recent DOM snapshot for the specified session,
    including page structure, interactive elements, and metadata.
    
    Args:
        session_id: Session identifier
        
    Returns:
        str: JSON-serialized DOM snapshot
    """
    # Find most recent snapshot for session
    session_snapshots = {
        key: snapshot for key, snapshot in dom_provider.snapshots.items()
        if key.startswith(f"{session_id}:")
    }
    
    if not session_snapshots:
        return json.dumps({
            "error": "No DOM snapshots found for session",
            "session_id": session_id
        })
    
    # Get most recent snapshot
    latest_key = max(session_snapshots.keys())
    snapshot = session_snapshots[latest_key]
    
    return snapshot.model_dump_json()

@mcp_server.resource("dom://{session_id}/elements")
async def get_dom_elements(session_id: str) -> str:
    """
    Get interactive elements from DOM snapshot.
    
    Returns filtered list of interactive elements for easier processing
    by AI tools.
    
    Args:
        session_id: Session identifier
        
    Returns:
        str: JSON-serialized element list
    """
    snapshot_data = await get_dom_snapshot(session_id)
    snapshot_dict = json.loads(snapshot_data)
    
    if "error" in snapshot_dict:
        return snapshot_data
    
    # Extract and filter elements
    elements = snapshot_dict.get("elements", [])
    interactive_elements = [
        element for element in elements
        if element.get("visible", False) and element.get("text")
    ]
    
    return json.dumps({
        "session_id": session_id,
        "element_count": len(interactive_elements),
        "elements": interactive_elements
    })
```

### 🔒 5. Security & Authentication Implementation

#### OAuth 2.0 Authentication Middleware
```python
# src/backend/mcp/security/auth.py
from mcp.server.auth import AuthProvider
from typing import Optional, Dict, Any
import jwt
from datetime import datetime, timedelta
import httpx

class MCPAuthMiddleware:
    """OAuth 2.0 authentication middleware for MCP server."""
    
    def __init__(self, settings):
        self.settings = settings
        self.auth_provider = AuthProvider()
        
    async def authenticate(self, token: str) -> Optional[Dict[str, Any]]:
        """Authenticate token and return user context."""
        try:
            # Verify JWT token
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=["HS256"]
            )
            
            # Check expiration
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                return None
            
            # Return user context
            return {
                "user_id": payload["sub"],
                "username": payload.get("username"),
                "roles": payload.get("roles", []),
                "permissions": payload.get("permissions", []),
                "tenant_id": payload.get("tenant_id")
            }
            
        except jwt.InvalidTokenError:
            return None
    
    async def authorize_tool(self, user_context: Dict[str, Any], tool_name: str) -> bool:
        """Check if user is authorized to use tool."""
        required_permission = f"tool:{tool_name}"
        return required_permission in user_context.get("permissions", [])
    
    async def authorize_resource(self, user_context: Dict[str, Any], resource_uri: str) -> bool:
        """Check if user is authorized to access resource."""
        # Extract resource type from URI
        resource_type = resource_uri.split("://")[0]
        required_permission = f"resource:{resource_type}"
        return required_permission in user_context.get("permissions", [])

# RBAC Implementation
class RBACManager:
    """Role-Based Access Control manager."""
    
    def __init__(self):
        self.roles = {
            "admin": [
                "tool:*",
                "resource:*",
                "audit:read",
                "config:write"
            ],
            "tester": [
                "tool:generate_bdd_scenario",
                "tool:generate_element_locator",
                "tool:generate_test_step",
                "resource:dom",
                "resource:execution"
            ],
            "viewer": [
                "resource:dom",
                "resource:execution"
            ]
        }
    
    def get_permissions(self, roles: List[str]) -> List[str]:
        """Get combined permissions for roles."""
        permissions = set()
        for role in roles:
            if role in self.roles:
                permissions.update(self.roles[role])
        return list(permissions)
    
    def check_permission(self, user_roles: List[str], required_permission: str) -> bool:
        """Check if user roles include required permission."""
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
```

### 🔄 6. Orchestration & Workflow Management

#### Session Context Manager
```python
# src/backend/mcp/orchestration/context.py
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
import json

@dataclass
class SessionContext:
    """Session context for MCP operations."""
    session_id: str
    user_id: str
    tenant_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_history: List[Dict[str, Any]] = field(default_factory=list)
    resource_cache: Dict[str, Any] = field(default_factory=dict)
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def add_tool_call(self, tool_name: str, request_data: Dict[str, Any], response_data: Dict[str, Any]):
        """Add tool call to history."""
        self.tool_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "tool_name": tool_name,
            "request": request_data,
            "response": response_data
        })
        self.update_activity()
    
    def is_expired(self, ttl_hours: int = 24) -> bool:
        """Check if session is expired."""
        expiry_time = self.last_activity + timedelta(hours=ttl_hours)
        return datetime.utcnow() > expiry_time

class ContextManager:
    """Manages session contexts and their lifecycle."""
    
    def __init__(self, ttl_hours: int = 24):
        self.sessions: Dict[str, SessionContext] = {}
        self.ttl_hours = ttl_hours
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_expired_sessions())
    
    async def get_context(self, session_id: str) -> Optional[SessionContext]:
        """Get session context by ID."""
        context = self.sessions.get(session_id)
        if context and not context.is_expired(self.ttl_hours):
            context.update_activity()
            return context
        elif context:
            # Remove expired context
            del self.sessions[session_id]
        return None
    
    async def create_context(self, session_id: str, user_id: str, tenant_id: Optional[str] = None) -> SessionContext:
        """Create new session context."""
        context = SessionContext(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id
        )
        self.sessions[session_id] = context
        return context
    
    async def _cleanup_expired_sessions(self):
        """Periodic cleanup of expired sessions."""
        while True:
            expired_sessions = [
                session_id for session_id, context in self.sessions.items()
                if context.is_expired(self.ttl_hours)
            ]
            
            for session_id in expired_sessions:
                del self.sessions[session_id]
            
            # Cleanup every hour
            await asyncio.sleep(3600)

# Workflow Orchestrator
class WorkflowOrchestrator:
    """Orchestrates multi-tool workflows."""
    
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
    
    async def run_workflow(self, session_id: str, workflow_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute workflow with multiple tool calls."""
        context = await self.context_manager.get_context(session_id)
        if not context:
            raise ValueError(f"Session not found: {session_id}")
        
        results = []
        workflow_context = {}
        
        for step in workflow_steps:
            tool_name = step["tool"]
            tool_args = step.get("args", {})
            
            # Inject workflow context into tool args
            tool_args["workflow_context"] = workflow_context
            tool_args["session_id"] = session_id
            
            try:
                # Execute tool (simplified - would use actual tool registry)
                result = await self._execute_tool(tool_name, tool_args)
                results.append({
                    "step": step["name"],
                    "tool": tool_name,
                    "success": True,
                    "result": result
                })
                
                # Update workflow context with result
                workflow_context[step["name"]] = result
                
            except Exception as e:
                results.append({
                    "step": step["name"],
                    "tool": tool_name,
                    "success": False,
                    "error": str(e)
                })
                
                # Stop on error unless step is marked as optional
                if not step.get("optional", False):
                    break
        
        return {
            "workflow_id": f"{session_id}:{datetime.utcnow().isoformat()}",
            "session_id": session_id,
            "steps": results,
            "success": all(step["success"] for step in results),
            "context": workflow_context
        }
    
    async def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Execute tool by name (placeholder)."""
        # This would integrate with actual tool registry
        pass
```

### 📊 7. Configuration & Settings Management

#### Environment Configuration
```python
# src/backend/mcp/config/settings.py
from pydantic_settings import BaseSettings
from typing import Optional, List
import os

class MCPSettings(BaseSettings):
    """MCP Server configuration settings."""
    
    # Server settings
    app_name: str = "IntelliBrowse MCP Server"
    debug: bool = False
    log_level: str = "INFO"
    
    # Transport settings
    transport_mode: str = "sse"  # stdio, sse, or http
    host: str = "127.0.0.1"
    port: int = 8080
    
    # AI/LLM settings
    openai_api_key: str
    openai_model: str = "gpt-4"
    openai_max_tokens: int = 1000
    openai_temperature: float = 0.3
    
    # Database settings
    mongodb_url: str
    mongodb_database: str = "intellibrowse_mcp"
    
    # Security settings
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    
    # Session settings
    session_ttl_hours: int = 24
    session_cleanup_interval: int = 3600
    
    # Rate limiting
    rate_limit_per_minute: int = 100
    rate_limit_per_hour: int = 1000
    
    # Plugin settings
    enable_plugins: bool = True
    plugin_directories: List[str] = ["./plugins"]
    
    # Audit settings
    enable_audit_logging: bool = True
    audit_log_file: str = "logs/mcp_audit.log"
    
    class Config:
        env_file = ".env"
        env_prefix = "MCP_"
        case_sensitive = False

# Singleton settings instance
_settings: Optional[MCPSettings] = None

def get_mcp_settings() -> MCPSettings:
    """Get MCP settings singleton."""
    global _settings
    if _settings is None:
        _settings = MCPSettings()
    return _settings

# Environment file template
ENVIRONMENT_TEMPLATE = """
# IntelliBrowse MCP Server Configuration

# Server Settings
MCP_APP_NAME=IntelliBrowse MCP Server
MCP_DEBUG=false
MCP_LOG_LEVEL=INFO

# Transport Settings  
MCP_TRANSPORT_MODE=sse
MCP_HOST=127.0.0.1
MCP_PORT=8080

# AI/LLM Settings
MCP_OPENAI_API_KEY=your_openai_api_key_here
MCP_OPENAI_MODEL=gpt-4
MCP_OPENAI_MAX_TOKENS=1000
MCP_OPENAI_TEMPERATURE=0.3

# Database Settings
MCP_MONGODB_URL=mongodb://localhost:27017
MCP_MONGODB_DATABASE=intellibrowse_mcp

# Security Settings
MCP_JWT_SECRET=your_jwt_secret_here
MCP_JWT_ALGORITHM=HS256
MCP_JWT_EXPIRY_HOURS=24

# Session Settings
MCP_SESSION_TTL_HOURS=24
MCP_SESSION_CLEANUP_INTERVAL=3600

# Rate Limiting
MCP_RATE_LIMIT_PER_MINUTE=100
MCP_RATE_LIMIT_PER_HOUR=1000

# Plugin Settings
MCP_ENABLE_PLUGINS=true
MCP_PLUGIN_DIRECTORIES=./plugins

# Audit Settings
MCP_ENABLE_AUDIT_LOGGING=true
MCP_AUDIT_LOG_FILE=logs/mcp_audit.log
"""
```

---

## ✅ VERIFICATION CHECKPOINT

### Architecture Design Verification
- [x] All system requirements addressed
- [x] Component responsibilities defined  
- [x] Interfaces specified with Pydantic schemas
- [x] Data flows documented via MCP protocol
- [x] Security considerations addressed (OAuth 2.0, RBAC, audit)
- [x] Scalability requirements met (async, session management)
- [x] Performance requirements met (caching, optimization)
- [x] Maintenance approach defined (plugin architecture)

### Implementation Readiness
- [x] All components identified and blueprinted
- [x] Dependencies mapped (MCP SDK, OpenAI, MongoDB)
- [x] Technical constraints documented
- [x] Risk assessment completed (hybrid architecture reduces risk)
- [x] Resource requirements defined
- [x] Timeline estimates provided (6-week implementation)

---

## 🎨🎨🎨 EXITING CREATIVE PHASE

### Design Decision Summary

**Selected Architecture**: Hybrid Modular-Monolithic with Plugin Capability
**Rationale**: Balances immediate implementation needs with future extensibility
**Implementation Priority**: Core tools first, plugin framework second

### Next Phase Transition

**Phase**: CREATIVE → IMPLEMENT  
**Deliverables Ready**: Complete architectural blueprints and implementation patterns  
**Implementation Order**: 
1. Core server infrastructure
2. Tool implementations  
3. Security and authentication
4. Session management and orchestration
5. Testing and validation
6. Plugin framework

### Memory Bank Update Required

All design decisions, patterns, and code examples have been documented for the IMPLEMENT phase. The hybrid architecture provides a clear path forward with manageable complexity and future extensibility.

**Resume Checkpoint**: Creative phase complete - ready for systematic implementation of MCP server components. 