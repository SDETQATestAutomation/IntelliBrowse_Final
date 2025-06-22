"""
Session context management and workflow orchestration for IntelliBrowse MCP Server.

This module provides session lifecycle management, context persistence,
and workflow orchestration capabilities for MCP operations.

Enhanced with comprehensive browser state tracking and cross-tool context propagation.
"""

import asyncio
import json
from typing import Dict, Any, Optional, List, Set, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict
import uuid
import pickle
import os
from pathlib import Path

try:
    from config.settings import MCPSettings
except ImportError:
    # Fallback for when running directly from mcp directory
    from config.settings import MCPSettings

try:
    from schemas.context_schemas import SessionContext, TaskContext, UserContext
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.context_schemas import SessionContext, TaskContext, UserContext

try:
    from core.exceptions import SessionError, ContextError
except ImportError:
    # Fallback for when running directly from mcp directory
    from core.exceptions import SessionError, ContextError

def get_settings():
    """Get MCP settings instance."""
    return MCPSettings()


@dataclass
class BrowserState:
    """Browser state tracking for comprehensive state management."""
    browser_id: str
    browser_type: str = "chromium"  # chromium, firefox, webkit
    current_url: Optional[str] = None
    page_title: Optional[str] = None
    viewport_size: Optional[Dict[str, int]] = None
    cookies: List[Dict[str, str]] = field(default_factory=list)
    local_storage: Dict[str, str] = field(default_factory=dict)
    session_storage: Dict[str, str] = field(default_factory=dict)
    form_data: Dict[str, Dict[str, str]] = field(default_factory=dict)  # form_id -> field_data
    scroll_position: Dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0})
    active_element: Optional[str] = None  # CSS selector or locator
    dom_snapshot_hash: Optional[str] = None
    network_requests: List[Dict[str, Any]] = field(default_factory=list)
    console_logs: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def update_state(self, **kwargs):
        """Update browser state with new values."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert browser state to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BrowserState':
        """Create browser state from dictionary."""
        # Handle datetime serialization
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


@dataclass
class CrossToolContext:
    """Cross-tool context for sharing data between tool executions."""
    context_id: str
    session_id: str
    tool_chain: List[str] = field(default_factory=list)  # Tools executed in sequence
    shared_variables: Dict[str, Any] = field(default_factory=dict)
    element_registry: Dict[str, str] = field(default_factory=dict)  # element_name -> locator
    page_objects: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # page_name -> elements
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    error_recovery_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_tool_execution(self, tool_name: str, input_data: Dict[str, Any], output_data: Dict[str, Any]):
        """Add tool execution to the chain."""
        self.tool_chain.append(tool_name)
        
        # Extract shared variables from tool output
        if isinstance(output_data, dict):
            # Store locators for future use
            if 'locator' in output_data:
                element_key = f"{tool_name}_{len(self.tool_chain)}"
                self.element_registry[element_key] = output_data['locator']
            
            # Store page objects
            if 'page_data' in output_data:
                page_key = f"page_{len(self.tool_chain)}"
                self.page_objects[page_key] = output_data['page_data']
        
        self.updated_at = datetime.utcnow()
    
    def get_shared_variable(self, key: str, default: Any = None) -> Any:
        """Get shared variable value."""
        return self.shared_variables.get(key, default)
    
    def set_shared_variable(self, key: str, value: Any):
        """Set shared variable value."""
        self.shared_variables[key] = value
        self.updated_at = datetime.utcnow()
    
    def get_element_locator(self, element_name: str) -> Optional[str]:
        """Get element locator by name."""
        return self.element_registry.get(element_name)
    
    def register_element(self, element_name: str, locator: str):
        """Register element locator for cross-tool use."""
        self.element_registry[element_name] = locator
        self.updated_at = datetime.utcnow()


@dataclass
class PersistentState:
    """Persistent state management for session restoration."""
    session_id: str
    state_data: Dict[str, Any] = field(default_factory=dict)
    browser_states: Dict[str, BrowserState] = field(default_factory=dict)
    cross_tool_contexts: Dict[str, CrossToolContext] = field(default_factory=dict)
    checkpoint_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_checkpoint(self, checkpoint_name: str, data: Dict[str, Any]):
        """Add state checkpoint for recovery."""
        self.checkpoint_data[checkpoint_name] = {
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        self.updated_at = datetime.utcnow()
    
    def restore_checkpoint(self, checkpoint_name: str) -> Optional[Dict[str, Any]]:
        """Restore state from checkpoint."""
        checkpoint = self.checkpoint_data.get(checkpoint_name)
        return checkpoint['data'] if checkpoint else None


class StateManager:
    """
    Enhanced state management with browser state tracking and cross-tool context.
    
    Provides comprehensive state persistence, restoration, and cross-tool context sharing.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.persistent_states: Dict[str, PersistentState] = {}
        self.browser_states: Dict[str, BrowserState] = {}
        self.cross_tool_contexts: Dict[str, CrossToolContext] = {}
        self.state_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # Initialize state persistence directory
        self.state_dir = Path(self.settings.data_directory) / "state_persistence"
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_persistent_state(self, session_id: str) -> PersistentState:
        """Create persistent state for session."""
        async with self.state_locks[session_id]:
            persistent_state = PersistentState(session_id=session_id)
            self.persistent_states[session_id] = persistent_state
            await self._save_persistent_state(persistent_state)
            return persistent_state
    
    async def get_persistent_state(self, session_id: str) -> Optional[PersistentState]:
        """Get persistent state for session."""
        async with self.state_locks[session_id]:
            if session_id in self.persistent_states:
                return self.persistent_states[session_id]
            
            # Try to load from disk
            persistent_state = await self._load_persistent_state(session_id)
            if persistent_state:
                self.persistent_states[session_id] = persistent_state
            
            return persistent_state
    
    async def update_browser_state(
        self, 
        session_id: str, 
        browser_id: str, 
        state_updates: Dict[str, Any]
    ):
        """Update browser state with new data."""
        async with self.state_locks[session_id]:
            # Get or create browser state
            state_key = f"{session_id}_{browser_id}"
            if state_key not in self.browser_states:
                self.browser_states[state_key] = BrowserState(browser_id=browser_id)
            
            # Update state
            self.browser_states[state_key].update_state(**state_updates)
            
            # Update persistent state
            persistent_state = await self.get_persistent_state(session_id)
            if persistent_state:
                persistent_state.browser_states[browser_id] = self.browser_states[state_key]
                persistent_state.updated_at = datetime.utcnow()
                await self._save_persistent_state(persistent_state)
    
    async def get_browser_state(self, session_id: str, browser_id: str) -> Optional[BrowserState]:
        """Get browser state for session and browser."""
        async with self.state_locks[session_id]:
            state_key = f"{session_id}_{browser_id}"
            if state_key in self.browser_states:
                return self.browser_states[state_key]
            
            # Try to get from persistent state
            persistent_state = await self.get_persistent_state(session_id)
            if persistent_state and browser_id in persistent_state.browser_states:
                browser_state = persistent_state.browser_states[browser_id]
                self.browser_states[state_key] = browser_state
                return browser_state
            
            return None
    
    async def create_cross_tool_context(self, session_id: str) -> CrossToolContext:
        """Create cross-tool context for session."""
        context_id = str(uuid.uuid4())
        context = CrossToolContext(
            context_id=context_id,
            session_id=session_id
        )
        
        async with self.state_locks[session_id]:
            self.cross_tool_contexts[context_id] = context
            
            # Update persistent state
            persistent_state = await self.get_persistent_state(session_id)
            if persistent_state:
                persistent_state.cross_tool_contexts[context_id] = context
                await self._save_persistent_state(persistent_state)
        
        return context
    
    async def get_cross_tool_context(self, context_id: str) -> Optional[CrossToolContext]:
        """Get cross-tool context by ID."""
        if context_id in self.cross_tool_contexts:
            return self.cross_tool_contexts[context_id]
        
        # Search in persistent states
        for persistent_state in self.persistent_states.values():
            if context_id in persistent_state.cross_tool_contexts:
                context = persistent_state.cross_tool_contexts[context_id]
                self.cross_tool_contexts[context_id] = context
                return context
        
        return None
    
    async def update_cross_tool_context(
        self, 
        context_id: str, 
        tool_name: str, 
        input_data: Dict[str, Any], 
        output_data: Dict[str, Any]
    ):
        """Update cross-tool context with tool execution data."""
        context = await self.get_cross_tool_context(context_id)
        if context:
            async with self.state_locks[context.session_id]:
                context.add_tool_execution(tool_name, input_data, output_data)
                
                # Update persistent state
                persistent_state = await self.get_persistent_state(context.session_id)
                if persistent_state:
                    persistent_state.cross_tool_contexts[context_id] = context
                    await self._save_persistent_state(persistent_state)
    
    async def create_state_checkpoint(
        self, 
        session_id: str, 
        checkpoint_name: str, 
        checkpoint_data: Dict[str, Any]
    ):
        """Create state checkpoint for recovery."""
        persistent_state = await self.get_persistent_state(session_id)
        if not persistent_state:
            persistent_state = await self.create_persistent_state(session_id)
        
        async with self.state_locks[session_id]:
            persistent_state.add_checkpoint(checkpoint_name, checkpoint_data)
            await self._save_persistent_state(persistent_state)
    
    async def restore_state_checkpoint(
        self, 
        session_id: str, 
        checkpoint_name: str
    ) -> Optional[Dict[str, Any]]:
        """Restore state from checkpoint."""
        persistent_state = await self.get_persistent_state(session_id)
        if persistent_state:
            return persistent_state.restore_checkpoint(checkpoint_name)
        return None
    
    async def cleanup_expired_states(self, max_age_hours: int = 24):
        """Clean up expired states."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        expired_sessions = []
        for session_id, persistent_state in self.persistent_states.items():
            if persistent_state.updated_at < cutoff_time:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            await self._delete_persistent_state(session_id)
    
    async def _save_persistent_state(self, persistent_state: PersistentState):
        """Save persistent state to disk."""
        try:
            state_file = self.state_dir / f"{persistent_state.session_id}.pkl"
            
            # Convert to serializable format
            state_data = {
                'session_id': persistent_state.session_id,
                'state_data': persistent_state.state_data,
                'browser_states': {k: v.to_dict() for k, v in persistent_state.browser_states.items()},
                'cross_tool_contexts': {k: asdict(v) for k, v in persistent_state.cross_tool_contexts.items()},
                'checkpoint_data': persistent_state.checkpoint_data,
                'created_at': persistent_state.created_at.isoformat(),
                'updated_at': persistent_state.updated_at.isoformat()
            }
            
            with open(state_file, 'wb') as f:
                pickle.dump(state_data, f)
                
        except Exception as e:
            # Log error but don't raise to avoid breaking state operations
            pass
    
    async def _load_persistent_state(self, session_id: str) -> Optional[PersistentState]:
        """Load persistent state from disk."""
        try:
            state_file = self.state_dir / f"{session_id}.pkl"
            if not state_file.exists():
                return None
            
            with open(state_file, 'rb') as f:
                state_data = pickle.load(f)
            
            # Reconstruct objects
            browser_states = {k: BrowserState.from_dict(v) for k, v in state_data['browser_states'].items()}
            cross_tool_contexts = {k: CrossToolContext(**v) for k, v in state_data['cross_tool_contexts'].items()}
            
            persistent_state = PersistentState(
                session_id=state_data['session_id'],
                state_data=state_data['state_data'],
                browser_states=browser_states,
                cross_tool_contexts=cross_tool_contexts,
                checkpoint_data=state_data['checkpoint_data'],
                created_at=datetime.fromisoformat(state_data['created_at']),
                updated_at=datetime.fromisoformat(state_data['updated_at'])
            )
            
            return persistent_state
            
        except Exception as e:
            return None
    
    async def _delete_persistent_state(self, session_id: str):
        """Delete persistent state from disk and memory."""
        try:
            # Remove from memory
            if session_id in self.persistent_states:
                del self.persistent_states[session_id]
            
            # Remove from disk
            state_file = self.state_dir / f"{session_id}.pkl"
            if state_file.exists():
                state_file.unlink()
                
        except Exception as e:
            # Log error but don't raise
            pass


@dataclass
class WorkflowStep:
    """Individual step in a workflow."""
    step_id: str
    step_type: str  # tool, prompt, resource
    step_name: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def start(self):
        """Mark step as started."""
        self.status = "running"
        self.started_at = datetime.utcnow()
    
    def complete(self, output_data: Dict[str, Any]):
        """Mark step as completed."""
        self.status = "completed"
        self.completed_at = datetime.utcnow()
        self.output_data = output_data
    
    def fail(self, error_message: str):
        """Mark step as failed."""
        self.status = "failed"
        self.completed_at = datetime.utcnow()
        self.error_message = error_message


@dataclass
class Workflow:
    """Workflow definition and execution state."""
    workflow_id: str
    name: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed, cancelled
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    def add_step(self, step: WorkflowStep):
        """Add step to workflow."""
        self.steps.append(step)
    
    def get_current_step(self) -> Optional[WorkflowStep]:
        """Get current step to execute."""
        for step in self.steps:
            if step.status == "pending":
                return step
        return None
    
    def is_complete(self) -> bool:
        """Check if workflow is complete."""
        return all(step.status in ["completed", "failed"] for step in self.steps)
    
    def has_failed_steps(self) -> bool:
        """Check if any steps have failed."""
        return any(step.status == "failed" for step in self.steps)


class SessionManager:
    """
    Session lifecycle and context management.
    
    Manages user sessions, context persistence, and TTL cleanup
    for MCP server operations.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.sessions: Dict[str, SessionContext] = {}
        self.session_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start background cleanup task."""
        if not self.cleanup_task or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
    
    async def create_session(
        self, 
        user_context: UserContext,
        session_metadata: Optional[Dict[str, Any]] = None
    ) -> SessionContext:
        """
        Create new session.
        
        Args:
            user_context: Authenticated user context
            session_metadata: Optional session metadata
            
        Returns:
            SessionContext: New session context
        """
        session_id = str(uuid.uuid4())
        
        session_context = SessionContext(
            session_id=session_id,
            user_context=user_context,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            metadata=session_metadata or {},
            tool_history=[],
            resource_cache={},
            workflow_state={}
        )
        
        async with self.session_locks[session_id]:
            self.sessions[session_id] = session_context
        
        return session_context
    
    async def get_session(self, session_id: str) -> Optional[SessionContext]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[SessionContext]: Session context if found
        """
        async with self.session_locks[session_id]:
            session = self.sessions.get(session_id)
            if session and not session.is_expired(self.settings.session_ttl_hours):
                session.update_activity()
                return session
            elif session:
                # Clean up expired session
                del self.sessions[session_id]
        
        return None
    
    async def update_session(self, session_context: SessionContext):
        """
        Update session context.
        
        Args:
            session_context: Updated session context
        """
        session_id = session_context.session_id
        async with self.session_locks[session_id]:
            if session_id in self.sessions:
                self.sessions[session_id] = session_context
    
    async def delete_session(self, session_id: str):
        """
        Delete session.
        
        Args:
            session_id: Session identifier
        """
        async with self.session_locks[session_id]:
            if session_id in self.sessions:
                del self.sessions[session_id]
    
    async def add_tool_execution(
        self, 
        session_id: str, 
        tool_name: str, 
        request_data: Dict[str, Any], 
        response_data: Dict[str, Any]
    ):
        """
        Add tool execution to session history.
        
        Args:
            session_id: Session identifier
            tool_name: Name of executed tool
            request_data: Tool request data
            response_data: Tool response data
        """
        session = await self.get_session(session_id)
        if session:
            session.add_tool_call(tool_name, request_data, response_data)
            await self.update_session(session)
    
    async def cache_resource(
        self, 
        session_id: str, 
        resource_key: str, 
        resource_data: Any
    ):
        """
        Cache resource data in session.
        
        Args:
            session_id: Session identifier
            resource_key: Resource cache key
            resource_data: Resource data to cache
        """
        session = await self.get_session(session_id)
        if session:
            session.resource_cache[resource_key] = {
                "data": resource_data,
                "cached_at": datetime.utcnow().isoformat()
            }
            await self.update_session(session)
    
    async def get_cached_resource(
        self, 
        session_id: str, 
        resource_key: str,
        max_age_minutes: int = 30
    ) -> Optional[Any]:
        """
        Get cached resource data.
        
        Args:
            session_id: Session identifier
            resource_key: Resource cache key
            max_age_minutes: Maximum cache age in minutes
            
        Returns:
            Optional[Any]: Cached resource data if valid
        """
        session = await self.get_session(session_id)
        if not session or resource_key not in session.resource_cache:
            return None
        
        cached_item = session.resource_cache[resource_key]
        cached_at = datetime.fromisoformat(cached_item["cached_at"])
        
        # Check if cache is still valid
        if datetime.utcnow() - cached_at <= timedelta(minutes=max_age_minutes):
            return cached_item["data"]
        else:
            # Remove expired cache item
            del session.resource_cache[resource_key]
            await self.update_session(session)
            return None
    
    async def get_active_sessions(self) -> List[SessionContext]:
        """Get all active sessions."""
        active_sessions = []
        for session in self.sessions.values():
            if not session.is_expired(self.settings.session_ttl_hours):
                active_sessions.append(session)
        return active_sessions
    
    async def _cleanup_expired_sessions(self):
        """Background task to clean up expired sessions."""
        while True:
            try:
                expired_sessions = []
                
                # Find expired sessions
                for session_id, session in self.sessions.items():
                    if session.is_expired(self.settings.session_ttl_hours):
                        expired_sessions.append(session_id)
                
                # Remove expired sessions
                for session_id in expired_sessions:
                    async with self.session_locks[session_id]:
                        if session_id in self.sessions:
                            del self.sessions[session_id]
                
                # Wait before next cleanup
                await asyncio.sleep(self.settings.session_cleanup_interval_minutes * 60)
                
            except Exception as e:
                # Log error but continue cleanup task
                print(f"Session cleanup error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error


class WorkflowOrchestrator:
    """
    Workflow orchestration and execution engine.
    
    Manages multi-step workflows, chained tool executions,
    and complex automation scenarios.
    """
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.workflows: Dict[str, Workflow] = {}
        self.workflow_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    async def create_workflow(
        self, 
        name: str, 
        description: str,
        session_id: str
    ) -> Workflow:
        """
        Create new workflow.
        
        Args:
            name: Workflow name
            description: Workflow description
            session_id: Associated session ID
            
        Returns:
            Workflow: New workflow instance
        """
        workflow_id = str(uuid.uuid4())
        
        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            description=description,
            context={"session_id": session_id}
        )
        
        async with self.workflow_locks[workflow_id]:
            self.workflows[workflow_id] = workflow
        
        return workflow
    
    async def add_tool_step(
        self, 
        workflow_id: str, 
        tool_name: str, 
        input_data: Dict[str, Any]
    ) -> WorkflowStep:
        """
        Add tool execution step to workflow.
        
        Args:
            workflow_id: Workflow identifier
            tool_name: Name of tool to execute
            input_data: Tool input data
            
        Returns:
            WorkflowStep: Created workflow step
        """
        step_id = str(uuid.uuid4())
        step = WorkflowStep(
            step_id=step_id,
            step_type="tool",
            step_name=tool_name,
            input_data=input_data
        )
        
        async with self.workflow_locks[workflow_id]:
            if workflow_id not in self.workflows:
                raise ContextError(f"Workflow {workflow_id} not found")
            
            self.workflows[workflow_id].add_step(step)
        
        return step
    
    async def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Execute workflow steps sequentially.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Dict[str, Any]: Workflow execution results
        """
        async with self.workflow_locks[workflow_id]:
            workflow = self.workflows.get(workflow_id)
            if not workflow:
                raise ContextError(f"Workflow {workflow_id} not found")
            
            workflow.status = "running"
            workflow.started_at = datetime.utcnow()
        
        results = {
            "workflow_id": workflow_id,
            "status": "running",
            "steps": []
        }
        
        try:
            # Execute steps sequentially
            while True:
                current_step = workflow.get_current_step()
                if not current_step:
                    break
                
                # Execute step based on type
                step_result = await self._execute_step(workflow, current_step)
                results["steps"].append(step_result)
                
                # Check if step failed and workflow should stop
                if current_step.status == "failed":
                    workflow.status = "failed"
                    break
            
            # Update final workflow status
            if workflow.is_complete() and not workflow.has_failed_steps():
                workflow.status = "completed"
            elif workflow.has_failed_steps():
                workflow.status = "failed"
            
            workflow.completed_at = datetime.utcnow()
            results["status"] = workflow.status
            
        except Exception as e:
            workflow.status = "failed"
            workflow.completed_at = datetime.utcnow()
            results["status"] = "failed"
            results["error"] = str(e)
        
        return results
    
    async def _execute_step(self, workflow: Workflow, step: WorkflowStep) -> Dict[str, Any]:
        """
        Execute individual workflow step.
        
        Args:
            workflow: Workflow context
            step: Step to execute
            
        Returns:
            Dict[str, Any]: Step execution result
        """
        step.start()
        
        try:
            if step.step_type == "tool":
                # TODO: Integrate with tool execution system
                # This would call the appropriate MCP tool
                output_data = {"message": f"Tool {step.step_name} executed successfully"}
                step.complete(output_data)
            
            elif step.step_type == "prompt":
                # TODO: Integrate with prompt system
                output_data = {"message": f"Prompt {step.step_name} executed successfully"}
                step.complete(output_data)
            
            elif step.step_type == "resource":
                # TODO: Integrate with resource system
                output_data = {"message": f"Resource {step.step_name} accessed successfully"}
                step.complete(output_data)
            
            else:
                step.fail(f"Unknown step type: {step.step_type}")
        
        except Exception as e:
            step.fail(str(e))
        
        return {
            "step_id": step.step_id,
            "step_name": step.step_name,
            "status": step.status,
            "output_data": step.output_data,
            "error_message": step.error_message
        }
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get workflow execution status.
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Dict[str, Any]: Workflow status information
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ContextError(f"Workflow {workflow_id} not found")
        
        return {
            "workflow_id": workflow_id,
            "name": workflow.name,
            "status": workflow.status,
            "created_at": workflow.created_at.isoformat(),
            "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
            "steps": [
                {
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "status": step.status,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "error_message": step.error_message
                }
                for step in workflow.steps
            ]
        }


class ContextManager:
    """
    Enhanced context manager with comprehensive state management integration.
    
    Provides unified access to session management, workflow orchestration,
    and advanced state persistence capabilities.
    """
    
    def __init__(self):
        self.session_manager = SessionManager()
        self.workflow_orchestrator = WorkflowOrchestrator(self.session_manager)
        self.state_manager = StateManager()  # Enhanced state management
    
    # Session Management Methods
    async def create_context(
        self, 
        user_context: UserContext,
        session_metadata: Optional[Dict[str, Any]] = None
    ) -> SessionContext:
        """Create new session context with enhanced state management."""
        session_context = await self.session_manager.create_session(user_context, session_metadata)
        
        # Initialize persistent state
        await self.state_manager.create_persistent_state(session_context.session_id)
        
        return session_context

    async def get_context(self, session_id: str) -> Optional[SessionContext]:
        """Get session context with state restoration."""
        return await self.session_manager.get_session(session_id)

    async def update_context(self, session_context: SessionContext):
        """Update session context with state persistence."""
        await self.session_manager.update_session(session_context)

    async def delete_context(self, session_id: str):
        """Delete session context and clean up persistent state."""
        await self.session_manager.delete_session(session_id)
        await self.state_manager._delete_persistent_state(session_id)
    
    # Enhanced State Management Methods
    async def update_browser_state(
        self, 
        session_id: str, 
        browser_id: str, 
        state_updates: Dict[str, Any]
    ):
        """Update browser state with comprehensive tracking."""
        return await self.state_manager.update_browser_state(session_id, browser_id, state_updates)
    
    async def get_browser_state(self, session_id: str, browser_id: str) -> Optional[BrowserState]:
        """Get browser state for session restoration."""
        return await self.state_manager.get_browser_state(session_id, browser_id)
    
    async def create_cross_tool_context(self, session_id: str) -> CrossToolContext:
        """Create cross-tool context for tool chain execution."""
        return await self.state_manager.create_cross_tool_context(session_id)
    
    async def get_cross_tool_context(self, context_id: str) -> Optional[CrossToolContext]:
        """Get cross-tool context for shared variables and element registry."""
        return await self.state_manager.get_cross_tool_context(context_id)
    
    async def update_cross_tool_context(
        self, 
        context_id: str, 
        tool_name: str, 
        input_data: Dict[str, Any], 
        output_data: Dict[str, Any]
    ):
        """Update cross-tool context with tool execution results."""
        return await self.state_manager.update_cross_tool_context(
            context_id, tool_name, input_data, output_data
        )
    
    async def create_state_checkpoint(
        self, 
        session_id: str, 
        checkpoint_name: str, 
        checkpoint_data: Dict[str, Any]
    ):
        """Create state checkpoint for error recovery."""
        return await self.state_manager.create_state_checkpoint(
            session_id, checkpoint_name, checkpoint_data
        )
    
    async def restore_state_checkpoint(
        self, 
        session_id: str, 
        checkpoint_name: str
    ) -> Optional[Dict[str, Any]]:
        """Restore state from checkpoint."""
        return await self.state_manager.restore_state_checkpoint(session_id, checkpoint_name)
    
    # Workflow Management Methods (Enhanced)
    async def create_workflow(
        self, 
        name: str, 
        description: str, 
        session_id: str
    ) -> Workflow:
        """Create workflow with state checkpoint creation."""
        workflow = await self.workflow_orchestrator.create_workflow(name, description, session_id)
        
        # Create initial checkpoint
        await self.create_state_checkpoint(
            session_id, 
            f"workflow_start_{workflow.workflow_id}",
            {"workflow_id": workflow.workflow_id, "status": "created"}
        )
        
        return workflow

    async def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Execute workflow with comprehensive state tracking."""
        workflow = self.workflow_orchestrator.workflows.get(workflow_id)
        if workflow:
            # Create execution checkpoint
            await self.create_state_checkpoint(
                workflow.context.get('session_id', ''),
                f"workflow_execution_{workflow_id}",
                {"workflow_id": workflow_id, "status": "executing"}
            )
        
        result = await self.workflow_orchestrator.execute_workflow(workflow_id)
        
        # Create completion checkpoint
        if workflow:
            await self.create_state_checkpoint(
                workflow.context.get('session_id', ''),
                f"workflow_complete_{workflow_id}",
                {"workflow_id": workflow_id, "status": "completed", "result": result}
            )
        
        return result

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow status with state information."""
        return await self.workflow_orchestrator.get_workflow_status(workflow_id)
    
    # Utility Methods
    async def cleanup_expired_data(self):
        """Clean up expired sessions and states."""
        await self.state_manager.cleanup_expired_states()
    
    async def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive session summary including state information."""
        session_context = await self.get_context(session_id)
        if not session_context:
            return {"error": "Session not found"}
        
        persistent_state = await self.state_manager.get_persistent_state(session_id)
        
        summary = {
            "session_id": session_id,
            "user_id": session_context.user_context.user_id,
            "created_at": session_context.created_at.isoformat(),
            "last_activity": session_context.last_activity.isoformat(),
            "tool_history_count": len(session_context.tool_history),
            "resource_cache_count": len(session_context.resource_cache),
            "browser_states": {},
            "cross_tool_contexts": {},
            "checkpoints": []
        }
        
        if persistent_state:
            summary["browser_states"] = {
                k: {"current_url": v.current_url, "updated_at": v.updated_at.isoformat()}
                for k, v in persistent_state.browser_states.items()
            }
            summary["cross_tool_contexts"] = {
                k: {"tool_chain_length": len(v.tool_chain), "updated_at": v.updated_at.isoformat()}
                for k, v in persistent_state.cross_tool_contexts.items()
            }
            summary["checkpoints"] = list(persistent_state.checkpoint_data.keys())
        
        return summary 