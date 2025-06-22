import asyncio
import json
import os
from datetime import datetime
from email_agent.agents.orchestrator import EmailProcessingOrchestrator
from email_agent.config.settings import settings

class EndToEndTester:
    """Test the complete email agent workflow"""
    
    def __init__(self):
        self.orchestrator = EmailProcessingOrchestrator()
        
    async def test_complete_workflow(self):
        """Test the complete workflow with sample data"""
        print("🚀 Starting End-to-End Email Agent Test")
        print("=" * 50)
        
        # Step 1: Simulate receiving an email
        sample_email = self.create_sample_error_email()
        print(f"📧 Step 1: Simulated email received")
        print(f"   Subject: {sample_email['subject']}")
        print(f"   From: {sample_email['from']}")
        print()
        
        # Step 2: Process the email through the orchestrator
        print("🔄 Step 2: Processing email through orchestrator...")
        try:
            result = await self.orchestrator.process_email(sample_email)
            print(f"   ✅ Email processed successfully")
            print(f"   Result: {result}")
        except Exception as e:
            print(f"   ❌ Error processing email: {str(e)}")
            return False
        
        print()
        return True
    
    def create_sample_error_email(self):
        """Create a sample EPCIS error email for testing"""
        return {
            'id': 'test_email_001',
            'subject': 'EPCIS Validation Error - Action Required',
            'from': 'epcis-system@company.com',
            'to': 'vendor-support@mycompany.com',
            'date': datetime.now().isoformat(),
            'body': """
Dear Vendor Support Team,

We have identified validation errors in your recent EPCIS submission that require immediate attention.

ERROR DETAILS:
- File: EPCIS_ABC_PHARMA_20240615.xml
- Purchase Order: PO-2024-7890
- LOT Number: LOT-ABC-12345
- Submission Date: 2024-06-15 14:30:00

VALIDATION ERRORS FOUND:
1. Missing required field 'bizStep' in ObjectEvent at line 145
2. Invalid EPC format in AggregationEvent at line 267
3. Sequence violation: Item not commissioned before packing event
4. Missing business transaction reference for shipping event

Please correct these errors and resubmit the EPCIS file within 24 hours.

If you need assistance, please contact our support team.

Best regards,
EPCIS Validation System
            """,
            'attachments': []
        }

async def main():
    """Run the end-to-end test"""
    tester = EndToEndTester()
    success = await tester.test_complete_workflow()
    
    if success:
        print("🎉 End-to-end test completed successfully!")
    else:
        print("❌ End-to-end test failed!")

if __name__ == "__main__":
    asyncio.run(main())