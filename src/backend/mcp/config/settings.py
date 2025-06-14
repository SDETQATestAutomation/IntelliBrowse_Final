"""
MCP Server Settings Configuration

Environment-driven configuration management for the IntelliBrowse MCP Server.
All sensitive configuration comes from environment variables, no hardcoded secrets.
"""

from typing import Optional, List
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class MCPSettings(BaseSettings):
    """
    MCP Server configuration settings loaded from environment variables.
    """
    
    # Server Configuration
    mcp_host: str = Field(default="127.0.0.1", description="MCP server host")
    mcp_port: int = Field(default=8001, description="MCP server port")
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
    max_concurrent_sessions: int = Field(default=100, description="Max concurrent sessions per user")
    
    # RBAC Configuration
    default_user_role: str = Field(default="viewer", description="Default role for new users")
    admin_users: List[str] = Field(default=[], description="List of admin user IDs")
    
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
    
    # Tool Configuration
    enabled_tools: List[str] = Field(
        default=["bdd_generator", "locator_generator", "step_generator", "selector_healer", "debug_analyzer"],
        description="List of enabled tools"
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
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @validator("mcp_transport")
    def validate_transport(cls, v):
        """Validate MCP transport protocol."""
        valid_transports = ["sse", "stdio"]
        if v not in valid_transports:
            raise ValueError(f"Transport must be one of {valid_transports}")
        return v
    
    @validator("openai_temperature")
    def validate_temperature(cls, v):
        """Validate OpenAI temperature."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v
    
    class Config:
        env_file = ".env"
        env_prefix = "MCP_"
        case_sensitive = False


# Global settings instance
def get_settings() -> MCPSettings:
    """Get MCP settings instance."""
    return MCPSettings()

# For backward compatibility
settings = get_settings() 