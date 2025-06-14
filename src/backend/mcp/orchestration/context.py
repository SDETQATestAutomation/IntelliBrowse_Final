"""
Session context management and workflow orchestration for IntelliBrowse MCP Server.

This module provides session lifecycle management, context persistence,
and workflow orchestration capabilities for MCP operations.
"""

import asyncio
import json
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict
import uuid

from ..config.settings import get_settings
from ..schemas.context_schemas import SessionContext, TaskContext, UserContext
from ..core.exceptions import SessionError, ContextError


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
    Unified context management for MCP operations.
    
    Provides centralized access to session management, workflow orchestration,
    and context propagation throughout the MCP server.
    """
    
    def __init__(self):
        self.session_manager = SessionManager()
        self.workflow_orchestrator = WorkflowOrchestrator(self.session_manager)
    
    async def create_context(
        self, 
        user_context: UserContext,
        session_metadata: Optional[Dict[str, Any]] = None
    ) -> SessionContext:
        """Create new session context."""
        return await self.session_manager.create_session(user_context, session_metadata)
    
    async def get_context(self, session_id: str) -> Optional[SessionContext]:
        """Get session context by ID."""
        return await self.session_manager.get_session(session_id)
    
    async def update_context(self, session_context: SessionContext):
        """Update session context."""
        await self.session_manager.update_session(session_context)
    
    async def delete_context(self, session_id: str):
        """Delete session context."""
        await self.session_manager.delete_session(session_id)
    
    async def create_workflow(
        self, 
        name: str, 
        description: str, 
        session_id: str
    ) -> Workflow:
        """Create new workflow."""
        return await self.workflow_orchestrator.create_workflow(name, description, session_id)
    
    async def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Execute workflow."""
        return await self.workflow_orchestrator.execute_workflow(workflow_id)
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow status."""
        return await self.workflow_orchestrator.get_workflow_status(workflow_id) 