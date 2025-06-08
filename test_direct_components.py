#!/usr/bin/env python3
"""
Test script to verify orchestration components work by importing them directly.
"""

import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_direct_imports():
    """Test orchestration components by importing them directly."""
    try:
        # Test direct model imports
        from src.backend.orchestration.models.orchestration_models import (
            JobStatus, NodeType, RetryStrategy, RecoveryAction
        )
        print("✅ Models imported directly")
        
        # Test direct schema imports
        from src.backend.orchestration.schemas.orchestration_schemas import (
            CreateOrchestrationJobRequest,
            JobStatusResponse,
            OrchestrationResponse
        )
        print("✅ Schemas imported directly")
        
        # Test enum functionality
        statuses = [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED]
        print(f"✅ JobStatus enum: {[s.value for s in statuses]}")
        
        node_types = [NodeType.TEST_EXECUTION, NodeType.VALIDATION]
        print(f"✅ NodeType enum: {[nt.value for nt in node_types]}")
        
        # Test schema creation
        from bson import ObjectId
        request = CreateOrchestrationJobRequest(
            job_name="Direct Test Job",
            job_type="test_execution",
            test_case_ids=[str(ObjectId())]
        )
        print(f"✅ Schema creation: {request.job_name}")
        
        # Test response creation
        response = OrchestrationResponse(
            success=True,
            message="Direct test successful",
            data={"component": "orchestration"}
        )
        print(f"✅ Response creation: {response.success}")
        
        # Test controller import (without instantiation)
        from src.backend.orchestration.controllers.orchestration_controller import OrchestrationController
        print("✅ Controller class imported")
        
        print("\n🎉 All direct component imports successful!")
        print("✅ Phase 5 Integration Tests - Core Components Verified")
        return True
        
    except Exception as e:
        print(f"❌ Error with direct imports: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_direct_imports()
    sys.exit(0 if success else 1) 