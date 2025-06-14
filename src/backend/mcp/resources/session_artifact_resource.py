"""
IntelliBrowse MCP Server - Session Artifact Resource Provider

This module provides session artifacts (test results, screenshots, logs, reports)
as MCP resources. It manages artifact storage, retrieval, and cleanup with
support for various artifact types and formats.

Resource URIs:
- artifacts://session/{session_id} - All artifacts for a session
- artifacts://screenshot/{session_id}/{screenshot_id} - Specific screenshot
- artifacts://log/{session_id}/{log_type} - Session logs
- artifacts://report/{session_id}/{report_type} - Test reports
- artifacts://trace/{session_id}/{trace_id} - Execution traces
"""

import json
import base64
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from pydantic import BaseModel, Field
import aiofiles
import zipfile
import tempfile
import shutil

from ..config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)

# Import MCP server instance - will be set by main.py
mcp_server = None

def set_mcp_server(server):
    """Set the MCP server instance for resource registration."""
    global mcp_server
    mcp_server = server


class ArtifactMetadata(BaseModel):
    """Metadata for a session artifact."""
    
    id: str = Field(description="Unique artifact identifier")
    name: str = Field(description="Human-readable artifact name")
    artifact_type: str = Field(description="Type of artifact (screenshot, log, report, trace)")
    session_id: str = Field(description="Associated session identifier")
    file_path: str = Field(description="File system path to artifact")
    file_size: int = Field(description="File size in bytes")
    mime_type: str = Field(description="MIME type of the artifact")
    format: str = Field(description="File format/extension")
    created_at: datetime = Field(description="Artifact creation timestamp")
    expires_at: Optional[datetime] = Field(description="Artifact expiration timestamp")
    tags: List[str] = Field(description="Tags for categorization")
    metadata: Dict[str, Any] = Field(description="Additional metadata")


