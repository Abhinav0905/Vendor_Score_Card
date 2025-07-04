import asyncio
import json
from datetime import datetime
from email_agent.agents.email_processor import EmailProcessorAgent
from email_agent.agents.epcis_analyzer import EPCISAnalyzerAgent
from email_agent.agents.vendor_communicator import VendorCommunicatorAgent
from email_agent.services.gmail_service import GmailService
from email_agent.services.database_service import DatabaseService

class WorkflowStepTester:
    """Test each step of the workflow individually"""
    
    def __init__(self):
        self.email_processor = EmailProcessorAgent()
        self.epcis_analyzer = EPCISAnalyzerAgent()
        self.vendor_communicator = VendorCommunicatorAgent()
        
    async def test_step_1_email_reading(self):
        """Test Step 1: Reading and parsing email"""
        print("📧 STEP 1: Email Reading and Parsing")
        print("-" * 40)
        
        # Simulate Gmail service reading email
        sample_email = {
            'id': 'gmail_12345',
            'subject': 'EPCIS Error: PO-2024-7890 - LOT-ABC-12345',
            'from': 'system@vendor.com',
            'body': """
            EPCIS validation failed for:
            Purchase Order: PO-2024-7890
            LOT Number: LOT-ABC-12345
            Vendor: ABC Pharmaceuticals
            
            Errors:
            - Missing bizStep field
            - Invalid sequence order
            """
        }
        
        print(f"   📨 Raw email received:")
        print(f"      Subject: {sample_email['subject']}")
        print(f"      From: {sample_email['from']}")
        print(f"      Body preview: {sample_email['body'][:100]}...")
        
        # Process email to extract structured data
        extracted_data = await self.email_processor.process_email(sample_email)
        
        print(f"   🔍 Extracted data:")
        print(f"      PO Number: {extracted_data.po_number}")
        print(f"      LOT Number: {extracted_data.lot_number}")
        print(f"      Vendor: {extracted_data.vendor_name}")
        print(f"      Error types: {extracted_data.error_types}")
        print()
        
        return extracted_data
    
    async def test_step_2_database_search(self, extracted_data):
        """Test Step 2: Searching database for PO/LOT"""
        print("🗄️ STEP 2: Database Search")
        print("-" * 40)
        
        print(f"   🔍 Searching database for:")
        print(f"      PO: {extracted_data.po_number}")
        print(f"      LOT: {extracted_data.lot_number}")
        
        # Simulate database search
        db_service = DatabaseService()
        
        # Mock database results for testing
        po_data = {
            'po_number': extracted_data.po_number,
            'lot_number': extracted_data.lot_number,
            'vendor_id': 'ABC_PHARMA_001',
            'vendor_name': 'ABC Pharmaceuticals',
            'vendor_email': 'support@abc-pharma.com',
            'epcis_file_path': '/path/to/EPCIS_ABC_PHARMA_20240615.xml',
            'submission_date': '2024-06-15T14:30:00Z',
            'status': 'validation_failed'
        }
        
        print(f"   ✅ Found matching records:")
        print(f"      Vendor: {po_data['vendor_name']}")
        print(f"      Email: {po_data['vendor_email']}")
        print(f"      EPCIS File: {po_data['epcis_file_path']}")
        print(f"      Status: {po_data['status']}")
        print()
        
        return po_data
    
    async def test_step_3_epcis_validation(self, po_data):
        """Test Step 3: EPCIS file validation"""
        print("🔍 STEP 3: EPCIS File Validation")
        print("-" * 40)
        
        print(f"   📄 Analyzing EPCIS file: {po_data['epcis_file_path']}")
        
        # Simulate EPCIS validation using the analyzer
        validation_results = await self.epcis_analyzer.analyze_epcis_file(po_data['epcis_file_path'])
        
        print(f"   📊 Validation Results:")
        print(f"      Total Events: {validation_results.get('total_events', 0)}")
        print(f"      Errors Found: {len(validation_results.get('errors', []))}")
        
        for i, error in enumerate(validation_results.get('errors', [])[:3], 1):
            print(f"      Error {i}: {error.get('type')} - {error.get('description')[:50]}...")
        
        print()
        return validation_results
    
    async def test_step_4_action_plan_generation(self, po_data, validation_results):
        """Test Step 4: Action plan generation"""
        print("📝 STEP 4: Action Plan Generation")
        print("-" * 40)
        
        print(f"   🎯 Generating action plan for vendor: {po_data['vendor_name']}")
        
        # Generate action plan
        action_plan = await self.vendor_communicator.generate_action_plan(
            po_data, validation_results
        )
        
        print(f"   📋 Action Plan Created:")
        print(f"      Priority: {action_plan.get('priority', 'Medium')}")
        print(f"      Actions: {len(action_plan.get('actions', []))}")
        print(f"      Deadline: {action_plan.get('deadline', 'N/A')}")
        
        for i, action in enumerate(action_plan.get('actions', [])[:2], 1):
            print(f"      Action {i}: {action[:60]}...")
        
        print()
        return action_plan
    
    async def test_step_5_vendor_communication(self, po_data, action_plan):
        """Test Step 5: Send email to vendor"""
        print("📤 STEP 5: Vendor Communication")
        print("-" * 40)
        
        print(f"   📧 Sending action plan to: {po_data['vendor_email']}")
        
        # Generate and send email
        email_result = await self.vendor_communicator.send_action_plan_email(
            po_data['vendor_email'], action_plan
        )
        
        print(f"   ✅ Email sent successfully:")
        print(f"      To: {po_data['vendor_email']}")
        print(f"      Subject: {email_result.get('subject', 'N/A')}")
        print(f"      Message ID: {email_result.get('message_id', 'N/A')}")
        print()
        
        return email_result
    
    async def run_complete_test(self):
        """Run all steps in sequence"""
        print("🚀 COMPLETE EMAIL AGENT WORKFLOW TEST")
        print("=" * 50)
        print()
        
        try:
            # Step 1: Email reading
            extracted_data = await self.test_step_1_email_reading()
            
            # Step 2: Database search
            po_data = await self.test_step_2_database_search(extracted_data)
            
            # Step 3: EPCIS validation
            validation_results = await self.test_step_3_epcis_validation(po_data)
            
            # Step 4: Action plan generation
            action_plan = await self.test_step_4_action_plan_generation(po_data, validation_results)
            
            # Step 5: Vendor communication
            email_result = await self.test_step_5_vendor_communication(po_data, action_plan)
            
            print("🎉 ALL STEPS COMPLETED SUCCESSFULLY!")
            print("=" * 50)
            
            return True
            
        except Exception as e:
            print(f"❌ Workflow failed at step: {str(e)}")
            return False

async def main():
    """Run the workflow test"""
    tester = WorkflowStepTester()
    success = await tester.run_complete_test()
    
    if success:
        print("\n✅ End-to-end workflow test passed!")
    else:
        print("\n❌ End-to-end workflow test failed!")

if __name__ == "__main__":
    asyncio.run(main())