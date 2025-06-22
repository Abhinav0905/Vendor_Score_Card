import asyncio
import os
import json
from datetime import datetime, timedelta
from email_agent.services.gmail_service import GmailService
from email_agent.agents.orchestrator import EmailProcessingOrchestrator

class RealIntegrationTester:
    """Test with real Gmail integration"""
    
    def __init__(self):
        self.gmail_service = GmailService()
        self.orchestrator = EmailProcessingOrchestrator()
        
    async def test_real_gmail_connection(self):
        """Test actual Gmail API connection"""
        print("📧 Testing Gmail API Connection")
        print("-" * 30)
        
        try:
            # Test Gmail connection
            labels = await self.gmail_service.get_labels()
            print(f"✅ Connected to Gmail successfully")
            print(f"   Available labels: {len(labels)}")
            
            # Check for EPCIS error label
            epcis_labels = [label for label in labels if 'EPCIS' in label.get('name', '').upper()]
            if epcis_labels:
                print(f"   📂 Found EPCIS-related labels: {[l['name'] for l in epcis_labels]}")
            else:
                print("   ⚠️  No EPCIS-related labels found")
                
            return True
            
        except Exception as e:
            print(f"❌ Gmail connection failed: {str(e)}")
            return False
    
    async def test_email_monitoring(self, label_name="EPCIS_ERRORS", max_emails=5):
        """Test monitoring for EPCIS error emails"""
        print(f"👀 Testing Email Monitoring (Label: {label_name})")
        print("-" * 40)
        
        try:
            # Get recent emails from the specified label
            emails = await self.gmail_service.get_emails_by_label(label_name, max_emails)
            
            print(f"📨 Found {len(emails)} emails in '{label_name}' label")
            
            if emails:
                for i, email in enumerate(emails[:3], 1):
                    print(f"   Email {i}:")
                    print(f"      Subject: {email.get('subject', 'N/A')[:50]}...")
                    print(f"      From: {email.get('from', 'N/A')}")
                    print(f"      Date: {email.get('date', 'N/A')}")
                    
                # Process the first email through the orchestrator
                if emails:
                    print(f"\n🔄 Processing first email through orchestrator...")
                    result = await self.orchestrator.process_email(emails[0])
                    print(f"   ✅ Processing result: {result}")
            else:
                print("   📭 No emails found in the specified label")
                print("   💡 Try creating a test email with EPCIS errors")
                
            return len(emails) > 0
            
        except Exception as e:
            print(f"❌ Email monitoring failed: {str(e)}")
            return False
    
    async def create_test_email(self):
        """Create a test email for testing purposes"""
        print("📝 Creating Test Email")
        print("-" * 20)
        
        test_email_content = {
            'to': 'your-email@gmail.com',  # Replace with your email
            'subject': 'TEST: EPCIS Validation Error - PO-TEST-001',
            'body': """
This is a test email for the EPCIS Error Correction Agent.

ERROR DETAILS:
- Purchase Order: PO-TEST-001
- LOT Number: LOT-TEST-12345
- Vendor: Test Pharmaceuticals Inc.
- File: EPCIS_TEST_20240615.xml

VALIDATION ERRORS:
1. Missing required field 'bizStep' in ObjectEvent
2. Invalid EPC format in line 123
3. Sequence violation: Item not commissioned before aggregation

Please ignore this test email.
            """
        }
        
        try:
            # Send test email to yourself
            result = await self.gmail_service.send_email(test_email_content)
            print(f"✅ Test email sent successfully")
            print(f"   Message ID: {result.get('id', 'N/A')}")
            
            # Add label to the sent email
            await asyncio.sleep(2)  # Wait for email to be processed
            print("🏷️  Adding EPCIS_ERRORS label to test email...")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to create test email: {str(e)}")
            return False
    
    async def run_integration_test(self):
        """Run complete integration test"""
        print("🔄 REAL INTEGRATION TEST")
        print("=" * 30)
        print()
        
        # Step 1: Test Gmail connection
        gmail_ok = await self.test_real_gmail_connection()
        if not gmail_ok:
            return False
        
        print()
        
        # Step 2: Create test email (optional)
        create_test = input("Create a test email? (y/n): ").lower().strip() == 'y'
        if create_test:
            await self.create_test_email()
            print()
        
        # Step 3: Monitor emails
        monitoring_ok = await self.test_email_monitoring()
        
        return gmail_ok and monitoring_ok

async def main():
    """Run the integration test"""
    tester = RealIntegrationTester()
    
    print("🚀 Starting Real Integration Test")
    print("This will test the agent with actual Gmail API")
    print()
    
    # Check if credentials are available
    if not os.path.exists('config/gmail_credentials.json'):
        print("❌ Gmail credentials not found!")
        print("   Please set up Gmail API credentials first")
        print("   See README.md for setup instructions")
        return
    
    success = await tester.run_integration_test()
    
    if success:
        print("\n🎉 Integration test completed successfully!")
    else:
        print("\n❌ Integration test failed!")

if __name__ == "__main__":
    asyncio.run(main())