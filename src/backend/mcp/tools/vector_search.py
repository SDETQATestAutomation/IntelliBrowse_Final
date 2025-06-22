"""
Vector Search Tool for IntelliBrowse MCP Server

This tool provides comprehensive vector search capabilities for DOM elements
and Gherkin steps through the MCP protocol. It integrates with the enterprise
vector store service to offer semantic search with audit logging and security.

Features:
- Semantic search for DOM elements and Gherkin steps
- Advanced filtering and similarity matching
- Batch operations with performance optimization
- Comprehensive audit logging for compliance
- Enterprise-grade error handling and validation
- Context-aware search with session memory
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from mcp import types
# Import the shared server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

from pydantic import BaseModel, Field, field_validator

try:
    from core.exceptions import VectorStoreError, MCPValidationError, MCPOperationError
except ImportError:
    # Fallback for when running directly from mcp directory
    from core.exceptions import VectorStoreError, MCPValidationError, MCPOperationError
try:
    from schemas.vector_store_schemas import (
        VectorSearchRequest,
        VectorSearchResponse,
        VectorSearchResult,
        AddElementsRequest,
        AddElementsResponse,
        AddGherkinStepsRequest,
        AddGherkinStepsResponse,
        QueryElementsRequest,
        QueryElementsResponse,
        QueryGherkinStepsRequest,
        QueryGherkinStepsResponse,
        ClearPageElementsRequest,
        ClearPageElementsResponse,
        HealthCheckRequest,
        HealthCheckResponse,
        ElementAnalysisData
    )
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.vector_store_schemas import (
        VectorSearchRequest,
        VectorSearchResponse,
        VectorSearchResult,
        AddElementsRequest,
        AddElementsResponse,
        AddGherkinStepsRequest,
        AddGherkinStepsResponse,
        QueryElementsRequest,
        QueryElementsResponse,
        QueryGherkinStepsRequest,
        QueryGherkinStepsResponse,
        ClearPageElementsRequest,
        ClearPageElementsResponse,
        HealthCheckRequest,
        HealthCheckResponse,
        ElementAnalysisData
    )
try:
    from services.vector_store_service import VectorStoreService
except ImportError:
    # Fallback for when running directly from mcp directory
    from services.vector_store_service import VectorStoreService


# Initialize MCP server instance
# Use the shared mcp_server instance (imported above)


class VectorSearchToolContext(BaseModel):
    """Context information for vector search operations."""
    session_id: Optional[str] = Field(None, description="Session identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    page_url: Optional[str] = Field(None, description="Current page URL")
    search_intent: Optional[str] = Field(None, description="Search intent or purpose")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Operation timestamp")
    
    class Config:
        extra = "allow"


@mcp_server.tool()
async def search_dom_elements(
    query_description: str,
    page_url: Optional[str] = None,
    n_results: int = 5,
    similarity_threshold: float = 0.7,
    filters: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Search for DOM elements using semantic vector search.
    
    This tool searches for DOM elements based on natural language descriptions,
    returning the most semantically similar elements with their locators and metadata.
    
    Args:
        query_description: Natural language description of the element to find
        page_url: Optional URL filter to search within specific page
        n_results: Maximum number of results to return (1-50)
        similarity_threshold: Minimum similarity score (0.0-1.0)
        filters: Additional metadata filters (e.g., {"tag": "button", "role": "button"})
        context: Search context information (session, user, intent, etc.)
    
    Returns:
        Dictionary containing search results with elements, metadata, and performance info
    
    Raises:
        MCPValidationError: Invalid search parameters
        VectorStoreError: Vector store operation failed
    """
    start_time = datetime.utcnow()
    
    # Validate inputs
    if not query_description or not query_description.strip():
        raise MCPValidationError("Query description cannot be empty")
    
    if n_results < 1 or n_results > 50:
        raise MCPValidationError("n_results must be between 1 and 50")
    
    if similarity_threshold < 0.0 or similarity_threshold > 1.0:
        raise MCPValidationError("similarity_threshold must be between 0.0 and 1.0")
    
    # Create enriched context
    search_context = VectorSearchToolContext(
        search_intent="dom_element_search",
        page_url=page_url,
        **(context or {})
    )
    
    logger.info(
        "DOM element search initiated",
        extra={
            "tool": "vector_search",
            "action": "search_dom_elements",
            "query": query_description,
            "page_url": page_url,
            "n_results": n_results,
            "similarity_threshold": similarity_threshold,
            "filters": filters,
            "context": search_context.dict(),
            "audit": True
        }
    )
    
    try:
        # Get vector store service
        vector_store = await VectorStoreService.get_instance()
        
        # Execute search
        results = await vector_store.query_elements(
            query_description=query_description.strip(),
            page_url=page_url,
            n_results=n_results,
            filters=filters or {},
            context=search_context.dict()
        )
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Filter results by similarity threshold
        filtered_results = [
            result for result in results
            if result.get('distance') is not None and (1.0 - result['distance']) >= similarity_threshold
        ]
        
        # Enrich results with similarity scores
        enriched_results = []
        for result in filtered_results:
            enriched_result = {
                "element_id": result.get('id'),
                "description": result.get('description', ''),
                "locators": result.get('locators', []),
                "metadata": result.get('metadata', {}),
                "similarity_score": 1.0 - result.get('distance', 1.0) if result.get('distance') is not None else 0.0,
                "distance": result.get('distance')
            }
            enriched_results.append(enriched_result)
        
        # Sort by similarity score (highest first)
        enriched_results.sort(key=lambda x: x.get('similarity_score', 0.0), reverse=True)
        
        response = {
            "success": True,
            "query": query_description,
            "results": enriched_results,
            "total_results": len(enriched_results),
            "execution_time_ms": execution_time,
            "metadata": {
                "page_url": page_url,
                "similarity_threshold": similarity_threshold,
                "filters_applied": bool(filters),
                "context": search_context.dict()
            }
        }
        
        logger.info(
            f"DOM element search completed: found {len(enriched_results)} matches in {execution_time:.2f}ms",
            extra={
                "tool": "vector_search",
                "action": "search_dom_elements_complete",
                "query": query_description,
                "results_count": len(enriched_results),
                "execution_time_ms": execution_time,
                "audit": True
            }
        )
        
        return response
        
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.error(
            f"DOM element search failed: {e}",
            extra={
                "tool": "vector_search",
                "action": "search_dom_elements_error",
                "query": query_description,
                "error": str(e),
                "execution_time_ms": execution_time,
                "audit": True
            },
            exc_info=True
        )
        
        if isinstance(e, (MCPValidationError, VectorStoreError)):
            raise
        
        raise MCPOperationError(f"DOM element search failed: {e}", operation="search_dom_elements")


