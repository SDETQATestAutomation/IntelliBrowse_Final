"""
IntelliBrowse MCP Server - Schema Resource Provider

This module provides API schemas, data validation schemas, and test configuration
schemas as MCP resources. It manages schema definitions, validation rules, and
provides schema discovery and validation capabilities.

Resource URIs:
- schema://api/{api_name}/{version} - API schema definitions
- schema://validation/{schema_name} - Data validation schemas
- schema://config/{config_type} - Configuration schemas
- schema://openapi/{service_name} - OpenAPI specifications
- schema://jsonschema/{schema_name} - JSON Schema definitions
"""

import json
import yaml
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
import asyncio

try:
    from config.settings import get_settings
except ImportError:
    # Fallback for when running directly from mcp directory
    from config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)

# Import MCP server instance from server_instance module
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server
except ImportError:
    # Handle relative import issues for testing
    import sys
    from pathlib import Path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir.parent))
    from server_instance import mcp_server


class SchemaDefinition(BaseModel):
    """Schema definition with metadata."""
    
    name: str = Field(description="Schema name")
    version: str = Field(description="Schema version")
    schema_type: str = Field(description="Type of schema (api, validation, config, openapi)")
    format: str = Field(description="Schema format (json, yaml, openapi)")
    description: str = Field(description="Schema description")
    schema_content: Dict[str, Any] = Field(description="Actual schema definition")
    examples: List[Dict[str, Any]] = Field(description="Schema usage examples")
    validation_rules: List[str] = Field(description="Validation rules")
    dependencies: List[str] = Field(description="Schema dependencies")
    tags: List[str] = Field(description="Schema tags for categorization")
    created_at: datetime = Field(description="Schema creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    metadata: Dict[str, Any] = Field(description="Additional metadata")


class APISchema(BaseModel):
    """API schema definition."""
    
    api_name: str = Field(description="API name")
    version: str = Field(description="API version")
    base_url: str = Field(description="API base URL")
    title: str = Field(description="API title")
    description: str = Field(description="API description")
    endpoints: List[Dict[str, Any]] = Field(description="API endpoints")
    models: Dict[str, Any] = Field(description="Data models")
    authentication: Dict[str, Any] = Field(description="Authentication requirements")
    rate_limits: Dict[str, Any] = Field(description="Rate limiting configuration")
    created_at: datetime = Field(description="Schema creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ValidationSchema(BaseModel):
    """Data validation schema."""
    
    schema_name: str = Field(description="Validation schema name")
    schema_type: str = Field(description="Schema type (jsonschema, pydantic, etc.)")
    target_type: str = Field(description="Target data type being validated")
    schema_definition: Dict[str, Any] = Field(description="Schema definition")
    validation_examples: List[Dict[str, Any]] = Field(description="Validation examples")
    error_messages: Dict[str, str] = Field(description="Custom error messages")
    strict_mode: bool = Field(description="Whether to use strict validation")
    created_at: datetime = Field(description="Schema creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ConfigSchema(BaseModel):
    """Configuration schema definition."""
    
    config_type: str = Field(description="Configuration type")
    schema_definition: Dict[str, Any] = Field(description="Configuration schema")
    default_values: Dict[str, Any] = Field(description="Default configuration values")
    required_fields: List[str] = Field(description="Required configuration fields")
    environment_variables: Dict[str, str] = Field(description="Environment variable mappings")
    validation_rules: List[str] = Field(description="Configuration validation rules")
    examples: List[Dict[str, Any]] = Field(description="Configuration examples")
    created_at: datetime = Field(description="Schema creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class OpenAPISpec(BaseModel):
    """OpenAPI specification."""
    
    service_name: str = Field(description="Service name")
    openapi_version: str = Field(description="OpenAPI specification version")
    info: Dict[str, Any] = Field(description="API information")
    servers: List[Dict[str, Any]] = Field(description="Server configurations")
    paths: Dict[str, Any] = Field(description="API paths and operations")
    components: Dict[str, Any] = Field(description="Reusable components")
    security: List[Dict[str, Any]] = Field(description="Security schemes")
    tags: List[Dict[str, Any]] = Field(description="API tags")
    external_docs: Optional[Dict[str, Any]] = Field(description="External documentation")
    created_at: datetime = Field(description="Spec creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class SchemaResourceProvider:
    """
    Provides schema definitions as MCP resources.
    
    This class manages various types of schemas including API schemas,
    validation schemas, configuration schemas, and OpenAPI specifications.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._schemas: Dict[str, SchemaDefinition] = {}
        self._api_schemas: Dict[str, APISchema] = {}
        self._validation_schemas: Dict[str, ValidationSchema] = {}
        self._config_schemas: Dict[str, ConfigSchema] = {}
        self._openapi_specs: Dict[str, OpenAPISpec] = {}
        
        # Initialize with sample schemas
        asyncio.create_task(self._initialize_sample_schemas())
    
    async def _initialize_sample_schemas(self):
        """Initialize sample schemas for testing."""
        try:
            now = datetime.now(timezone.utc)
            
            # Sample API Schema
            api_schema = APISchema(
                api_name="intellibrowse_api",
                version="v1",
                base_url="https://api.intellibrowse.com/v1",
                title="IntelliBrowse API",
                description="API for IntelliBrowse test automation platform",
                endpoints=[
                    {
                        "path": "/tests",
                        "method": "POST",
                        "summary": "Create new test",
                        "parameters": [
                            {"name": "name", "type": "string", "required": True},
                            {"name": "type", "type": "string", "required": True}
                        ],
                        "responses": {
                            "201": {"description": "Test created successfully"},
                            "400": {"description": "Invalid request data"}
                        }
                    }
                ],
                models={
                    "Test": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "type": {"type": "string", "enum": ["functional", "integration", "e2e"]},
                            "status": {"type": "string", "enum": ["pending", "running", "completed", "failed"]},
                            "created_at": {"type": "string", "format": "date-time"}
                        },
                        "required": ["name", "type"]
                    }
                },
                authentication={
                    "type": "bearer",
                    "token_url": "/auth/token",
                    "scopes": ["read", "write", "admin"]
                },
                rate_limits={
                    "requests_per_minute": 100,
                    "requests_per_hour": 1000
                },
                created_at=now,
                updated_at=now
            )
            
            self._api_schemas["intellibrowse_api_v1"] = api_schema
            
            # Sample Validation Schema
            validation_schema = ValidationSchema(
                schema_name="user_registration",
                schema_type="jsonschema",
                target_type="user",
                schema_definition={
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "minLength": 3,
                            "maxLength": 30
                        },
                        "email": {
                            "type": "string",
                            "format": "email"
                        },
                        "password": {
                            "type": "string",
                            "minLength": 8
                        }
                    },
                    "required": ["username", "email", "password"]
                },
                validation_examples=[
                    {
                        "valid": True,
                        "data": {
                            "username": "john_doe",
                            "email": "john@example.com",
                            "password": "SecurePass123!"
                        }
                    }
                ],
                error_messages={
                    "username.minLength": "Username must be at least 3 characters long",
                    "email.format": "Please provide a valid email address"
                },
                strict_mode=True,
                created_at=now,
                updated_at=now
            )
            
            self._validation_schemas["user_registration"] = validation_schema
            
            # Sample Configuration Schema
            config_schema = ConfigSchema(
                config_type="test_execution",
                schema_definition={
                    "type": "object",
                    "properties": {
                        "browser": {
                            "type": "string",
                            "enum": ["chromium", "firefox", "webkit"],
                            "default": "chromium"
                        },
                        "headless": {
                            "type": "boolean",
                            "default": True
                        },
                        "timeout": {
                            "type": "integer",
                            "minimum": 1000,
                            "maximum": 60000,
                            "default": 30000
                        }
                    },
                    "required": ["browser", "timeout"]
                },
                default_values={
                    "browser": "chromium",
                    "headless": True,
                    "timeout": 30000
                },
                required_fields=["browser", "timeout"],
                environment_variables={
                    "browser": "TEST_BROWSER",
                    "headless": "TEST_HEADLESS",
                    "timeout": "TEST_TIMEOUT"
                },
                validation_rules=[
                    "timeout must be between 1-60 seconds"
                ],
                examples=[
                    {
                        "name": "development",
                        "config": {
                            "browser": "chromium",
                            "headless": False,
                            "timeout": 10000
                        }
                    }
                ],
                created_at=now,
                updated_at=now
            )
            
            self._config_schemas["test_execution"] = config_schema
            
            logger.info("Initialized sample schemas",
                       api_schemas=len(self._api_schemas),
                       validation_schemas=len(self._validation_schemas),
                       config_schemas=len(self._config_schemas))
            
        except Exception as e:
            logger.error("Failed to initialize sample schemas", error=str(e), exc_info=True)
    
    async def _get_api_schema(self, api_name: str, version: str) -> Optional[APISchema]:
        """Get API schema by name and version."""
        schema_key = f"{api_name}_{version}"
        return self._api_schemas.get(schema_key)
    
    async def _get_validation_schema(self, schema_name: str) -> Optional[ValidationSchema]:
        """Get validation schema by name."""
        return self._validation_schemas.get(schema_name)
    
    async def _get_config_schema(self, config_type: str) -> Optional[ConfigSchema]:
        """Get configuration schema by type."""
        return self._config_schemas.get(config_type)


# MCP Resource Registration Functions
@mcp_server.resource("schema://api/{api_name}/{version}")
async def get_api_schema_resource(api_name: str, version: str) -> str:
    """
    Get API schema definition.
    
    Args:
        api_name: Name of the API
        version: API version
        
    Returns:
        JSON string containing API schema
    """
    try:
        provider = SchemaResourceProvider()
        api_schema = await provider._get_api_schema(api_name, version)
        
        if api_schema:
            logger.info("Retrieved API schema resource",
                       api_name=api_name,
                       version=version,
                       endpoints_count=len(api_schema.endpoints))
            
            return api_schema.model_dump_json(indent=2)
        else:
            return json.dumps({"error": "API schema not found"}, indent=2)
            
    except Exception as e:
        logger.error("Failed to get API schema resource",
                    api_name=api_name,
                    version=version,
                    error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("schema://validation/{schema_name}")
async def get_validation_schema_resource(schema_name: str) -> str:
    """
    Get validation schema definition.
    
    Args:
        schema_name: Name of the validation schema
        
    Returns:
        JSON string containing validation schema
    """
    try:
        provider = SchemaResourceProvider()
        validation_schema = await provider._get_validation_schema(schema_name)
        
        if validation_schema:
            logger.info("Retrieved validation schema resource",
                       schema_name=schema_name,
                       schema_type=validation_schema.schema_type,
                       target_type=validation_schema.target_type)
            
            return validation_schema.model_dump_json(indent=2)
        else:
            return json.dumps({"error": "Validation schema not found"}, indent=2)
            
    except Exception as e:
        logger.error("Failed to get validation schema resource",
                    schema_name=schema_name,
                    error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("schema://config/{config_type}")
async def get_config_schema_resource(config_type: str) -> str:
    """
    Get configuration schema definition.
    
    Args:
        config_type: Type of configuration schema
        
    Returns:
        JSON string containing configuration schema
    """
    try:
        provider = SchemaResourceProvider()
        config_schema = await provider._get_config_schema(config_type)
        
        if config_schema:
            logger.info("Retrieved config schema resource",
                       config_type=config_type,
                       required_fields_count=len(config_schema.required_fields),
                       examples_count=len(config_schema.examples))
            
            return config_schema.model_dump_json(indent=2)
        else:
            return json.dumps({"error": "Configuration schema not found"}, indent=2)
            
    except Exception as e:
        logger.error("Failed to get config schema resource",
                    config_type=config_type,
                    error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("schema://openapi/{service_name}")
async def get_openapi_spec_resource(service_name: str) -> str:
    """
    Get OpenAPI specification.
    
    Args:
        service_name: Name of the service
        
    Returns:
        JSON string containing OpenAPI specification
    """
    try:
        provider = SchemaResourceProvider()
        openapi_spec = await provider._get_openapi_spec(service_name)
        
        if openapi_spec:
            logger.info("Retrieved OpenAPI spec resource",
                       service_name=service_name,
                       openapi_version=openapi_spec.openapi_version,
                       paths_count=len(openapi_spec.paths))
            
            return openapi_spec.model_dump_json(indent=2)
        else:
            return json.dumps({"error": "OpenAPI specification not found"}, indent=2)
            
    except Exception as e:
        logger.error("Failed to get OpenAPI spec resource",
                    service_name=service_name,
                    error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("schema://jsonschema/{schema_name}")
async def get_jsonschema_resource(schema_name: str) -> str:
    """
    Get JSON Schema definition.
    
    Args:
        schema_name: Name of the JSON schema
        
    Returns:
        JSON string containing JSON schema definition
    """
    try:
        provider = SchemaResourceProvider()
        validation_schema = await provider._get_validation_schema(schema_name)
        
        if validation_schema and validation_schema.schema_type == "jsonschema":
            json_schema = {
                "name": validation_schema.schema_name,
                "target_type": validation_schema.target_type,
                "schema": validation_schema.schema_definition,
                "examples": validation_schema.validation_examples,
                "error_messages": validation_schema.error_messages,
                "strict_mode": validation_schema.strict_mode
            }
            
            logger.info("Retrieved JSON schema resource",
                       schema_name=schema_name,
                       target_type=validation_schema.target_type,
                       strict_mode=validation_schema.strict_mode)
            
            return json.dumps(json_schema, indent=2)
        else:
            return json.dumps({"error": "JSON schema not found"}, indent=2)
            
    except Exception as e:
        logger.error("Failed to get JSON schema resource",
                    schema_name=schema_name,
                    error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2) 