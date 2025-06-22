#!/usr/bin/env python3
"""Test script to verify all imports work correctly"""

def test_imports():
    """Test that all imports work"""
    print("Testing imports...")
    
    try:
        # Test models import
        from email_agent.models import ExtractedData, EmailData, ValidationError, ActionPlan, AgentState
        print("✅ Models imported successfully")
        
        # Test config import  
        from email_agent.config import settings, Settings
        print("✅ Config imported successfully")
        
        # Test services import
        from email_agent.services import GmailService, DatabaseService
        print("✅ Services imported successfully")
        
        # Test agent imports
        from email_agent.agents.email_processor import EmailProcessorAgent
        from email_agent.agents.epcis_analyzer import EPCISAnalyzerAgent
        from email_agent.agents.vendor_communicator import VendorCommunicatorAgent
        from email_agent.agents.orchestrator import EmailProcessingOrchestrator
        print("✅ Agents imported successfully")
        
        print("\n🎉 All imports working correctly!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    exit(0 if success else 1)