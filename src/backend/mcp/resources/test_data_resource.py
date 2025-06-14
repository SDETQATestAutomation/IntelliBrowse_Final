"""
IntelliBrowse MCP Server - Test Data Resource Provider

This module provides test data, fixtures, and validation datasets as MCP resources.
It manages test data across different formats (JSON, CSV, XML) and provides
validation states, mock data generation, and test data filtering.

Resource URIs:
- testdata://dataset/{dataset_name} - Complete test dataset
- testdata://fixture/{fixture_name} - Specific test fixture
- testdata://validation/{validation_set} - Validation dataset
- testdata://mock/{data_type} - Generated mock data
- testdata://filter/{dataset_name}/{filter_criteria} - Filtered dataset
"""

import json
import csv
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from pydantic import BaseModel, Field
import asyncio
import random
import string

from ..config.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)

# Import MCP server instance - will be set by main.py
mcp_server = None

def set_mcp_server(server):
    """Set the MCP server instance for resource registration."""
    global mcp_server
    mcp_server = server


class TestDataItem(BaseModel):
    """Individual test data item."""
    
    id: str = Field(description="Unique identifier for the data item")
    name: str = Field(description="Human-readable name")
    data_type: str = Field(description="Type of data (user, product, order, etc.)")
    category: str = Field(description="Data category (valid, invalid, edge_case)")
    priority: int = Field(description="Data priority (1=high, 5=low)")
    tags: List[str] = Field(description="Tags for filtering and categorization")
    values: Dict[str, Any] = Field(description="Actual data values")
    validation_rules: List[str] = Field(description="Validation rules applied")
    expected_outcomes: Dict[str, Any] = Field(description="Expected test outcomes")
    created_at: datetime = Field(description="Data creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    metadata: Dict[str, Any] = Field(description="Additional metadata")


class TestDataset(BaseModel):
    """Complete test dataset with metadata."""
    
    name: str = Field(description="Dataset name")
    description: str = Field(description="Dataset description")
    version: str = Field(description="Dataset version")
    format: str = Field(description="Data format (json, csv, xml)")
    total_records: int = Field(description="Total number of records")
    categories: Dict[str, int] = Field(description="Record count by category")
    tags: List[str] = Field(description="Available tags")
    items: List[TestDataItem] = Field(description="Test data items")
    schema: Dict[str, Any] = Field(description="Data schema definition")
    created_at: datetime = Field(description="Dataset creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class TestFixture(BaseModel):
    """Test fixture with setup and teardown data."""
    
    name: str = Field(description="Fixture name")
    description: str = Field(description="Fixture description")
    fixture_type: str = Field(description="Type of fixture (database, api, file, etc.)")
    scope: str = Field(description="Fixture scope (function, class, module, session)")
    setup_data: Dict[str, Any] = Field(description="Data for test setup")
    teardown_data: Dict[str, Any] = Field(description="Data for test cleanup")
    dependencies: List[str] = Field(description="Other fixtures this depends on")
    parameters: Dict[str, Any] = Field(description="Fixture parameters")
    created_at: datetime = Field(description="Fixture creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ValidationSet(BaseModel):
    """Validation dataset for testing data integrity."""
    
    name: str = Field(description="Validation set name")
    description: str = Field(description="Validation set description")
    validation_type: str = Field(description="Type of validation (schema, business, format)")
    test_cases: List[Dict[str, Any]] = Field(description="Validation test cases")
    expected_results: List[Dict[str, Any]] = Field(description="Expected validation results")
    schema_rules: Dict[str, Any] = Field(description="Schema validation rules")
    business_rules: List[str] = Field(description="Business validation rules")
    created_at: datetime = Field(description="Validation set creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class MockDataGenerator:
    """Generates mock test data for various data types."""
    
    @staticmethod
    def generate_user_data(count: int = 1) -> List[Dict[str, Any]]:
        """Generate mock user data."""
        users = []
        for i in range(count):
            user = {
                "id": f"user_{i:04d}",
                "username": f"user_{random.randint(1000, 9999)}",
                "email": f"user{i}@example.com",
                "first_name": random.choice(["John", "Jane", "Bob", "Alice", "Charlie"]),
                "last_name": random.choice(["Smith", "Johnson", "Williams", "Brown", "Jones"]),
                "age": random.randint(18, 80),
                "role": random.choice(["admin", "user", "moderator"]),
                "is_active": random.choice([True, False]),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "preferences": {
                    "theme": random.choice(["light", "dark"]),
                    "notifications": random.choice([True, False]),
                    "language": random.choice(["en", "es", "fr"])
                }
            }
            users.append(user)
        return users
    
    @staticmethod
    def generate_product_data(count: int = 1) -> List[Dict[str, Any]]:
        """Generate mock product data."""
        products = []
        categories = ["electronics", "clothing", "books", "home", "sports"]
        
        for i in range(count):
            product = {
                "id": f"prod_{i:04d}",
                "name": f"Product {i}",
                "description": f"Description for product {i}",
                "category": random.choice(categories),
                "price": round(random.uniform(10.0, 500.0), 2),
                "currency": "USD",
                "stock_quantity": random.randint(0, 100),
                "is_available": random.choice([True, False]),
                "rating": round(random.uniform(1.0, 5.0), 1),
                "reviews_count": random.randint(0, 1000),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "specifications": {
                    "weight": f"{random.uniform(0.1, 10.0):.1f}kg",
                    "dimensions": f"{random.randint(10, 50)}x{random.randint(10, 50)}x{random.randint(5, 30)}cm",
                    "color": random.choice(["red", "blue", "green", "black", "white"])
                }
            }
            products.append(product)
        return products
    
    @staticmethod
    def generate_order_data(count: int = 1) -> List[Dict[str, Any]]:
        """Generate mock order data."""
        orders = []
        statuses = ["pending", "processing", "shipped", "delivered", "cancelled"]
        
        for i in range(count):
            order = {
                "id": f"order_{i:04d}",
                "user_id": f"user_{random.randint(1, 100):04d}",
                "status": random.choice(statuses),
                "total_amount": round(random.uniform(20.0, 1000.0), 2),
                "currency": "USD",
                "items_count": random.randint(1, 10),
                "shipping_address": {
                    "street": f"{random.randint(100, 9999)} Main St",
                    "city": random.choice(["New York", "Los Angeles", "Chicago", "Houston"]),
                    "state": random.choice(["NY", "CA", "IL", "TX"]),
                    "zip_code": f"{random.randint(10000, 99999)}"
                },
                "payment_method": random.choice(["credit_card", "paypal", "bank_transfer"]),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "estimated_delivery": datetime.now(timezone.utc).isoformat()
            }
            orders.append(order)
        return orders


class TestDataResourceProvider:
    """
    Provides test data, fixtures, and validation datasets as MCP resources.
    
    This class manages various types of test data and exposes them through
    MCP resource URIs for AI tools to access structured test data.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._datasets: Dict[str, TestDataset] = {}
        self._fixtures: Dict[str, TestFixture] = {}
        self._validation_sets: Dict[str, ValidationSet] = {}
        self._mock_generator = MockDataGenerator()
        self._cache_timeout = 600  # 10 minutes
        self._last_cache_update = {}
        
        # Initialize with sample data
        asyncio.create_task(self._initialize_sample_data())
    
    async def _initialize_sample_data(self):
        """Initialize sample test data."""
        try:
            # Create sample user dataset
            user_items = []
            for i in range(5):
                item = TestDataItem(
                    id=f"user_item_{i}",
                    name=f"User Test Data {i}",
                    data_type="user",
                    category="valid" if i < 3 else "invalid",
                    priority=1,
                    tags=["authentication", "user_management"],
                    values={
                        "username": f"testuser{i}",
                        "email": f"test{i}@example.com",
                        "password": "TestPass123!",
                        "role": "user"
                    },
                    validation_rules=["email_format", "password_strength", "username_unique"],
                    expected_outcomes={"login_success": i < 3, "validation_pass": i < 3},
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    metadata={"test_purpose": "authentication_testing"}
                )
                user_items.append(item)
            
            user_dataset = TestDataset(
                name="user_authentication",
                description="User authentication test dataset",
                version="1.0.0",
                format="json",
                total_records=len(user_items),
                categories={"valid": 3, "invalid": 2},
                tags=["authentication", "user_management", "security"],
                items=user_items,
                schema={
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "minLength": 3},
                        "email": {"type": "string", "format": "email"},
                        "password": {"type": "string", "minLength": 8},
                        "role": {"type": "string", "enum": ["admin", "user", "moderator"]}
                    },
                    "required": ["username", "email", "password"]
                },
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            self._datasets["user_authentication"] = user_dataset
            
            # Create sample fixture
            login_fixture = TestFixture(
                name="user_login",
                description="User login test fixture",
                fixture_type="api",
                scope="function",
                setup_data={
                    "create_user": {
                        "username": "testuser",
                        "email": "test@example.com",
                        "password": "TestPass123!"
                    },
                    "login_endpoint": "/api/auth/login"
                },
                teardown_data={
                    "cleanup_user": True,
                    "clear_sessions": True
                },
                dependencies=["database_connection"],
                parameters={
                    "timeout": 30,
                    "retry_count": 3
                },
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            self._fixtures["user_login"] = login_fixture
            
            # Create sample validation set
            validation_set = ValidationSet(
                name="email_validation",
                description="Email format validation test cases",
                validation_type="format",
                test_cases=[
                    {"input": "test@example.com", "expected": True},
                    {"input": "invalid-email", "expected": False},
                    {"input": "@example.com", "expected": False},
                    {"input": "test@", "expected": False}
                ],
                expected_results=[
                    {"case": 0, "result": "valid"},
                    {"case": 1, "result": "invalid"},
                    {"case": 2, "result": "invalid"},
                    {"case": 3, "result": "invalid"}
                ],
                schema_rules={
                    "email": {
                        "type": "string",
                        "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                    }
                },
                business_rules=["email_must_be_unique", "email_required_for_registration"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            self._validation_sets["email_validation"] = validation_set
            
            logger.info("Initialized sample test data",
                       datasets=len(self._datasets),
                       fixtures=len(self._fixtures),
                       validation_sets=len(self._validation_sets))
            
        except Exception as e:
            logger.error("Failed to initialize sample test data", error=str(e), exc_info=True)
    
    async def _get_dataset(self, dataset_name: str) -> Optional[TestDataset]:
        """Get test dataset by name."""
        try:
            if dataset_name in self._datasets:
                return self._datasets[dataset_name]
            
            # Try to load from file if not in memory
            data_file = Path(f"test_data/{dataset_name}.json")
            if data_file.exists():
                with open(data_file, 'r') as f:
                    data = json.load(f)
                    dataset = TestDataset(**data)
                    self._datasets[dataset_name] = dataset
                    return dataset
            
            logger.warning("Dataset not found", dataset_name=dataset_name)
            return None
            
        except Exception as e:
            logger.error("Failed to get dataset", dataset_name=dataset_name, error=str(e), exc_info=True)
            return None
    
    async def _get_fixture(self, fixture_name: str) -> Optional[TestFixture]:
        """Get test fixture by name."""
        try:
            if fixture_name in self._fixtures:
                return self._fixtures[fixture_name]
            
            logger.warning("Fixture not found", fixture_name=fixture_name)
            return None
            
        except Exception as e:
            logger.error("Failed to get fixture", fixture_name=fixture_name, error=str(e), exc_info=True)
            return None
    
    async def _get_validation_set(self, validation_set: str) -> Optional[ValidationSet]:
        """Get validation set by name."""
        try:
            if validation_set in self._validation_sets:
                return self._validation_sets[validation_set]
            
            logger.warning("Validation set not found", validation_set=validation_set)
            return None
            
        except Exception as e:
            logger.error("Failed to get validation set", validation_set=validation_set, error=str(e), exc_info=True)
            return None
    
    async def _generate_mock_data(self, data_type: str, count: int = 10) -> List[Dict[str, Any]]:
        """Generate mock data of specified type."""
        try:
            if data_type == "user":
                return self._mock_generator.generate_user_data(count)
            elif data_type == "product":
                return self._mock_generator.generate_product_data(count)
            elif data_type == "order":
                return self._mock_generator.generate_order_data(count)
            else:
                logger.warning("Unknown mock data type", data_type=data_type)
                return []
                
        except Exception as e:
            logger.error("Failed to generate mock data", data_type=data_type, error=str(e), exc_info=True)
            return []
    
    async def _filter_dataset(self, dataset_name: str, filter_criteria: str) -> List[TestDataItem]:
        """Filter dataset based on criteria."""
        try:
            dataset = await self._get_dataset(dataset_name)
            if not dataset:
                return []
            
            # Parse filter criteria (simple implementation)
            # Format: category=valid or tag=authentication or priority=1
            filtered_items = []
            
            for item in dataset.items:
                include_item = True
                
                # Simple filter parsing
                if "category=" in filter_criteria:
                    category = filter_criteria.split("category=")[1].split("&")[0]
                    if item.category != category:
                        include_item = False
                
                if "tag=" in filter_criteria:
                    tag = filter_criteria.split("tag=")[1].split("&")[0]
                    if tag not in item.tags:
                        include_item = False
                
                if "priority=" in filter_criteria:
                    priority = int(filter_criteria.split("priority=")[1].split("&")[0])
                    if item.priority != priority:
                        include_item = False
                
                if include_item:
                    filtered_items.append(item)
            
            logger.info("Filtered dataset",
                       dataset_name=dataset_name,
                       filter_criteria=filter_criteria,
                       original_count=len(dataset.items),
                       filtered_count=len(filtered_items))
            
            return filtered_items
            
        except Exception as e:
            logger.error("Failed to filter dataset",
                        dataset_name=dataset_name,
                        filter_criteria=filter_criteria,
                        error=str(e), exc_info=True)
            return []


# MCP Resource Registration Functions
@mcp_server.resource("testdata://dataset/{dataset_name}")
async def get_test_dataset_resource(dataset_name: str) -> str:
    """
    Get complete test dataset.
    
    Args:
        dataset_name: Name of the test dataset
        
    Returns:
        JSON string containing the complete dataset
    """
    try:
        provider = TestDataResourceProvider()
        dataset = await provider._get_dataset(dataset_name)
        
        if dataset:
            logger.info("Retrieved test dataset resource",
                       dataset_name=dataset_name,
                       total_records=dataset.total_records,
                       format=dataset.format)
            
            return dataset.model_dump_json(indent=2)
        else:
            return json.dumps({"error": "Dataset not found"}, indent=2)
            
    except Exception as e:
        logger.error("Failed to get test dataset resource",
                    dataset_name=dataset_name, error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("testdata://fixture/{fixture_name}")
async def get_test_fixture_resource(fixture_name: str) -> str:
    """
    Get test fixture.
    
    Args:
        fixture_name: Name of the test fixture
        
    Returns:
        JSON string containing the fixture
    """
    try:
        provider = TestDataResourceProvider()
        fixture = await provider._get_fixture(fixture_name)
        
        if fixture:
            logger.info("Retrieved test fixture resource",
                       fixture_name=fixture_name,
                       fixture_type=fixture.fixture_type,
                       scope=fixture.scope)
            
            return fixture.model_dump_json(indent=2)
        else:
            return json.dumps({"error": "Fixture not found"}, indent=2)
            
    except Exception as e:
        logger.error("Failed to get test fixture resource",
                    fixture_name=fixture_name, error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("testdata://validation/{validation_set}")
async def get_validation_set_resource(validation_set: str) -> str:
    """
    Get validation dataset.
    
    Args:
        validation_set: Name of the validation set
        
    Returns:
        JSON string containing the validation set
    """
    try:
        provider = TestDataResourceProvider()
        validation = await provider._get_validation_set(validation_set)
        
        if validation:
            logger.info("Retrieved validation set resource",
                       validation_set=validation_set,
                       validation_type=validation.validation_type,
                       test_cases_count=len(validation.test_cases))
            
            return validation.model_dump_json(indent=2)
        else:
            return json.dumps({"error": "Validation set not found"}, indent=2)
            
    except Exception as e:
        logger.error("Failed to get validation set resource",
                    validation_set=validation_set, error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("testdata://mock/{data_type}")
async def get_mock_data_resource(data_type: str) -> str:
    """
    Get generated mock data.
    
    Args:
        data_type: Type of mock data to generate (user, product, order)
        
    Returns:
        JSON string containing generated mock data
    """
    try:
        provider = TestDataResourceProvider()
        mock_data = await provider._generate_mock_data(data_type, count=10)
        
        logger.info("Generated mock data resource",
                   data_type=data_type,
                   count=len(mock_data))
        
        return json.dumps({
            "data_type": data_type,
            "count": len(mock_data),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "items": mock_data
        }, indent=2)
        
    except Exception as e:
        logger.error("Failed to generate mock data resource",
                    data_type=data_type, error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


@mcp_server.resource("testdata://filter/{dataset_name}/{filter_criteria}")
async def get_filtered_dataset_resource(dataset_name: str, filter_criteria: str) -> str:
    """
    Get filtered test dataset.
    
    Args:
        dataset_name: Name of the test dataset
        filter_criteria: Filter criteria (e.g., category=valid&tag=authentication)
        
    Returns:
        JSON string containing filtered dataset
    """
    try:
        provider = TestDataResourceProvider()
        filtered_items = await provider._filter_dataset(dataset_name, filter_criteria)
        
        logger.info("Retrieved filtered dataset resource",
                   dataset_name=dataset_name,
                   filter_criteria=filter_criteria,
                   filtered_count=len(filtered_items))
        
        return json.dumps({
            "dataset_name": dataset_name,
            "filter_criteria": filter_criteria,
            "filtered_count": len(filtered_items),
            "items": [item.model_dump() for item in filtered_items]
        }, indent=2)
        
    except Exception as e:
        logger.error("Failed to get filtered dataset resource",
                    dataset_name=dataset_name,
                    filter_criteria=filter_criteria,
                    error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2) 