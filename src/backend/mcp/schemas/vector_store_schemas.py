"""
Vector Store Schemas for IntelliBrowse MCP Server

This module defines comprehensive Pydantic schemas for vector store operations,
including DOM elements, Gherkin steps, search requests/responses, and metrics.

Features:
- Type-safe data models with validation
- Request/response schemas for MCP tools
- Metrics and monitoring schemas
- Configuration validation schemas
- Enterprise-grade validation rules
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field, field_validator, root_validator


class LocatorStrategy(str, Enum):
    """Supported locator strategies for DOM elements."""
    CSS = "css"
    XPATH = "xpath"
    DATA_TESTID = "data-testid"
    ACCESSIBILITY = "accessibility"
    TEXT = "text"
    AUTO = "auto"


class GherkinStepType(str, Enum):
    """Gherkin step types."""
    GIVEN = "given"
    WHEN = "when"
    THEN = "then"
    AND = "and"
    BUT = "but"


class DOMElementLocator(BaseModel):
    """Schema for DOM element locator."""
    strategy: LocatorStrategy = Field(..., description="Locator strategy used")
    value: str = Field(..., min_length=1, description="Locator value/selector")
    priority: int = Field(default=1, ge=1, le=10, description="Priority ranking (1=highest)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    options: Dict[str, Any] = Field(default_factory=dict, description="Additional locator options")
    
    class Config:
        use_enum_values = True


class DOMElementMetadata(BaseModel):
    """Schema for DOM element metadata."""
    tag: str = Field(..., description="HTML tag name")
    attributes: Dict[str, str] = Field(default_factory=dict, description="Element attributes")
    text: Optional[str] = Field(None, description="Element text content")
    accessible_name: Optional[str] = Field(None, description="Accessible name")
    role: Optional[str] = Field(None, description="ARIA role")
    bounding_box: Optional[Dict[str, float]] = Field(None, description="Element bounding box")
    is_visible: bool = Field(default=True, description="Element visibility")
    
    @field_validator('tag')
    @classmethod
    def validate_tag(cls, v):
        if not v or not v.strip():
            raise ValueError("Tag name cannot be empty")
        return v.lower().strip()


class ElementAnalysisData(BaseModel):
    """Schema for element analysis data from locator generator."""
    element_id: Optional[str] = Field(None, description="Unique element identifier")
    metadata: DOMElementMetadata = Field(..., description="Element metadata")
    locators: List[DOMElementLocator] = Field(..., min_items=1, description="Generated locators")
    description: Optional[str] = Field(None, description="Human-readable description")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Overall confidence")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Analysis timestamp")
    
    def get_description_string(self) -> str:
        """Generate description string for vector embedding."""
        if self.description:
            return self.description
        
        # Build description from metadata
        parts = [f"{self.metadata.tag} element"]
        
        if self.metadata.role:
            parts.append(f"with role '{self.metadata.role}'")
        
        if self.metadata.accessible_name:
            parts.append(f"named '{self.metadata.accessible_name}'")
        elif self.metadata.text:
            text_preview = self.metadata.text[:50] + "..." if len(self.metadata.text) > 50 else self.metadata.text
            parts.append(f"containing text '{text_preview}'")
        
        # Add key attributes
        attrs = self.metadata.attributes
        if attrs.get('id'):
            parts.append(f"with id '{attrs['id']}'")
        elif attrs.get('class'):
            parts.append(f"with class '{attrs['class']}'")
        elif attrs.get('data-testid'):
            parts.append(f"with test id '{attrs['data-testid']}'")
        
        return " ".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "element_id": self.element_id,
            "metadata": self.metadata.dict(),
            "locators": [loc.dict() for loc in self.locators],
            "description": self.description,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat()
        }
    
    def get_best_locator(self) -> Optional[DOMElementLocator]:
        """Get the highest priority locator."""
        if not self.locators:
            return None
        return min(self.locators, key=lambda x: x.priority)


class DOMElementData(BaseModel):
    """Schema for DOM element vector store data."""
    page_url: str = Field(..., description="URL of the page containing the element")
    element_analysis: ElementAnalysisData = Field(..., description="Element analysis data")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    
    @field_validator('page_url')
    @classmethod
    def validate_page_url(cls, v):
        if not v or not v.strip():
            raise ValueError("Page URL cannot be empty")
        return v.strip()


class GherkinStepData(BaseModel):
    """Schema for Gherkin step data."""
    step_id: Optional[str] = Field(None, description="Unique step identifier")
    step_text: str = Field(..., min_length=1, description="Gherkin step text")
    step_type: GherkinStepType = Field(..., description="Step type (Given/When/Then/And/But)")
    tags: List[str] = Field(default_factory=list, description="Associated tags")
    feature_context: Optional[str] = Field(None, description="Feature context")
    scenario_context: Optional[str] = Field(None, description="Scenario context")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Step creation timestamp")
    
    @field_validator('step_text')

    
    @classmethod
    def validate_step_text(cls, v):
        if not v or not v.strip():
            raise ValueError("Step text cannot be empty")
        return v.strip()
    
    class Config:
        use_enum_values = True


class VectorSearchRequest(BaseModel):
    """Schema for vector search requests."""
    query_description: str = Field(..., min_length=1, description="Search query description")
    page_url: Optional[str] = Field(None, description="Filter by page URL")
    n_results: int = Field(default=5, ge=1, le=50, description="Number of results to return")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional filters")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity threshold")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Search context")
    
    @field_validator('query_description')

    
    @classmethod
    def validate_query_description(cls, v):
        if not v or not v.strip():
            raise ValueError("Query description cannot be empty")
        return v.strip()


class VectorSearchResult(BaseModel):
    """Schema for individual vector search result."""
    id: str = Field(..., description="Element/step identifier")
    description: str = Field(..., description="Element/step description")
    metadata: Dict[str, Any] = Field(..., description="Result metadata")
    locators: Optional[List[DOMElementLocator]] = Field(None, description="Element locators (for DOM results)")
    step_text: Optional[str] = Field(None, description="Step text (for Gherkin results)")
    distance: Optional[float] = Field(None, description="Vector distance")
    similarity_score: Optional[float] = Field(None, description="Similarity score (0-1)")
    
    @field_validator('similarity_score')

    
    @classmethod
    def validate_similarity_score(cls, v):
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Similarity score must be between 0.0 and 1.0")
        return v


class VectorSearchResponse(BaseModel):
    """Schema for vector search response."""
    success: bool = Field(..., description="Search success status")
    query: str = Field(..., description="Original query")
    results: List[VectorSearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., ge=0, description="Total number of results")
    execution_time_ms: float = Field(..., ge=0, description="Execution time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    error_message: Optional[str] = Field(None, description="Error message if search failed")


class VectorStoreMetrics(BaseModel):
    """Schema for vector store metrics and statistics."""
    dom_elements_stored: int = Field(default=0, ge=0, description="Number of DOM elements stored")
    gherkin_steps_stored: int = Field(default=0, ge=0, description="Number of Gherkin steps stored")
    dom_queries_executed: int = Field(default=0, ge=0, description="Number of DOM queries executed")
    gherkin_queries_executed: int = Field(default=0, ge=0, description="Number of Gherkin queries executed")
    last_dom_update: Optional[datetime] = Field(None, description="Last DOM update timestamp")
    last_gherkin_update: Optional[datetime] = Field(None, description="Last Gherkin update timestamp")
    average_query_time_ms: float = Field(default=0.0, ge=0, description="Average query time in milliseconds")
    cache_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Cache hit rate")
    
    def update_query_time(self, duration_ms: float) -> None:
        """Update average query time with new measurement."""
        total_queries = self.dom_queries_executed + self.gherkin_queries_executed
        if total_queries > 1:
            self.average_query_time_ms = (
                (self.average_query_time_ms * (total_queries - 1) + duration_ms) / total_queries
            )
        else:
            self.average_query_time_ms = duration_ms


class VectorStoreConfig(BaseModel):
    """Schema for vector store configuration."""
    persist_path: str = Field(..., description="ChromaDB persistence path")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", description="Embedding model name")
    dom_collection_name: str = Field(default="dom_elements", description="DOM collection name")
    gherkin_collection_name: str = Field(default="gherkin_steps", description="Gherkin collection name")
    batch_size: int = Field(default=100, ge=1, le=1000, description="Batch processing size")
    max_results: int = Field(default=100, ge=1, le=1000, description="Maximum results per query")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Default similarity threshold")
    enable_caching: bool = Field(default=True, description="Enable result caching")
    cache_ttl_seconds: int = Field(default=300, ge=0, description="Cache TTL in seconds")
    
    @field_validator('persist_path')

    
    @classmethod
    def validate_persist_path(cls, v):
        if not v or not v.strip():
            raise ValueError("Persist path cannot be empty")
        return v.strip()
    
    @field_validator('embedding_model')

    
    @classmethod
    def validate_embedding_model(cls, v):
        if not v or not v.strip():
            raise ValueError("Embedding model cannot be empty")
        return v.strip()


class AddElementsRequest(BaseModel):
    """Schema for add elements request."""
    page_url: str = Field(..., description="Page URL")
    elements: List[ElementAnalysisData] = Field(..., min_items=1, description="Elements to add")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Request context")
    
    @field_validator('page_url')

    
    @classmethod
    def validate_page_url(cls, v):
        if not v or not v.strip():
            raise ValueError("Page URL cannot be empty")
        return v.strip()


class AddElementsResponse(BaseModel):
    """Schema for add elements response."""
    success: bool = Field(..., description="Operation success status")
    elements_added: int = Field(..., ge=0, description="Number of elements added")
    execution_time_ms: float = Field(..., ge=0, description="Execution time in milliseconds")
    message: str = Field(..., description="Success/error message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")


class AddGherkinStepsRequest(BaseModel):
    """Schema for add Gherkin steps request."""
    steps: List[str] = Field(..., min_items=1, description="Gherkin steps to add")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Request context")
    
    @field_validator('steps')

    
    @classmethod
    def validate_steps(cls, v):
        if not v:
            raise ValueError("Steps list cannot be empty")
        cleaned_steps = [step.strip() for step in v if step and step.strip()]
        if not cleaned_steps:
            raise ValueError("All steps are empty or whitespace")
        return cleaned_steps


class AddGherkinStepsResponse(BaseModel):
    """Schema for add Gherkin steps response."""
    success: bool = Field(..., description="Operation success status")
    steps_added: int = Field(..., ge=0, description="Number of steps added")
    execution_time_ms: float = Field(..., ge=0, description="Execution time in milliseconds")
    message: str = Field(..., description="Success/error message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")


class QueryElementsRequest(BaseModel):
    """Schema for query elements request."""
    query_description: str = Field(..., min_length=1, description="Element description to search for")
    page_url: Optional[str] = Field(None, description="Filter by page URL")
    n_results: int = Field(default=5, ge=1, le=50, description="Number of results to return")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional filters")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity threshold")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query context")
    
    @field_validator('query_description')

    
    @classmethod
    def validate_query_description(cls, v):
        if not v or not v.strip():
            raise ValueError("Query description cannot be empty")
        return v.strip()


class QueryElementsResponse(BaseModel):
    """Schema for query elements response."""
    success: bool = Field(..., description="Query success status")
    query: str = Field(..., description="Original query")
    results: List[VectorSearchResult] = Field(..., description="Query results")
    total_results: int = Field(..., ge=0, description="Total number of results")
    execution_time_ms: float = Field(..., ge=0, description="Execution time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")


class QueryGherkinStepsRequest(BaseModel):
    """Schema for query Gherkin steps request."""
    query_text: str = Field(..., min_length=1, description="Step text to search for")
    n_results: int = Field(default=3, ge=1, le=20, description="Number of results to return")
    step_type: Optional[GherkinStepType] = Field(None, description="Filter by step type")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    similarity_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Minimum similarity threshold")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query context")
    
    @field_validator('query_text')

    
    @classmethod
    def validate_query_text(cls, v):
        if not v or not v.strip():
            raise ValueError("Query text cannot be empty")
        return v.strip()
    
    class Config:
        use_enum_values = True


class QueryGherkinStepsResponse(BaseModel):
    """Schema for query Gherkin steps response."""
    success: bool = Field(..., description="Query success status")
    query: str = Field(..., description="Original query")
    results: List[VectorSearchResult] = Field(..., description="Query results")
    total_results: int = Field(..., ge=0, description="Total number of results")
    execution_time_ms: float = Field(..., ge=0, description="Execution time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")


class ClearPageElementsRequest(BaseModel):
    """Schema for clear page elements request."""
    page_url: str = Field(..., description="Page URL to clear elements for")
    
    @field_validator('page_url')

    
    @classmethod
    def validate_page_url(cls, v):
        if not v or not v.strip():
            raise ValueError("Page URL cannot be empty")
        return v.strip()


class ClearPageElementsResponse(BaseModel):
    """Schema for clear page elements response."""
    success: bool = Field(..., description="Operation success status")
    elements_cleared: int = Field(..., ge=0, description="Number of elements cleared")
    message: str = Field(..., description="Success/error message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")


class HealthCheckRequest(BaseModel):
    """Schema for health check request."""
    include_metrics: bool = Field(default=True, description="Include metrics in response")
    test_collections: bool = Field(default=False, description="Test collection connectivity")


class HealthCheckResponse(BaseModel):
    """Schema for health check response."""
    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status (healthy/degraded/unhealthy)")
    initialized: bool = Field(..., description="Service initialization status")
    dom_collection_ready: bool = Field(..., description="DOM collection readiness")
    gherkin_collection_ready: bool = Field(..., description="Gherkin collection readiness")
    embedding_model: str = Field(..., description="Current embedding model")
    metrics: Optional[VectorStoreMetrics] = Field(None, description="Service metrics")
    dom_collection_status: Optional[str] = Field(None, description="DOM collection test status")
    gherkin_collection_status: Optional[str] = Field(None, description="Gherkin collection test status")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


# Legacy compatibility schemas (for migration support)
class LegacyElementSearchResult(BaseModel):
    """Legacy schema for element search results."""
    element_id: str = Field(..., description="Element identifier")
    description: str = Field(..., description="Element description")
    locators: List[Dict[str, Any]] = Field(..., description="Element locators")
    similarity_score: float = Field(..., description="Similarity score")
    metadata: Dict[str, Any] = Field(..., description="Element metadata")


class LegacyGherkinStepSearchResult(BaseModel):
    """Legacy schema for Gherkin step search results."""
    step_id: str = Field(..., description="Step identifier")
    step_text: str = Field(..., description="Step text")
    step_type: str = Field(..., description="Step type")
    similarity_score: float = Field(..., description="Similarity score")
    metadata: Dict[str, Any] = Field(..., description="Step metadata") 