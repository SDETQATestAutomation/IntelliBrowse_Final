"""
IntelliBrowse MCP Server - SSE Testing Suite

Comprehensive testing suite for the IntelliBrowse MCP Server SSE implementation.
Based on OpenAI Agents Python SDK testing patterns.
"""

import asyncio
import pytest
import logging
import time
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import httpx

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))

try:
    from client import IntelliBrowseMCPClient, IntelliBrowseMCPTestClient
except ImportError:
    # Fallback for when running directly from mcp directory
    from client import IntelliBrowseMCPClient, IntelliBrowseMCPTestClient
try:
    from config.settings import get_settings
except ImportError:
    # Fallback for when running directly from mcp directory
    from config.settings import get_settings

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SSEServerTestSuite:
    """
    Comprehensive test suite for SSE Server testing.
    
    Based on OpenAI testing patterns:
    - Server lifecycle testing
    - Tool invocation testing
    - Error handling testing
    - Performance testing
    - Connection management testing
    """
    
    def __init__(self, server_url: str = "http://127.0.0.1:8001"):
        self.server_url = server_url
        self.sse_url = f"{server_url}/sse"
        self.settings = get_settings()
        self.server_process: Optional[subprocess.Popen] = None
        
    async def run_full_test_suite(self):
        """Run the complete test suite."""
        logger.info("🧪 Starting IntelliBrowse MCP Server SSE Test Suite")
        logger.info("=" * 60)
        
        test_results = {}
        
        try:
            # Test 1: Server Health Check
            test_results["server_health"] = await self._test_server_health()
            
            # Test 2: Basic Connection Test
            test_results["basic_connection"] = await self._test_basic_connection()
            
            # Test 3: Tool Discovery Test
            test_results["tool_discovery"] = await self._test_tool_discovery()
            
            # Test 4: Tool Invocation Test
            test_results["tool_invocation"] = await self._test_tool_invocation()
            
            # Test 5: Error Handling Test
            test_results["error_handling"] = await self._test_error_handling()
            
            # Test 6: Session Management Test
            test_results["session_management"] = await self._test_session_management()
            
            # Test 7: Performance Test
            test_results["performance"] = await self._test_performance()
            
            # Generate test report
            self._generate_test_report(test_results)
            
        except Exception as e:
            logger.error(f"❌ Test suite failed: {e}")
            raise
            
        logger.info("✅ Test suite completed successfully")
        return test_results
        
    async def _test_server_health(self) -> Dict[str, Any]:
        """Test basic server health and availability."""
        logger.info("🔍 Testing server health...")
        
        try:
            async with httpx.AsyncClient() as client:
                # Try to connect to the base URL
                response = await client.get(self.server_url, timeout=5.0)
                
                health_status = {
                    "server_reachable": True,
                    "status_code": response.status_code,
                    "response_time_ms": 0  # Will be calculated
                }
                
        except Exception as e:
            logger.warning(f"Server health check failed: {e}")
            health_status = {
                "server_reachable": False,
                "error": str(e)
            }
            
        logger.info(f"✅ Server health test completed: {health_status}")
        return health_status
        
    async def _test_basic_connection(self) -> Dict[str, Any]:
        """Test basic MCP client connection."""
        logger.info("🔗 Testing basic MCP connection...")
        
        try:
            async with IntelliBrowseMCPClient(self.sse_url, timeout=10.0) as client:
                # Test connection establishment
                connected = client.session is not None
                
                # Test server info
                server_name = client.server_info.serverInfo.name if client.server_info else None
                
                connection_result = {
                    "connection_successful": connected,
                    "server_name": server_name,
                    "server_capabilities": client.server_info.capabilities.__dict__ if client.server_info else None
                }
                
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            connection_result = {
                "connection_successful": False,
                "error": str(e)
            }
            
        logger.info(f"✅ Connection test completed: {connection_result}")
        return connection_result
        
    async def _test_tool_discovery(self) -> Dict[str, Any]:
        """Test tool discovery and listing."""
        logger.info("🛠️ Testing tool discovery...")
        
        try:
            async with IntelliBrowseMCPClient(self.sse_url) as client:
                # List all available tools
                tools = await client.list_tools()
                
                tool_names = [tool.name for tool in tools]
                tool_count = len(tools)
                
                # Check for expected IntelliBrowse tools
                expected_tools = ["bdd_generator", "locator_generator", "step_generator"]
                found_expected = [tool for tool in expected_tools if tool in tool_names]
                
                discovery_result = {
                    "tools_discovered": tool_count,
                    "tool_names": tool_names,
                    "expected_tools_found": found_expected,
                    "discovery_successful": tool_count > 0
                }
                
        except Exception as e:
            logger.error(f"Tool discovery test failed: {e}")
            discovery_result = {
                "discovery_successful": False,
                "error": str(e)
            }
            
        logger.info(f"✅ Tool discovery test completed: {discovery_result}")
        return discovery_result
        
    async def _test_tool_invocation(self) -> Dict[str, Any]:
        """Test basic tool invocation."""
        logger.info("⚙️ Testing tool invocation...")
        
        invocation_results = []
        
        try:
            async with IntelliBrowseMCPClient(self.sse_url) as client:
                tools = await client.list_tools()
                
                # Test BDD Generator if available
                if any(tool.name == "bdd_generator" for tool in tools):
                    try:
                        result = await client.call_tool("bdd_generator", {
                            "user_story": "As a test user, I want to validate the system",
                            "acceptance_criteria": ["System should respond", "Response should be valid"]
                        })
                        
                        invocation_results.append({
                            "tool": "bdd_generator",
                            "success": True,
                            "result_length": len(str(result))
                        })
                        
                    except Exception as e:
                        invocation_results.append({
                            "tool": "bdd_generator",
                            "success": False,
                            "error": str(e)
                        })
                
                # Test Locator Generator if available
                if any(tool.name == "locator_generator" for tool in tools):
                    try:
                        result = await client.call_tool("locator_generator", {
                            "dom_content": "<button id='test-btn'>Test</button>",
                            "element_description": "test button"
                        })
                        
                        invocation_results.append({
                            "tool": "locator_generator",
                            "success": True,
                            "result_length": len(str(result))
                        })
                        
                    except Exception as e:
                        invocation_results.append({
                            "tool": "locator_generator", 
                            "success": False,
                            "error": str(e)
                        })
                        
        except Exception as e:
            logger.error(f"Tool invocation test failed: {e}")
            invocation_results = [{"error": str(e)}]
            
        successful_invocations = sum(1 for result in invocation_results if result.get("success", False))
        
        invocation_result = {
            "total_tests": len(invocation_results),
            "successful_invocations": successful_invocations,
            "invocation_details": invocation_results,
            "success_rate": successful_invocations / len(invocation_results) if invocation_results else 0
        }
        
        logger.info(f"✅ Tool invocation test completed: {invocation_result}")
        return invocation_result
        
    async def _test_error_handling(self) -> Dict[str, Any]:
        """Test error handling and recovery."""
        logger.info("🚨 Testing error handling...")
        
        error_tests = []
        
        try:
            async with IntelliBrowseMCPClient(self.sse_url) as client:
                # Test 1: Invalid tool name
                try:
                    await client.call_tool("nonexistent_tool", {})
                    error_tests.append({"test": "invalid_tool", "handled": False})
                except Exception:
                    error_tests.append({"test": "invalid_tool", "handled": True})
                
                # Test 2: Invalid arguments
                tools = await client.list_tools()
                if tools:
                    try:
                        await client.call_tool(tools[0].name, {"invalid": "arguments"})
                        error_tests.append({"test": "invalid_args", "handled": False})
                    except Exception:
                        error_tests.append({"test": "invalid_args", "handled": True})
                        
        except Exception as e:
            logger.error(f"Error handling test failed: {e}")
            error_tests = [{"error": str(e)}]
            
        handled_errors = sum(1 for test in error_tests if test.get("handled", False))
        
        error_result = {
            "total_error_tests": len(error_tests),
            "properly_handled": handled_errors,
            "error_details": error_tests,
            "error_handling_rate": handled_errors / len(error_tests) if error_tests else 0
        }
        
        logger.info(f"✅ Error handling test completed: {error_result}")
        return error_result
        
    async def _test_session_management(self) -> Dict[str, Any]:
        """Test session management and multiple connections."""
        logger.info("📡 Testing session management...")
        
        try:
            # Test multiple concurrent connections
            clients = []
            connection_results = []
            
            for i in range(3):
                try:
                    client = IntelliBrowseMCPClient(self.sse_url, name=f"TestClient-{i}")
                    await client.connect()
                    clients.append(client)
                    connection_results.append({"client": i, "connected": True})
                except Exception as e:
                    connection_results.append({"client": i, "connected": False, "error": str(e)})
            
            # Test concurrent tool calls
            if clients:
                concurrent_tasks = []
                for i, client in enumerate(clients):
                    task = asyncio.create_task(client.list_tools())
                    concurrent_tasks.append(task)
                
                results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
                successful_concurrent = sum(1 for result in results if not isinstance(result, Exception))
            else:
                successful_concurrent = 0
            
            # Cleanup
            for client in clients:
                try:
                    await client.disconnect()
                except Exception:
                    pass
                    
            session_result = {
                "concurrent_connections": len([r for r in connection_results if r.get("connected", False)]),
                "total_connection_attempts": len(connection_results),
                "concurrent_operations_successful": successful_concurrent,
                "connection_details": connection_results
            }
            
        except Exception as e:
            logger.error(f"Session management test failed: {e}")
            session_result = {"error": str(e)}
            
        logger.info(f"✅ Session management test completed: {session_result}")
        return session_result
        
    async def _test_performance(self) -> Dict[str, Any]:
        """Test basic performance metrics."""
        logger.info("⚡ Testing performance...")
        
        try:
            async with IntelliBrowseMCPClient(self.sse_url) as client:
                # Test connection time
                start_time = time.time()
                await client.list_tools()
                tool_list_time = time.time() - start_time
                
                # Test multiple sequential calls
                start_time = time.time()
                for _ in range(5):
                    await client.list_tools()
                sequential_time = time.time() - start_time
                
                performance_result = {
                    "tool_list_time_ms": round(tool_list_time * 1000, 2),
                    "sequential_calls_time_ms": round(sequential_time * 1000, 2),
                    "avg_call_time_ms": round((sequential_time / 5) * 1000, 2)
                }
                
        except Exception as e:
            logger.error(f"Performance test failed: {e}")
            performance_result = {"error": str(e)}
            
        logger.info(f"✅ Performance test completed: {performance_result}")
        return performance_result
        
    def _generate_test_report(self, test_results: Dict[str, Any]):
        """Generate a comprehensive test report."""
        logger.info("\n" + "=" * 60)
        logger.info("📊 IntelliBrowse MCP Server SSE Test Report")
        logger.info("=" * 60)
        
        for test_name, result in test_results.items():
            logger.info(f"\n🔸 {test_name.upper().replace('_', ' ')}:")
            if isinstance(result, dict):
                for key, value in result.items():
                    if key != "error":
                        logger.info(f"   {key}: {value}")
                if "error" in result:
                    logger.error(f"   ERROR: {result['error']}")
            else:
                logger.info(f"   Result: {result}")
                
        logger.info("\n" + "=" * 60)


async def run_quick_test():
    """Run a quick connectivity test."""
    logger.info("🚀 Running quick SSE server test...")
    
    try:
        test_client = IntelliBrowseMCPTestClient()
        await test_client.run_basic_tests()
        logger.info("✅ Quick test passed!")
        return True
    except Exception as e:
        logger.error(f"❌ Quick test failed: {e}")
        return False


async def run_comprehensive_test():
    """Run the comprehensive test suite."""
    logger.info("🧪 Running comprehensive SSE server test suite...")
    
    test_suite = SSEServerTestSuite()
    results = await test_suite.run_full_test_suite()
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="IntelliBrowse MCP Server SSE Tests")
    parser.add_argument("--quick", action="store_true", help="Run quick connectivity test")
    parser.add_argument("--comprehensive", action="store_true", help="Run comprehensive test suite")
    
    args = parser.parse_args()
    
    try:
        if args.quick:
            success = asyncio.run(run_quick_test())
            sys.exit(0 if success else 1)
        elif args.comprehensive:
            asyncio.run(run_comprehensive_test())
        else:
            # Default: run quick test
            success = asyncio.run(run_quick_test())
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1) 