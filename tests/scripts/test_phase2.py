#!/usr/bin/env python3
"""
Test script to verify Phase 2 Multi-Test Type System implementation.
Tests the integration of multi-test type support into existing test item infrastructure.
"""

import sys
import os
import asyncio
from datetime import datetime
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from backend.testtypes import TestType, TestTypeValidatorFactory
from backend.testitems.models.test_item_model import (
    TestItemModel, TestItemSteps, TestItemSelectors, 
    TestItemMetadata, TestItemAudit, StepType, CreatedSource
)
from backend.testitems.schemas.test_item_schemas import CreateTestItemRequest, CreateTestItemStepsRequest, CreateTestItemSelectorsRequest


def test_bdd_type_data_validation():
    """Test BDD type data validation using TestTypeValidatorFactory."""
    print("🧪 Testing BDD type data validation...")
    
    bdd_data = {
        "feature_name": "User Authentication",
        "scenario_name": "Successful login",
        "bdd_blocks": [
            {"type": "Given", "content": "I am on the login page", "keyword": "Given"},
            {"type": "When", "content": "I enter valid credentials", "keyword": "When"},
            {"type": "Then", "content": "I should be logged in successfully", "keyword": "Then"}
        ]
    }
    
    try:
        validated_data = TestTypeValidatorFactory.validate_type_data(TestType.BDD, bdd_data)
        print(f"✅ BDD validation successful: {len(validated_data['bdd_blocks'])} blocks validated")
        return True
    except Exception as e:
        print(f"❌ BDD validation failed: {e}")
        return False


def test_test_item_model_with_type_data():
    """Test TestItemModel with multi-test type support."""
    print("🧪 Testing TestItemModel with type data...")
    
    # Create test item with BDD type data
    steps = TestItemSteps(
        type=StepType.GHERKIN,
        content=["Given I am on login page", "When I enter credentials", "Then I should be logged in"],
        step_count=3
    )
    
    selectors = TestItemSelectors(
        primary={"login_form": "#login-form", "submit_btn": "button[type='submit']"},
        reliability_score=0.9
    )
    
    metadata = TestItemMetadata(
        tags=["authentication", "login"],
        auto_healing_enabled=True
    )
    
    audit = TestItemAudit(
        created_by_user_id="test_user_123",
        created_at=datetime.utcnow(),
        created_source=CreatedSource.MANUAL
    )
    
    bdd_type_data = {
        "feature_name": "User Authentication",
        "scenario_name": "Successful login",
        "bdd_blocks": [
            {"type": "Given", "content": "I am on the login page", "keyword": "Given"},
            {"type": "When", "content": "I enter valid credentials", "keyword": "When"},
            {"type": "Then", "content": "I should be logged in successfully", "keyword": "Then"}
        ]
    }
    
    try:
        test_item = TestItemModel(
            title="BDD Login Test",
            feature_id="auth_feature",
            scenario_id="login_scenario",
            steps=steps,
            selectors=selectors,
            metadata=metadata,
            audit=audit,
            test_type=TestType.BDD,
            type_data=bdd_type_data
        )
        
        # Test type data validation
        validated_data = test_item.validate_type_data()
        print(f"✅ TestItemModel created with validated type data: {len(validated_data)} fields")
        
        # Test typed data conversion
        typed_data = test_item.get_typed_data()
        print(f"✅ Typed data conversion successful: {type(typed_data).__name__}")
        
        # Test MongoDB conversion
        mongo_doc = test_item.to_mongo()
        print(f"✅ MongoDB document conversion successful: {len(mongo_doc)} fields")
        
        # Test API response conversion
        api_dict = test_item.to_dict()
        print(f"✅ API response conversion successful: test_type = {api_dict['test_type']}")
        
        return True
        
    except Exception as e:
        print(f"❌ TestItemModel test failed: {e}")
        return False


def test_create_request_schema_validation():
    """Test CreateTestItemRequest schema with type validation."""
    print("🧪 Testing CreateTestItemRequest schema validation...")
    
    request_data = {
        "title": "BDD Authentication Test",
        "feature_id": "auth_feature",
        "scenario_id": "login_scenario",
        "steps": {
            "type": "gherkin",
            "content": ["Given I am on login page", "When I enter credentials", "Then I should be logged in"]
        },
        "selectors": {
            "primary": {"login_form": "#login-form"}
        },
        "test_type": "bdd",
        "type_data": {
            "feature_name": "User Authentication",
            "scenario_name": "Successful login",
            "bdd_blocks": [
                {"type": "Given", "content": "I am on the login page", "keyword": "Given"},
                {"type": "When", "content": "I enter valid credentials", "keyword": "When"},
                {"type": "Then", "content": "I should be logged in successfully", "keyword": "Then"}
            ]
        }
    }
    
    try:
        request = CreateTestItemRequest(**request_data)
        print(f"✅ CreateTestItemRequest validation successful: {request.test_type}")
        print(f"✅ Type data included: {len(request.type_data)} fields")
        return True
    except Exception as e:
        print(f"❌ CreateTestItemRequest validation failed: {e}")
        return False


def main():
    """Run all Phase 2 integration tests."""
    print("🚀 Testing Multi-Test Type System Phase 2 Implementation")
    print("=" * 60)
    
    tests = [
        test_bdd_type_data_validation,
        test_test_item_model_with_type_data,
        test_create_request_schema_validation
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
            print()
    
    print("=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ Phase 2 Multi-Test Type System Integration: ALL TESTS PASSED")
        print("🎯 Ready for Phase 3 - Controller & API Integration")
    else:
        print("❌ Some tests failed - Phase 2 implementation needs fixes")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 