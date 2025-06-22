"""
MCP Server Settings Configuration

Environment-driven configuration management for the IntelliBrowse MCP Server.
All sensitive configuration comes from environment variables, no hardcoded secrets.
"""

from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class MCPSettings(BaseSettings):
    """
    MCP Server configuration settings loaded from environment variables.
    """
    
    # Server Configuration
    mcp_host: str = Field(default="127.0.0.1", description="MCP server host")
    mcp_port: int = Field(default=8001, description="MCP server port")
    mcp_rest_port: int = Field(default=8002, description="REST API server port for legacy compatibility")
    mcp_transport: str = Field(default="sse", description="Transport protocol (sse, stdio)")
    
    # OpenAI Configuration
    openai_api_key: str = Field(default="", description="OpenAI API key for LLM operations")
    openai_model: str = Field(default="gpt-4", description="Default OpenAI model")
    openai_max_tokens: int = Field(default=4000, description="Maximum tokens per request")
    openai_temperature: float = Field(default=0.1, description="Model temperature")
    
    # MongoDB Configuration  
    mongodb_url: str = Field(default="mongodb://localhost:27017", description="MongoDB connection URL")
    mongodb_database: str = Field(default="intellibrowse_mcp", description="Database name")
    
    # Security Configuration
    jwt_secret: str = Field(default="development-secret-key-change-in-production", description="JWT secret key for token generation")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiry_hours: int = Field(default=24, description="JWT token expiry in hours")
    oauth_client_id: Optional[str] = Field(default=None, description="OAuth client ID")
    oauth_client_secret: Optional[str] = Field(default=None, description="OAuth client secret")
    oauth_authority: Optional[str] = Field(default=None, description="OAuth authority URL")
    
    # Session Configuration
    session_ttl_hours: int = Field(default=24, description="Session TTL in hours")
    session_cleanup_interval_minutes: int = Field(default=30, description="Session cleanup interval")
    max_concurrent_sessions: int = Field(default=1000, description="Maximum concurrent sessions")
    
    # RBAC Configuration
    default_user_role: str = Field(default="viewer", description="Default role for new users")
    admin_users: str = Field(default="", description="Comma-separated list of admin user IDs")
    
    # Audit Configuration
    audit_log_enabled: bool = Field(default=True, description="Enable audit logging")
    audit_log_file: str = Field(default="audit.log", description="Audit log file path")
    audit_retention_days: int = Field(default=90, description="Audit log retention in days")
    
    # Rate Limiting
    rate_limit_requests_per_minute: int = Field(default=60, description="Rate limit per minute")
    rate_limit_burst_size: int = Field(default=10, description="Rate limit burst size")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Logging format (json, text)")
    
    # Vector Database Configuration (ChromaDB)
    chroma_host: str = Field(default="localhost", description="ChromaDB host")
    chroma_port: int = Field(default=8000, description="ChromaDB port")
    chroma_collection_name: str = Field(default="intellibrowse_sessions", description="ChromaDB collection")
    
    # Vector Store Configuration (Enterprise ChromaDB Integration)
    mcp_vector_persist_path: str = Field(default="./chroma_db", env="MCP_VECTOR_PERSIST_PATH", description="ChromaDB persistent storage path")
    mcp_vector_embedding_model: str = Field(default="all-MiniLM-L6-v2", env="MCP_VECTOR_EMBEDDING_MODEL", description="Sentence transformer model for embeddings")
    mcp_vector_dom_collection: str = Field(default="dom_elements", env="MCP_VECTOR_DOM_COLLECTION", description="DOM elements collection name")
    mcp_vector_gherkin_collection: str = Field(default="gherkin_steps", env="MCP_VECTOR_GHERKIN_COLLECTION", description="Gherkin steps collection name")
    mcp_vector_batch_size: int = Field(default=100, env="MCP_VECTOR_BATCH_SIZE", description="Batch size for bulk operations", ge=1, le=1000)
    mcp_vector_max_results: int = Field(default=100, env="MCP_VECTOR_MAX_RESULTS", description="Maximum results per query", ge=1, le=1000)
    mcp_vector_similarity_threshold: float = Field(default=0.7, env="MCP_VECTOR_SIMILARITY_THRESHOLD", description="Default similarity threshold", ge=0.0, le=1.0)
    mcp_vector_enable_caching: bool = Field(default=True, env="MCP_VECTOR_ENABLE_CACHING", description="Enable result caching")
    mcp_vector_cache_ttl: int = Field(default=300, env="MCP_VECTOR_CACHE_TTL", description="Cache TTL in seconds", ge=0)
    
    # Legacy ChromaDB Configuration (deprecated - use mcp_vector_* settings)
    chroma_persist_path: str = Field(default="./chroma_db", description="ChromaDB persistent storage path")
    chroma_dom_collection: str = Field(default="dom_elements", description="DOM elements collection name")
    chroma_gherkin_collection: str = Field(default="gherkin_steps", description="Gherkin steps collection name")
    chroma_embedding_model: str = Field(default="all-MiniLM-L6-v2", description="Sentence transformer model for embeddings")
    chroma_max_results: int = Field(default=10, description="Maximum results returned by vector search")
    chroma_similarity_threshold: float = Field(default=0.7, description="Similarity threshold for vector search")
    chroma_collection_ttl_hours: int = Field(default=24, description="Collection TTL in hours")
    chroma_enable_hnsw: bool = Field(default=True, description="Enable HNSW indexing for performance")
    chroma_batch_size: int = Field(default=100, description="Batch size for bulk operations")
    
    # Tool Configuration
    enabled_tools: str = Field(
        default="bdd_generator,locator_generator,step_generator,selector_healer,debug_analyzer",
        description="Comma-separated list of enabled tools"
    )
    
    # Prompt Configuration
    prompt_cache_ttl_minutes: int = Field(default=30, description="Prompt cache TTL")
    
    # Resource Configuration
    resource_cache_ttl_minutes: int = Field(default=15, description="Resource cache TTL")
    dom_snapshot_max_size_mb: int = Field(default=10, description="Max DOM snapshot size in MB")
    
    # Browser Automation (Playwright)
    playwright_browser: str = Field(default="chromium", description="Default browser for Playwright")
    playwright_headless: bool = Field(default=True, description="Run browser in headless mode")
    playwright_timeout_ms: int = Field(default=30000, description="Browser operation timeout")
    
    # Development Configuration
    debug_mode: bool = Field(default=False, description="Enable debug mode")
    enable_inspector: bool = Field(default=True, description="Enable MCP inspector")
    
    # Session Management
    session_cleanup_interval_minutes: int = Field(default=30, description="Session cleanup interval")
    
    # State Management & Persistence
    data_directory: str = Field(default="./data", description="Data directory for state persistence")
    state_persistence_enabled: bool = Field(default=True, description="Enable state persistence")
    state_cleanup_interval_hours: int = Field(default=6, description="State cleanup interval in hours")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @field_validator("mcp_transport")
    @classmethod
    def validate_transport(cls, v):
        """Validate MCP transport protocol."""
        valid_transports = ["sse", "stdio", "streamable-http"]
        if v not in valid_transports:
            raise ValueError(f"Transport must be one of {valid_transports}")
        return v
    
    @field_validator("openai_temperature")
    @classmethod
    def validate_temperature(cls, v):
        """Validate OpenAI temperature."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v
    
    def get_enabled_tools_list(self) -> List[str]:
        """Convert enabled_tools string to list."""
        if not self.enabled_tools:
            return []
        
        # Handle JSON array format (e.g., ["tool1","tool2"])
        if self.enabled_tools.startswith('[') and self.enabled_tools.endswith(']'):
            try:
                import json
                return json.loads(self.enabled_tools)
            except json.JSONDecodeError:
                pass
        
        # Handle comma-separated format (e.g., "tool1,tool2")
        return [tool.strip() for tool in self.enabled_tools.split(',') if tool.strip()]
    
    def get_admin_users_list(self) -> List[str]:
        """Convert admin_users string to list."""
        if not self.admin_users:
            return []
        return [user.strip() for user in self.admin_users.split(',') if user.strip()]
    
    class Config:
        env_file = [".env.example", ".env"]  # Try .env.example first, then .env
        env_prefix = "MCP_"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from env file


# Global settings instance
def get_settings() -> MCPSettings:
    """Get MCP settings instance."""
    return MCPSettings()

# For backward compatibility
settings = get_settings() 