@mcp_server.tool()
async def search_gherkin_steps(
    query_text: str,
    n_results: int = 3,
    step_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    similarity_threshold: float = 0.8,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Search for Gherkin steps using semantic vector search.
    
    This tool searches for existing Gherkin steps based on natural language queries,
    helping with step reuse and consistency in test scenarios.
    
    Args:
        query_text: Text to search for in Gherkin steps
        n_results: Maximum number of results to return (1-20)
        step_type: Optional step type filter (given, when, then, and, but)
        tags: Optional list of tags to filter by
        similarity_threshold: Minimum similarity score (0.0-1.0)
        context: Search context information
    
    Returns:
        Dictionary containing search results with steps, metadata, and performance info
    
    Raises:
        MCPValidationError: Invalid search parameters
        VectorStoreError: Vector store operation failed
    """
    start_time = datetime.utcnow()
    
    # Validate inputs
    if not query_text or not query_text.strip():
        raise MCPValidationError("Query text cannot be empty")
    
    if n_results < 1 or n_results > 20:
        raise MCPValidationError("n_results must be between 1 and 20")
    
    if similarity_threshold < 0.0 or similarity_threshold > 1.0:
        raise MCPValidationError("similarity_threshold must be between 0.0 and 1.0")
    
    if step_type and step_type.lower() not in ['given', 'when', 'then', 'and', 'but']:
        raise MCPValidationError("step_type must be one of: given, when, then, and, but")
    
    # Create enriched context
    search_context = VectorSearchToolContext(
        search_intent="gherkin_step_search",
        **(context or {})
    )
    
    logger.info(
        "Gherkin step search initiated",
        extra={
            "tool": "vector_search",
            "action": "search_gherkin_steps",
            "query": query_text,
            "n_results": n_results,
            "step_type": step_type,
            "tags": tags,
            "similarity_threshold": similarity_threshold,
            "context": search_context.dict(),
            "audit": True
        }
    )
    
    try:
        # Get vector store service
        vector_store = await VectorStoreService.get_instance()
        
        # Execute search
        results = await vector_store.query_gherkin_steps(
            query_text=query_text.strip(),
            n_results=n_results,
            context=search_context.dict()
        )
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Filter results by similarity threshold and additional criteria
        filtered_results = []
        for result in results:
            similarity_score = 1.0 - result.get('distance', 1.0) if result.get('distance') is not None else 0.0
            
            # Apply similarity threshold
            if similarity_score < similarity_threshold:
                continue
            
            # Apply step type filter
            if step_type:
                step_metadata = result.get('metadata', {})
                result_step_type = step_metadata.get('step_type', '').lower()
                if result_step_type != step_type.lower():
                    continue
            
            # Apply tags filter (if step has any of the specified tags)
            if tags:
                step_metadata = result.get('metadata', {})
                step_tags = step_metadata.get('tags', [])
                if not any(tag in step_tags for tag in tags):
                    continue
            
            enriched_result = {
                "step_id": result.get('id'),
                "step_text": result.get('step_text', ''),
                "metadata": result.get('metadata', {}),
                "similarity_score": similarity_score,
                "distance": result.get('distance')
            }
            filtered_results.append(enriched_result)
        
        # Sort by similarity score (highest first)
        filtered_results.sort(key=lambda x: x.get('similarity_score', 0.0), reverse=True)
        
        response = {
            "success": True,
            "query": query_text,
            "results": filtered_results,
            "total_results": len(filtered_results),
            "execution_time_ms": execution_time,
            "metadata": {
                "step_type_filter": step_type,
                "tags_filter": tags,
                "similarity_threshold": similarity_threshold,
                "context": search_context.dict()
            }
        }
        
        logger.info(
            f"Gherkin step search completed: found {len(filtered_results)} matches in {execution_time:.2f}ms",
            extra={
                "tool": "vector_search",
                "action": "search_gherkin_steps_complete",
                "query": query_text,
                "results_count": len(filtered_results),
                "execution_time_ms": execution_time,
                "audit": True
            }
        )
        
        return response
        
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.error(
            f"Gherkin step search failed: {e}",
            extra={
                "tool": "vector_search",
                "action": "search_gherkin_steps_error",
                "query": query_text,
                "error": str(e),
                "execution_time_ms": execution_time,
                "audit": True
            },
            exc_info=True
        )
        
        if isinstance(e, (MCPValidationError, VectorStoreError)):
            raise
        
        raise MCPOperationError(f"Gherkin step search failed: {e}", operation="search_gherkin_steps")


@mcp_server.tool()
async def add_dom_elements(
    page_url: str,
    elements: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Add DOM elements to the vector store for future search.
    
    This tool stores DOM element analyses in the vector store, making them
    searchable via semantic queries. Elements are deduplicated by stable IDs.
    
    Args:
        page_url: URL of the page containing the elements
        elements: List of element analysis data (from locator generator)
        context: Operation context information
    
    Returns:
        Dictionary containing operation results and performance info
    
    Raises:
        MCPValidationError: Invalid input parameters
        VectorStoreError: Vector store operation failed
    """
    start_time = datetime.utcnow()
    
    # Validate inputs
    if not page_url or not page_url.strip():
        raise MCPValidationError("Page URL cannot be empty")
    
    if not elements:
        raise MCPValidationError("Elements list cannot be empty")
    
    # Create enriched context
    operation_context = VectorSearchToolContext(
        search_intent="dom_element_storage",
        page_url=page_url,
        **(context or {})
    )
    
    logger.info(
        f"Adding {len(elements)} DOM elements to vector store",
        extra={
            "tool": "vector_search",
            "action": "add_dom_elements",
            "page_url": page_url,
            "element_count": len(elements),
            "context": operation_context.dict(),
            "audit": True
        }
    )
    
    try:
        # Parse elements into ElementAnalysisData objects
        parsed_elements = []
        for i, element_data in enumerate(elements):
            try:
                # Handle both dictionary and ElementAnalysisData objects
                if isinstance(element_data, dict):
                    element_analysis = ElementAnalysisData(**element_data)
                else:
                    element_analysis = element_data
                parsed_elements.append(element_analysis)
            except Exception as parse_error:
                logger.warning(
                    f"Failed to parse element {i}: {parse_error}",
                    extra={
                        "tool": "vector_search",
                        "action": "add_dom_elements_parse_error",
                        "element_index": i,
                        "error": str(parse_error)
                    }
                )
                continue
        
        if not parsed_elements:
            raise MCPValidationError("No valid elements to add after parsing")
        
        # Get vector store service
        vector_store = await VectorStoreService.get_instance()
        
        # Add elements to vector store
        await vector_store.add_or_update_elements(
            page_url=page_url.strip(),
            element_analyses=parsed_elements,
            context=operation_context.dict()
        )
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        response = {
            "success": True,
            "elements_added": len(parsed_elements),
            "execution_time_ms": execution_time,
            "message": f"Successfully added {len(parsed_elements)} elements to vector store",
            "metadata": {
                "page_url": page_url,
                "original_count": len(elements),
                "parsed_count": len(parsed_elements),
                "context": operation_context.dict()
            }
        }
        
        logger.info(
            f"Successfully added {len(parsed_elements)} DOM elements in {execution_time:.2f}ms",
            extra={
                "tool": "vector_search",
                "action": "add_dom_elements_complete",
                "page_url": page_url,
                "elements_added": len(parsed_elements),
                "execution_time_ms": execution_time,
                "audit": True
            }
        )
        
        return response
        
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.error(
            f"Failed to add DOM elements: {e}",
            extra={
                "tool": "vector_search",
                "action": "add_dom_elements_error",
                "page_url": page_url,
                "error": str(e),
                "execution_time_ms": execution_time,
                "audit": True
            },
            exc_info=True
        )
        
        if isinstance(e, (MCPValidationError, VectorStoreError)):
            raise
        
        raise MCPOperationError(f"Failed to add DOM elements: {e}", operation="add_dom_elements")


@mcp_server.tool()
async def add_gherkin_steps(
    steps: List[str],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Add Gherkin steps to the vector store for future search and reuse.
    
    This tool stores Gherkin steps in the vector store, making them searchable
    for step reuse and consistency checking in test scenarios.
    
    Args:
        steps: List of Gherkin step text strings
        context: Operation context information
    
    Returns:
        Dictionary containing operation results and performance info
    
    Raises:
        MCPValidationError: Invalid input parameters
        VectorStoreError: Vector store operation failed
    """
    start_time = datetime.utcnow()
    
    # Validate inputs
    if not steps:
        raise MCPValidationError("Steps list cannot be empty")
    
    # Clean and validate steps
    cleaned_steps = []
    for step in steps:
        if isinstance(step, str) and step.strip():
            cleaned_steps.append(step.strip())
    
    if not cleaned_steps:
        raise MCPValidationError("No valid steps found after cleaning")
    
    # Create enriched context
    operation_context = VectorSearchToolContext(
        search_intent="gherkin_step_storage",
        **(context or {})
    )
    
    logger.info(
        f"Adding {len(cleaned_steps)} Gherkin steps to vector store",
        extra={
            "tool": "vector_search",
            "action": "add_gherkin_steps",
            "steps_count": len(cleaned_steps),
            "context": operation_context.dict(),
            "audit": True
        }
    )
    
    try:
        # Get vector store service
        vector_store = await VectorStoreService.get_instance()
        
        # Add steps to vector store
        await vector_store.add_gherkin_steps(
            steps=cleaned_steps,
            context=operation_context.dict()
        )
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        response = {
            "success": True,
            "steps_added": len(cleaned_steps),
            "execution_time_ms": execution_time,
            "message": f"Successfully added {len(cleaned_steps)} Gherkin steps to vector store",
            "metadata": {
                "original_count": len(steps),
                "cleaned_count": len(cleaned_steps),
                "context": operation_context.dict()
            }
        }
        
        logger.info(
            f"Successfully added {len(cleaned_steps)} Gherkin steps in {execution_time:.2f}ms",
            extra={
                "tool": "vector_search",
                "action": "add_gherkin_steps_complete",
                "steps_added": len(cleaned_steps),
                "execution_time_ms": execution_time,
                "audit": True
            }
        )
        
        return response
        
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.error(
            f"Failed to add Gherkin steps: {e}",
            extra={
                "tool": "vector_search",
                "action": "add_gherkin_steps_error",
                "error": str(e),
                "execution_time_ms": execution_time,
                "audit": True
            },
            exc_info=True
        )
        
        if isinstance(e, (MCPValidationError, VectorStoreError)):
            raise
        
        raise MCPOperationError(f"Failed to add Gherkin steps: {e}", operation="add_gherkin_steps")


@mcp_server.tool()
async def clear_page_elements(
    page_url: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Clear all DOM elements for a specific page from the vector store.
    
    This tool removes all stored DOM elements for a given page URL,
    useful for cleanup when a page structure changes significantly.
    
    Args:
        page_url: URL of the page to clear elements for
        context: Operation context information
    
    Returns:
        Dictionary containing operation results and performance info
    
    Raises:
        MCPValidationError: Invalid page URL
        VectorStoreError: Vector store operation failed
    """
    start_time = datetime.utcnow()
    
    # Validate inputs
    if not page_url or not page_url.strip():
        raise MCPValidationError("Page URL cannot be empty")
    
    # Create enriched context
    operation_context = VectorSearchToolContext(
        search_intent="dom_element_cleanup",
        page_url=page_url,
        **(context or {})
    )
    
    logger.info(
        f"Clearing DOM elements for page: {page_url}",
        extra={
            "tool": "vector_search",
            "action": "clear_page_elements",
            "page_url": page_url,
            "context": operation_context.dict(),
            "audit": True
        }
    )
    
    try:
        # Get vector store service
        vector_store = await VectorStoreService.get_instance()
        
        # Clear elements for the page
        await vector_store.clear_page_elements(page_url.strip())
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        response = {
            "success": True,
            "message": f"Successfully cleared elements for page: {page_url}",
            "execution_time_ms": execution_time,
            "metadata": {
                "page_url": page_url,
                "context": operation_context.dict()
            }
        }
        
        logger.info(
            f"Successfully cleared elements for page in {execution_time:.2f}ms",
            extra={
                "tool": "vector_search",
                "action": "clear_page_elements_complete",
                "page_url": page_url,
                "execution_time_ms": execution_time,
                "audit": True
            }
        )
        
        return response
        
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.error(
            f"Failed to clear page elements: {e}",
            extra={
                "tool": "vector_search",
                "action": "clear_page_elements_error",
                "page_url": page_url,
                "error": str(e),
                "execution_time_ms": execution_time,
                "audit": True
            },
            exc_info=True
        )
        
        if isinstance(e, (MCPValidationError, VectorStoreError)):
            raise
        
        raise MCPOperationError(f"Failed to clear page elements: {e}", operation="clear_page_elements")


@mcp_server.tool()
async def vector_store_health_check(
    include_metrics: bool = True,
    test_collections: bool = False,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Perform health check on the vector store service.
    
    This tool checks the operational status of the vector store service,
    including collection connectivity and performance metrics.
    
    Args:
        include_metrics: Include performance metrics in response
        test_collections: Test collection connectivity (may add latency)
        context: Operation context information
    
    Returns:
        Dictionary containing health status and metrics
    """
    start_time = datetime.utcnow()
    
    logger.info(
        "Vector store health check initiated",
        extra={
            "tool": "vector_search",
            "action": "health_check",
            "include_metrics": include_metrics,
            "test_collections": test_collections,
            "context": context,
            "audit": True
        }
    )
    
    try:
        # Get vector store service
        vector_store = await VectorStoreService.get_instance()
        
        # Perform health check
        health_status = await vector_store.health_check()
        
        # Add metrics if requested
        if include_metrics:
            metrics = await vector_store.get_metrics()
            health_status["metrics"] = metrics.dict()
        
        # Calculate execution time
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        health_status["health_check_time_ms"] = execution_time
        
        logger.info(
            f"Vector store health check completed: {health_status.get('status')} in {execution_time:.2f}ms",
            extra={
                "tool": "vector_search",
                "action": "health_check_complete",
                "status": health_status.get('status'),
                "execution_time_ms": execution_time,
                "audit": True
            }
        )
        
        return health_status
        
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.error(
            f"Vector store health check failed: {e}",
            extra={
                "tool": "vector_search",
                "action": "health_check_error",
                "error": str(e),
                "execution_time_ms": execution_time,
                "audit": True
            },
            exc_info=True
        )
        
        return {
            "service": "vector_store",
            "status": "unhealthy",
            "error": str(e),
            "health_check_time_ms": execution_time
        } 