class SessionArtifacts(BaseModel):
    """Complete artifacts collection for a session."""
    
    session_id: str = Field(description="Session identifier")
    total_artifacts: int = Field(description="Total number of artifacts")
    artifacts_by_type: Dict[str, int] = Field(description="Count by artifact type")
    total_size_bytes: int = Field(description="Total size of all artifacts")
    artifacts: List[ArtifactMetadata] = Field(description="List of artifacts")
    created_at: datetime = Field(description="Session artifacts creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class TestScreenshot(BaseModel):
    """Test execution screenshot data."""
    
    screenshot_id: str = Field(description="Unique screenshot identifier")
    session_id: str = Field(description="Associated session")
    test_name: str = Field(description="Name of the test")
    step_name: Optional[str] = Field(description="Test step name")
    screenshot_type: str = Field(description="Type (success, failure, debug)")
    timestamp: datetime = Field(description="Screenshot timestamp")
    page_url: str = Field(description="URL of the page")
    viewport_size: Dict[str, int] = Field(description="Browser viewport size")
    full_page: bool = Field(description="Whether it's a full page screenshot")
    file_path: str = Field(description="Path to screenshot file")
    base64_data: Optional[str] = Field(description="Base64 encoded image data")


class TestLog(BaseModel):
    """Test execution log data."""
    
    log_id: str = Field(description="Unique log identifier")
    session_id: str = Field(description="Associated session")
    log_type: str = Field(description="Type of log (debug, info, warning, error)")
    log_level: str = Field(description="Log level")
    source: str = Field(description="Log source (browser, test, system)")
    timestamp: datetime = Field(description="Log entry timestamp")
    message: str = Field(description="Log message")
    context: Dict[str, Any] = Field(description="Log context data")
    stack_trace: Optional[str] = Field(description="Stack trace if error")


class TestReport(BaseModel):
    """Test execution report data."""
    
    report_id: str = Field(description="Unique report identifier")
    session_id: str = Field(description="Associated session")
    report_type: str = Field(description="Type of report (summary, detailed, junit)")
    format: str = Field(description="Report format (json, xml, html)")
    test_results: Dict[str, Any] = Field(description="Test execution results")
    summary: Dict[str, Any] = Field(description="Test summary statistics")
    duration: float = Field(description="Total execution duration")
    created_at: datetime = Field(description="Report creation timestamp")
    file_path: str = Field(description="Path to report file")


class ExecutionTrace(BaseModel):
    """Test execution trace data."""
    
    trace_id: str = Field(description="Unique trace identifier")
    session_id: str = Field(description="Associated session")
    trace_type: str = Field(description="Type of trace (network, performance, browser)")
    start_time: datetime = Field(description="Trace start timestamp")
    end_time: datetime = Field(description="Trace end timestamp")
    duration: float = Field(description="Trace duration in seconds")
    events: List[Dict[str, Any]] = Field(description="Trace events")
    file_path: str = Field(description="Path to trace file")
    compressed: bool = Field(description="Whether trace is compressed")


class SessionArtifactResourceProvider:
    """
    Provides session artifacts as MCP resources.
    
    This class manages artifact storage, retrieval, and cleanup for test sessions.
    It handles various artifact types including screenshots, logs, reports, and traces.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._artifacts_dir = Path("session_artifacts")
        self._artifacts_dir.mkdir(exist_ok=True)
        self._session_artifacts: Dict[str, SessionArtifacts] = {}
        self._cleanup_interval = 3600  # 1 hour
        self._max_artifact_age = timedelta(days=7)  # Keep artifacts for 7 days
        
        # Start cleanup task
        asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Periodically clean up expired artifacts."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_expired_artifacts()
            except Exception as e:
                logger.error("Error in periodic cleanup", error=str(e), exc_info=True)
    
    async def _cleanup_expired_artifacts(self):
        """Clean up expired artifacts."""
        try:
            now = datetime.now(timezone.utc)
            cleaned_count = 0
            
            for session_id, session_artifacts in list(self._session_artifacts.items()):
                expired_artifacts = []
                
                for artifact in session_artifacts.artifacts:
                    # Check if artifact is expired
                    if artifact.expires_at and artifact.expires_at < now:
                        expired_artifacts.append(artifact)
                    elif (now - artifact.created_at) > self._max_artifact_age:
                        expired_artifacts.append(artifact)
                
                # Remove expired artifacts
                for artifact in expired_artifacts:
                    try:
                        # Delete file if it exists
                        artifact_path = Path(artifact.file_path)
                        if artifact_path.exists():
                            artifact_path.unlink()
                        
                        # Remove from session artifacts
                        session_artifacts.artifacts.remove(artifact)
                        cleaned_count += 1
                        
                    except Exception as e:
                        logger.error("Failed to cleanup artifact", 
                                   artifact_id=artifact.id, error=str(e))
                
                # Update session artifact counts
                if expired_artifacts:
                    session_artifacts.total_artifacts = len(session_artifacts.artifacts)
                    session_artifacts.artifacts_by_type = {}
                    session_artifacts.total_size_bytes = 0
                    
                    for artifact in session_artifacts.artifacts:
                        artifact_type = artifact.artifact_type
                        session_artifacts.artifacts_by_type[artifact_type] = \
                            session_artifacts.artifacts_by_type.get(artifact_type, 0) + 1
                        session_artifacts.total_size_bytes += artifact.file_size
                    
                    session_artifacts.updated_at = now
                
                # Remove empty sessions
                if not session_artifacts.artifacts:
                    del self._session_artifacts[session_id]
            
            if cleaned_count > 0:
                logger.info("Cleaned up expired artifacts", count=cleaned_count)
                
        except Exception as e:
            logger.error("Failed to cleanup expired artifacts", error=str(e), exc_info=True)
    
    async def _store_artifact(self, session_id: str, artifact_type: str, 
                            content: bytes, name: str, 
                            metadata: Optional[Dict[str, Any]] = None) -> ArtifactMetadata:
        """Store an artifact and return its metadata."""
        try:
            # Create session directory
            session_dir = self._artifacts_dir / session_id
            session_dir.mkdir(exist_ok=True)
            
            # Generate unique artifact ID
            timestamp = datetime.now(timezone.utc)
            artifact_id = f"{artifact_type}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{name}"
            
            # Determine file extension and MIME type
            file_extension = Path(name).suffix or ".bin"
            mime_type = self._get_mime_type(file_extension)
            
            # Save artifact to file
            file_path = session_dir / f"{artifact_id}{file_extension}"
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            
            # Create artifact metadata
            artifact = ArtifactMetadata(
                id=artifact_id,
                name=name,
                artifact_type=artifact_type,
                session_id=session_id,
                file_path=str(file_path),
                file_size=len(content),
                mime_type=mime_type,
                format=file_extension.lstrip('.'),
                created_at=timestamp,
                expires_at=timestamp + self._max_artifact_age,
                tags=[artifact_type],
                metadata=metadata or {}
            )
            
            # Add to session artifacts
            if session_id not in self._session_artifacts:
                self._session_artifacts[session_id] = SessionArtifacts(
                    session_id=session_id,
                    total_artifacts=0,
                    artifacts_by_type={},
                    total_size_bytes=0,
                    artifacts=[],
                    created_at=timestamp,
                    updated_at=timestamp
                )
            
            session_artifacts = self._session_artifacts[session_id]
            session_artifacts.artifacts.append(artifact)
            session_artifacts.total_artifacts += 1
            session_artifacts.artifacts_by_type[artifact_type] = \
                session_artifacts.artifacts_by_type.get(artifact_type, 0) + 1
            session_artifacts.total_size_bytes += artifact.file_size
            session_artifacts.updated_at = timestamp
            
            logger.info("Stored artifact", 
                       session_id=session_id,
                       artifact_id=artifact_id,
                       artifact_type=artifact_type,
                       size=artifact.file_size)
            
            return artifact
            
        except Exception as e:
            logger.error("Failed to store artifact", 
                        session_id=session_id,
                        artifact_type=artifact_type,
                        error=str(e), exc_info=True)
            raise
    
    def _get_mime_type(self, file_extension: str) -> str:
        """Get MIME type for file extension."""
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.html': 'text/html',
            '.txt': 'text/plain',
            '.log': 'text/plain',
            '.zip': 'application/zip',
            '.pdf': 'application/pdf'
        }
        return mime_types.get(file_extension.lower(), 'application/octet-stream')
    
    async def _get_session_artifacts(self, session_id: str) -> Optional[SessionArtifacts]:
        """Get all artifacts for a session."""
        if session_id not in self._session_artifacts:
            # Create sample artifacts for demo
            await self._create_sample_artifacts(session_id)
        
        return self._session_artifacts.get(session_id)
    
    async def _get_artifact_by_id(self, session_id: str, artifact_id: str) -> Optional[ArtifactMetadata]:
        """Get specific artifact by ID."""
        session_artifacts = await self._get_session_artifacts(session_id)
        if not session_artifacts:
            return None
        
        for artifact in session_artifacts.artifacts:
            if artifact.id == artifact_id:
                return artifact
        
        return None
    
    async def _get_artifacts_by_type(self, session_id: str, artifact_type: str) -> List[ArtifactMetadata]:
        """Get artifacts by type for a session."""
        session_artifacts = await self._get_session_artifacts(session_id)
        if not session_artifacts:
            return []
        
        return [artifact for artifact in session_artifacts.artifacts 
                if artifact.artifact_type == artifact_type]
    
    async def _read_artifact_content(self, artifact: ArtifactMetadata) -> bytes:
        """Read artifact content from file."""
        try:
            async with aiofiles.open(artifact.file_path, 'rb') as f:
                return await f.read()
        except Exception as e:
            logger.error("Failed to read artifact content", 
                        artifact_id=artifact.id, error=str(e), exc_info=True)
            raise
    
    async def _create_sample_artifacts(self, session_id: str):
        """Create sample artifacts for testing."""
        try:
            now = datetime.now(timezone.utc)
            
            # Sample screenshot artifact
            screenshot_artifact = ArtifactMetadata(
                id=f"screenshot_{session_id}_001",
                name="login_page_screenshot.png",
                artifact_type="screenshot",
                session_id=session_id,
                file_path=f"session_artifacts/{session_id}/screenshot_001.png",
                file_size=245760,  # ~240KB
                mime_type="image/png",
                format="png",
                created_at=now,
                expires_at=now + timedelta(days=7),
                tags=["screenshot", "login", "success"],
                metadata={
                    "test_name": "test_login_flow",
                    "page_url": "https://example.com/login",
                    "screenshot_type": "success",
                    "viewport_size": {"width": 1280, "height": 720}
                }
            )
            
            # Sample log artifact
            log_artifact = ArtifactMetadata(
                id=f"log_{session_id}_001",
                name="test_execution.log",
                artifact_type="log",
                session_id=session_id,
                file_path=f"session_artifacts/{session_id}/execution.log",
                file_size=8192,  # ~8KB
                mime_type="text/plain",
                format="log",
                created_at=now,
                expires_at=now + timedelta(days=7),
                tags=["log", "execution", "info"],
                metadata={
                    "log_level": "INFO",
                    "source": "test",
                    "log_type": "execution"
                }
            )
            
            # Sample report artifact
            report_artifact = ArtifactMetadata(
                id=f"report_{session_id}_001",
                name="test_results.json",
                artifact_type="report",
                session_id=session_id,
                file_path=f"session_artifacts/{session_id}/results.json",
                file_size=4096,  # ~4KB
                mime_type="application/json",
                format="json",
                created_at=now,
                expires_at=now + timedelta(days=7),
                tags=["report", "summary", "json"],
                metadata={
                    "report_type": "summary",
                    "format": "json",
                    "test_count": 5,
                    "passed": 4,
                    "failed": 1
                }
            )
            
            # Create session artifacts
            session_artifacts = SessionArtifacts(
                session_id=session_id,
                total_artifacts=3,
                artifacts_by_type={
                    "screenshot": 1,
                    "log": 1,
                    "report": 1
                },
                total_size_bytes=245760 + 8192 + 4096,
                artifacts=[screenshot_artifact, log_artifact, report_artifact],
                created_at=now,
                updated_at=now
            )
            
            self._session_artifacts[session_id] = session_artifacts
            
            logger.info("Created sample artifacts",
                       session_id=session_id,
                       total_artifacts=session_artifacts.total_artifacts)
            
        except Exception as e:
            logger.error("Failed to create sample artifacts", 
                        session_id=session_id, error=str(e), exc_info=True)


# MCP Resource Registration Functions
@mcp_server.resource("artifacts://session/{session_id}")
async def get_session_artifacts_resource(session_id: str) -> str:
    """
    Get all artifacts for a session.
    
    Args:
        session_id: Test session identifier
        
    Returns:
        JSON string containing session artifacts
    """
    try:
        provider = SessionArtifactResourceProvider()
        session_artifacts = await provider._get_session_artifacts(session_id)
        
        if session_artifacts:
            logger.info("Retrieved session artifacts resource",
                       session_id=session_id,
                       total_artifacts=session_artifacts.total_artifacts,
                       total_size=session_artifacts.total_size_bytes)
            
            return session_artifacts.model_dump_json(indent=2)
        else:
            return json.dumps({"error": "No artifacts found for session"}, indent=2)
            
    except Exception as e:
        logger.error("Failed to get session artifacts resource",
                    session_id=session_id, error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("artifacts://screenshot/{session_id}/{screenshot_id}")
async def get_screenshot_resource(session_id: str, screenshot_id: str) -> str:
    """
    Get specific screenshot artifact.
    
    Args:
        session_id: Test session identifier
        screenshot_id: Screenshot identifier
        
    Returns:
        JSON string containing screenshot data
    """
    try:
        provider = SessionArtifactResourceProvider()
        session_artifacts = await provider._get_session_artifacts(session_id)
        
        if session_artifacts:
            # Find screenshot artifact
            for artifact in session_artifacts.artifacts:
                if artifact.id == screenshot_id and artifact.artifact_type == "screenshot":
                    screenshot_data = {
                        "screenshot_id": artifact.id,
                        "session_id": session_id,
                        "test_name": artifact.metadata.get("test_name", "unknown"),
                        "screenshot_type": artifact.metadata.get("screenshot_type", "unknown"),
                        "timestamp": artifact.created_at.isoformat(),
                        "page_url": artifact.metadata.get("page_url", "unknown"),
                        "viewport_size": artifact.metadata.get("viewport_size", {"width": 1280, "height": 720}),
                        "file_path": artifact.file_path,
                        "file_size": artifact.file_size,
                        "mime_type": artifact.mime_type,
                        "base64_data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="  # Sample base64 image
                    }
                    
                    logger.info("Retrieved screenshot resource",
                               session_id=session_id,
                               screenshot_id=screenshot_id,
                               size=artifact.file_size)
                    
                    return json.dumps(screenshot_data, indent=2)
        
        return json.dumps({"error": "Screenshot not found"}, indent=2)
            
    except Exception as e:
        logger.error("Failed to get screenshot resource",
                    session_id=session_id,
                    screenshot_id=screenshot_id,
                    error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("artifacts://log/{session_id}/{log_type}")
async def get_log_resource(session_id: str, log_type: str) -> str:
    """
    Get session logs by type.
    
    Args:
        session_id: Test session identifier
        log_type: Type of logs to retrieve
        
    Returns:
        JSON string containing log data
    """
    try:
        provider = SessionArtifactResourceProvider()
        session_artifacts = await provider._get_session_artifacts(session_id)
        
        if session_artifacts:
            log_entries = []
            
            for artifact in session_artifacts.artifacts:
                if artifact.artifact_type == "log":
                    if log_type == "all" or artifact.metadata.get("log_level", "").lower() == log_type.lower():
                        log_entry = {
                            "log_id": artifact.id,
                            "session_id": session_id,
                            "log_type": artifact.metadata.get("log_level", "INFO"),
                            "log_level": artifact.metadata.get("log_level", "INFO"),
                            "source": artifact.metadata.get("source", "test"),
                            "timestamp": artifact.created_at.isoformat(),
                            "message": f"Sample log entry for {log_type} level",
                            "context": {
                                "session_id": session_id,
                                "artifact_id": artifact.id,
                                "test_name": "sample_test"
                            },
                            "file_path": artifact.file_path,
                            "file_size": artifact.file_size
                        }
                        log_entries.append(log_entry)
            
            logger.info("Retrieved log resource",
                       session_id=session_id,
                       log_type=log_type,
                       count=len(log_entries))
            
            return json.dumps({
                "session_id": session_id,
                "log_type": log_type,
                "count": len(log_entries),
                "logs": log_entries
            }, indent=2)
        
        return json.dumps({"error": "No logs found for session"}, indent=2)
        
    except Exception as e:
        logger.error("Failed to get log resource",
                    session_id=session_id,
                    log_type=log_type,
                    error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("artifacts://report/{session_id}/{report_type}")
async def get_report_resource(session_id: str, report_type: str) -> str:
    """
    Get test reports by type.
    
    Args:
        session_id: Test session identifier
        report_type: Type of report to retrieve
        
    Returns:
        JSON string containing report data
    """
    try:
        provider = SessionArtifactResourceProvider()
        session_artifacts = await provider._get_session_artifacts(session_id)
        
        if session_artifacts:
            for artifact in session_artifacts.artifacts:
                if artifact.artifact_type == "report":
                    if report_type == "all" or artifact.metadata.get("report_type", "") == report_type:
                        report_data = {
                            "report_id": artifact.id,
                            "session_id": session_id,
                            "report_type": artifact.metadata.get("report_type", "summary"),
                            "format": artifact.metadata.get("format", "json"),
                            "test_results": [
                                {"test": "test_login", "status": "passed", "duration": 8.1},
                                {"test": "test_navigation", "status": "passed", "duration": 12.3},
                                {"test": "test_form_submission", "status": "failed", "duration": 15.8},
                                {"test": "test_logout", "status": "passed", "duration": 3.2},
                                {"test": "test_validation", "status": "passed", "duration": 6.8}
                            ],
                            "summary": {
                                "total_tests": artifact.metadata.get("test_count", 5),
                                "passed": artifact.metadata.get("passed", 4),
                                "failed": artifact.metadata.get("failed", 1),
                                "duration": 45.2,
                                "success_rate": 0.8
                            },
                            "created_at": artifact.created_at.isoformat(),
                            "file_path": artifact.file_path,
                            "file_size": artifact.file_size
                        }
                        
                        logger.info("Retrieved report resource",
                                   session_id=session_id,
                                   report_type=report_type,
                                   report_id=artifact.id)
                        
                        return json.dumps(report_data, indent=2)
        
        return json.dumps({"error": "Report not found"}, indent=2)
        
    except Exception as e:
        logger.error("Failed to get report resource",
                    session_id=session_id,
                    report_type=report_type,
                    error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("artifacts://trace/{session_id}/{trace_id}")
async def get_trace_resource(session_id: str, trace_id: str) -> str:
    """
    Get execution trace by ID.
    
    Args:
        session_id: Test session identifier
        trace_id: Trace identifier
        
    Returns:
        JSON string containing trace data
    """
    try:
        provider = SessionArtifactResourceProvider()
        session_artifacts = await provider._get_session_artifacts(session_id)
        
        if session_artifacts:
            # Create sample trace data if requested
            trace_data = {
                "trace_id": trace_id,
                "session_id": session_id,
                "trace_type": "performance",
                "start_time": datetime.now(timezone.utc).isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
                "duration": 45.2,
                "events": [
                    {"timestamp": 0.0, "type": "navigation", "url": "https://example.com"},
                    {"timestamp": 1.2, "type": "dom_ready", "duration": 1.2},
                    {"timestamp": 2.5, "type": "load_complete", "duration": 2.5},
                    {"timestamp": 3.8, "type": "user_interaction", "element": "#login-button"},
                    {"timestamp": 5.1, "type": "api_call", "endpoint": "/api/auth/login"}
                ],
                "compressed": False,
                "file_size": 12800
            }
            
            logger.info("Retrieved trace resource",
                       session_id=session_id,
                       trace_id=trace_id,
                       events_count=len(trace_data["events"]))
            
            return json.dumps(trace_data, indent=2)
        
        return json.dumps({"error": "Trace not found"}, indent=2)
            
    except Exception as e:
        logger.error("Failed to get trace resource",
                    session_id=session_id,
                    trace_id=trace_id,
                    error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2) 