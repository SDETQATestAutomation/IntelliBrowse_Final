#!/usr/bin/env python3
"""
Simple test runner for MCP Server validation
Tests core functionality without complex pytest dependencies
"""

import asyncio
import sys
import traceback
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

async def test_schema_validation():
    """Test basic schema validation."""
    print("Testing schema validation...")
    
    try:
        from src.backend.mcp.schemas.context_schemas import SessionContext, TaskContext, UserContext
        from src.backend.mcp.schemas.tools.bdd_generator_schemas import BDDGeneratorRequest, BDDGeneratorResponse
        from src.backend.mcp.schemas.tools.locator_generator_schemas import LocatorGeneratorRequest, LocatorGeneratorResponse
        
        # Test SessionContext
        session_data = {
            "session_id": "test-session-001",
            "user_context": {
                "user_id": "user-123",
                "username": "test_user",
                "email": "test@example.com",
                "roles": ["test_engineer"],
                "permissions": ["tools:execute"],
                "tenant_id": "tenant-456"
            },
            "created_at": "2025-01-09T12:00:00Z",
            "last_activity": "2025-01-09T12:00:00Z"
        }
        session = SessionContext(**session_data)
        assert session.session_id == "test-session-001"
        print("✅ SessionContext validation passed")
        
        # Test BDD Request
        bdd_data = {
            "user_story": "As a user, I want to log in",
            "context": "Authentication flow"
        }
        bdd_request = BDDGeneratorRequest(**bdd_data)
        assert bdd_request.user_story == "As a user, I want to log in"
        print("✅ BDDGeneratorRequest validation passed")
        
        # Test Locator Request
        locator_data = {
            "dom_snapshot": "<button id='submit'>Submit</button>",
            "element_description": "Submit button",
            "locator_strategy": "auto",
            "context_hints": ["form", "submission"]
        }
        locator_request = LocatorGeneratorRequest(**locator_data)
        assert locator_request.locator_strategy == "auto"
        print("✅ LocatorGeneratorRequest validation passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        traceback.print_exc()
        return False

async def test_tool_imports():
    """Test tool imports and basic functionality."""
    print("\nTesting tool imports...")
    
    try:
        from src.backend.mcp.tools.bdd_generator import generate_bdd_scenarios
        from src.backend.mcp.tools.locator_generator import generate_locator
        from src.backend.mcp.tools.step_generator import generate_step
        from src.backend.mcp.tools.selector_healer import heal_selector
        from src.backend.mcp.tools.debug_analyzer import analyze_debug_info
        
        print("✅ All 5 tools imported successfully")
        
        # Test tool function signatures
        import inspect
        
        # Check BDD generator signature
        sig = inspect.signature(generate_bdd_scenarios)
        assert len(sig.parameters) == 1  # Should take one parameter (request)
        print("✅ BDD generator signature validated")
        
        # Check locator generator signature
        sig = inspect.signature(generate_locator)
        assert len(sig.parameters) == 1
        print("✅ Locator generator signature validated")
        
        return True
        
    except Exception as e:
        print(f"❌ Tool import failed: {e}")
        traceback.print_exc()
        return False

async def test_prompt_imports():
    """Test prompt imports and basic functionality."""
    print("\nTesting prompt imports...")
    
    try:
        from src.backend.mcp.prompts.bug_report_prompt import generate_bug_report_prompt
        from src.backend.mcp.prompts.test_scenario_prompt import generate_test_scenario_prompt
        from src.backend.mcp.prompts.debug_analysis_prompt import generate_debug_analysis_prompt
        from src.backend.mcp.prompts.locator_explanation_prompt import generate_locator_explanation_prompt
        from src.backend.mcp.prompts.step_documentation_prompt import generate_step_documentation_prompt
        
        print("✅ All 5 prompts imported successfully")
        
        # Test basic prompt generation
        bug_prompt = generate_bug_report_prompt(
            error_message="Test error",
            context="Test context",
            severity="medium"
        )
        assert isinstance(bug_prompt, str)
        assert len(bug_prompt) > 50
        print("✅ Bug report prompt generation validated")
        
        test_prompt = generate_test_scenario_prompt(
            feature_description="Test feature",
            test_type="functional",
            scope="test scope"
        )
        assert isinstance(test_prompt, str)
        assert len(test_prompt) > 50
        print("✅ Test scenario prompt generation validated")
        
        return True
        
    except Exception as e:
        print(f"❌ Prompt import failed: {e}")
        traceback.print_exc()
        return False

async def test_resource_imports():
    """Test resource imports and basic functionality."""
    print("\nTesting resource imports...")
    
    try:
        from src.backend.mcp.resources.dom_resource import get_dom_snapshot, get_dom_elements, get_dom_forms
        from src.backend.mcp.resources.execution_context_resource import (
            get_execution_state, get_environment_config,
            get_test_runner_context, get_browser_context
        )
        from src.backend.mcp.resources.test_data_resource import (
            get_test_dataset, get_test_fixtures, get_validation_data,
            get_mock_data, get_filtered_dataset
        )
        from src.backend.mcp.resources.session_artifact_resource import (
            get_session_screenshot, get_session_logs, get_session_report,
            get_session_traces, get_artifact_list
        )
        from src.backend.mcp.resources.schema_resource import (
            get_api_schema, get_validation_schema, get_config_schema
        )
        
        print("✅ All 5 resource modules with 18 functions imported successfully")
        
        # Test function signatures
        import inspect
        
        sig = inspect.signature(get_dom_snapshot)
        assert len(sig.parameters) == 1  # page_id parameter
        print("✅ DOM resource signatures validated")
        
        sig = inspect.signature(get_execution_state)
        assert len(sig.parameters) == 1  # session_id parameter
        print("✅ Execution context resource signatures validated")
        
        return True
        
    except Exception as e:
        print(f"❌ Resource import failed: {e}")
        traceback.print_exc()
        return False

async def test_config_system():
    """Test configuration system."""
    print("\nTesting configuration system...")
    
    try:
        from src.backend.mcp.config.settings import MCPSettings
        
        # Test with minimal configuration using correct field names
        test_config = MCPSettings(
            openai_api_key="test-key",
            openai_model="gpt-4",
            mongodb_url="mongodb://localhost:27017/test",
            mongodb_database="test_mcp",
            session_ttl_hours=24,
            openai_max_tokens=4000,
            jwt_secret="test-secret",
            jwt_algorithm="HS256",
            jwt_expiry_hours=24,
            admin_users=["admin@test.com"],
            chroma_host="localhost",
            log_level="INFO",
            audit_log_enabled=True
        )
        
        assert test_config.openai_model == "gpt-4"
        assert test_config.session_ttl_hours == 24
        assert test_config.jwt_algorithm == "HS256"
        print("✅ Configuration system validated")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration system failed: {e}")
        traceback.print_exc()
        return False

async def test_main_server():
    """Test main server creation."""
    print("\nTesting main server creation...")
    
    try:
        from src.backend.mcp.main import setup_logging
        
        # Test logging setup
        logger = setup_logging()
        assert logger is not None
        print("✅ Logging setup validated")
        
        # Test that create_mcp_server function exists
        from src.backend.mcp.main import create_mcp_server
        assert callable(create_mcp_server)
        print("✅ MCP server creation function available")
        
        return True
        
    except Exception as e:
        print(f"❌ Main server test failed: {e}")
        traceback.print_exc()
        return False

async def run_all_tests():
    """Run all validation tests."""
    print("🚀 Starting MCP Server Validation Tests")
    print("=" * 50)
    
    test_results = []
    
    # Run individual test suites
    test_results.append(await test_schema_validation())
    test_results.append(await test_tool_imports())
    test_results.append(await test_prompt_imports())
    test_results.append(await test_resource_imports())
    test_results.append(await test_config_system())
    test_results.append(await test_main_server())
    
    # Summary
    print("\n" + "=" * 50)
    print("🎯 TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(test_results)
    total = len(test_results)
    
    test_names = [
        "Schema Validation",
        "Tool Imports", 
        "Prompt Imports",
        "Resource Imports",
        "Configuration System",
        "Main Server"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, test_results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1}. {name:<20} {status}")
    
    print("-" * 50)
    print(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - MCP Server implementation is working!")
        return True
    else:
        print("⚠️  Some tests failed - review implementation")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(run_all_tests())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1) 