"""
Environment configuration for IntelliBrowse backend.
Manages application settings, database connections, and authentication configuration.
"""

import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Provides type-safe configuration with validation and defaults.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application Configuration
    app_name: str = Field(default="IntelliBrowse", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    environment: str = Field(default="development", description="Environment (development/staging/production)")
    debug: bool = Field(default=True, description="Enable debug mode")
    
    # Security Configuration
    secret_key: str = Field(
        default="your-secret-key-here-change-in-production",
        description="Application secret key for security operations"
    )
    
    # JWT Authentication Configuration
    jwt_secret_key: str = Field(
        default="your-jwt-secret-key-change-in-production-make-it-long-and-random",
        description="Secret key for JWT token signing and verification"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_expiry_minutes: int = Field(default=60, description="JWT token expiry time in minutes")
    
    # Database Configuration
    mongodb_url: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URL"
    )
    mongodb_db_name: str = Field(
        default="intellibrowse",
        description="MongoDB database name"
    )
    mongodb_collection_users: str = Field(
        default="users",
        description="MongoDB collection name for users"
    )
    
    # Test Suite Configuration
    test_suite_ttl_days: int = Field(
        default=90,
        description="TTL for archived test suites in days (0 = disabled)"
    )
    test_suite_max_items: int = Field(
        default=1000,
        description="Maximum items allowed per test suite"
    )
    
    # Logging Configuration
    log_level: str = Field(default="INFO", description="Console log level")
    log_to_file: bool = Field(default=True, description="Enable file logging")
    log_file_path: str = Field(default="logs/intellibrowse.log", description="Log file path")
    log_level_file: str = Field(default="DEBUG", description="File log level")
    
    # API Configuration
    api_prefix: str = Field(default="/api/v1", description="API URL prefix")
    enable_cors: bool = Field(default=True, description="Enable CORS middleware")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins"
    )
    
    # Server Configuration
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, description="Server port")
    reload: bool = Field(default=True, description="Enable auto-reload in development")
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment is one of the allowed values."""
        allowed = ["development", "staging", "production"]
        if v.lower() not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v.lower()
    
    @field_validator("log_level", "log_level_file")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level is supported by loguru."""
        allowed = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v.upper()
    
    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, v):
        """Validate JWT algorithm is supported."""
        allowed = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        if v.upper() not in allowed:
            raise ValueError(f"JWT algorithm must be one of {allowed}")
        return v.upper()
    
    @field_validator("jwt_expiry_minutes")
    @classmethod
    def validate_jwt_expiry(cls, v):
        """Validate JWT expiry is reasonable (1 minute to 24 hours)."""
        if not 1 <= v <= 1440:  # 1 minute to 24 hours
            raise ValueError("JWT expiry must be between 1 and 1440 minutes")
        return v
    
    @field_validator("port")
    @classmethod
    def validate_port(cls, v):
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v
    
    @field_validator("test_suite_ttl_days")
    @classmethod
    def validate_ttl_days(cls, v):
        """Validate TTL days is reasonable (0 = disabled, max 1 year)."""
        if not 0 <= v <= 365:
            raise ValueError("TTL days must be between 0 (disabled) and 365")
        return v
    
    @field_validator("test_suite_max_items")
    @classmethod
    def validate_max_items(cls, v):
        """Validate max items per suite is reasonable."""
        if not 1 <= v <= 10000:
            raise ValueError("Max items per suite must be between 1 and 10000")
        return v
    
    @property
    def mongodb_database(self) -> str:
        """Get MongoDB database name for convenience."""
        return self.mongodb_db_name
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment == "testing"
    
    def get_mongodb_connection_params(self) -> dict:
        """Get MongoDB connection parameters."""
        return {
            "url": self.mongodb_url,
            "database": self.mongodb_db_name,
            "collection_users": self.mongodb_collection_users,
        }
    
    def get_jwt_settings(self) -> dict:
        """Get JWT configuration parameters."""
        return {
            "secret_key": self.jwt_secret_key,
            "algorithm": self.jwt_algorithm,
            "expiry_minutes": self.jwt_expiry_minutes,
        }
    
    def get_cors_origins(self) -> List[str]:
        """Get CORS origins configuration."""
        return self.cors_origins
    
    def get_test_suite_config(self) -> dict:
        """Get test suite configuration parameters."""
        return {
            "ttl_days": self.test_suite_ttl_days,
            "max_items": self.test_suite_max_items,
            "ttl_enabled": self.test_suite_ttl_days > 0,
        }


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get the global settings instance.
    Uses singleton pattern to ensure consistent configuration across the application.
    
    Returns:
        Settings instance with loaded configuration
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Force reload of settings from environment.
    Useful for testing or when environment variables change.
    
    Returns:
        New Settings instance with reloaded configuration
    """
    global _settings
    _settings = None
    return get_settings()


# Development helper
if __name__ == "__main__":
    settings = get_settings()
    print(f"Application: {settings.app_name} v{settings.app_version}")
    print(f"Environment: {settings.environment}")
    print(f"Debug: {settings.debug}")
    print(f"MongoDB: {settings.mongodb_url}/{settings.mongodb_db_name}")
    print(f"JWT Algorithm: {settings.jwt_algorithm}")
    print(f"JWT Expiry: {settings.jwt_expiry_minutes} minutes")
    print(f"Test Suite TTL: {settings.test_suite_ttl_days} days")
    print(f"Test Suite Max Items: {settings.test_suite_max_items}") 