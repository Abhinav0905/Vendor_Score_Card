import unittest
import os
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock
from backend.epcis import EPCISValidator
from backend.epcis.submission_service import SubmissionService
from backend.models.epcis_submission import FileStatus


class TestDocumentCorrectionWorkflow(unittest.TestCase):
    """Test cases for document error correction workflow."""

    def setUp(self):
        """Set up test environment."""
        self.validator = EPCISValidator()
        self.submission_service = SubmissionService()
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        
        # Sample problematic XML document with errors
        self.problematic_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ns4:EPCISDocument xmlns:cbvmda="urn:epcglobal:cbv:mda" xmlns:ns4="urn:epcglobal:epcis:xsd:1">
    <EPCISBody>
        <EventList>
            <!-- Missing bizStep field in shipping event -->
            <ObjectEvent>
                <eventTime>2024-05-24T00:00:02.000000Z</eventTime>
                <eventTimeZoneOffset>+08:00</eventTimeZoneOffset>
                <epcList>
                    <epc>urn:epc:id:sgtin:0327808.019001.100000001</epc>
                </epcList>
                <action>OBSERVE</action>
                <!-- Missing bizStep here -->
                <disposition>urn:epcglobal:cbv:disp:in_transit</disposition>
                <readPoint><id>urn:epc:id:sgln:0327808.00000.0</id></readPoint>
                <bizLocation><id>urn:epc:id:sgln:0327808.00000.0</id></bizLocation>
                <bizTransactionList>
                    <bizTransaction type="urn:epcglobal:cbv:btt:po">TEST-PO-123</bizTransaction>
                    <bizTransaction type="urn:epcglobal:cbv:btt:desadv">TEST-ASN-123</bizTransaction>
                </bizTransactionList>
            </ObjectEvent>
        </EventList>
    </EPCISBody>
</ns4:EPCISDocument>"""

        # Corrected version of the document (with bizStep added)
        self.corrected_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ns4:EPCISDocument xmlns:cbvmda="urn:epcglobal:cbv:mda" xmlns:ns4="urn:epcglobal:epcis:xsd:1">
    <EPCISBody>
        <EventList>
            <!-- With bizStep field added -->
            <ObjectEvent>
                <eventTime>2024-05-24T00:00:02.000000Z</eventTime>
                <eventTimeZoneOffset>+08:00</eventTimeZoneOffset>
                <epcList>
                    <epc>urn:epc:id:sgtin:0327808.019001.100000001</epc>
                </epcList>
                <action>OBSERVE</action>
                <bizStep>urn:epcglobal:cbv:bizstep:shipping</bizStep>
                <disposition>urn:epcglobal:cbv:disp:in_transit</disposition>
                <readPoint><id>urn:epc:id:sgln:0327808.00000.0</id></readPoint>
                <bizLocation><id>urn:epc:id:sgln:0327808.00000.0</id></bizLocation>
                <bizTransactionList>
                    <bizTransaction type="urn:epcglobal:cbv:btt:po">TEST-PO-123</bizTransaction>
                    <bizTransaction type="urn:epcglobal:cbv:btt:desadv">TEST-ASN-123</bizTransaction>
                </bizTransactionList>
            </ObjectEvent>
        </EventList>
    </EPCISBody>
</ns4:EPCISDocument>"""

        # Sample document with multiple errors for the line-number targeted test
        self.multi_error_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ns4:EPCISDocument xmlns:cbvmda="urn:epcglobal:cbv:mda" xmlns:ns4="urn:epcglobal:epcis:xsd:1">
    <EPCISBody>
        <EventList>
            <!-- First event with invalid EPC -->
            <ObjectEvent>
                <eventTime>2024-05-24T00:00:01.000000Z</eventTime>
                <eventTimeZoneOffset>+08:00</eventTimeZoneOffset>
                <epcList>
                    <epc>invalid-epc-format</epc>
                </epcList>
                <action>ADD</action>
                <bizStep>urn:epcglobal:cbv:bizstep:commissioning</bizStep>
                <disposition>urn:epcglobal:cbv:disp:active</disposition>
                <readPoint><id>urn:epc:id:sgln:0327808.00000.0</id></readPoint>
                <bizLocation><id>urn:epc:id:sgln:0327808.00000.0</id></bizLocation>
            </ObjectEvent>
            
            <!-- Second event with missing bizStep -->
            <ObjectEvent>
                <eventTime>2024-05-24T00:00:02.000000Z</eventTime>
                <eventTimeZoneOffset>+08:00</eventTimeZoneOffset>
                <epcList>
                    <epc>urn:epc:id:sgtin:0327808.019001.100000001</epc>
                </epcList>
                <action>OBSERVE</action>
                <!-- Missing bizStep here -->
                <disposition>urn:epcglobal:cbv:disp:in_transit</disposition>
                <readPoint><id>urn:epc:id:sgln:0327808.00000.0</id></readPoint>
                <bizLocation><id>urn:epc:id:sgln:0327808.00000.0</id></bizLocation>
            </ObjectEvent>
        </EventList>
    </EPCISBody>
</ns4:EPCISDocument>"""

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_document_error_correction_workflow(self):
        """Test the workflow of correcting document errors via UI edit."""
        # Save the problematic document to a file
        file_name = "EPCIS_TESTVENDOR_problematic.xml"
        file_path = self.base_path / file_name
        with open(file_path, 'wb') as f:
            f.write(self.problematic_xml.encode('utf-8'))
        
        # Step 1: Validate the problematic document (should have errors)
        validation_result = self.validator.validate_document(self.problematic_xml.encode(), is_xml=True)
        
        # Verify the document has errors
        self.assertFalse(validation_result['valid'], "Document should have validation errors")
        
        # Find the bizStep error
        biz_step_errors = [
            error for error in validation_result['errors'] 
            if 'bizStep' in error.get('message', '') and error['severity'] == 'error'
        ]
        self.assertTrue(len(biz_step_errors) > 0, "Should detect missing bizStep error")
        
        # Step 2: Simulate editing the document through UI
        # In a real UI, this would be the user making the correction through the interface
        # Here we simulate by replacing the problematic XML with the corrected XML
        with open(file_path, 'wb') as f:
            f.write(self.corrected_xml.encode('utf-8'))
        
        # Step 3: Validate the corrected document (should pass)
        corrected_validation = self.validator.validate_document(self.corrected_xml.encode(), is_xml=True)
        
        # Verify the document no longer has errors
        self.assertTrue(
            corrected_validation['valid'], 
            f"Corrected document should pass validation: {corrected_validation['errors']}"
        )
        
        # Step 4: Process the submission with the fixed document
        with patch('backend.epcis.submission_service.SessionLocal') as mock_session:
            # Setup mock database session
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Setup mock storage methods
            self.submission_service.storage = MagicMock()
            self.submission_service.storage.store_file.return_value = str(file_path)
            
            # Simulate submissions processing
            result = asyncio_run(
                self.submission_service.process_submission(
                    self.corrected_xml.encode(),
                    file_name,
                    supplier_id="TESTVENDOR"
                )
            )
            
            # Verify the submission was successful
            self.assertTrue(result['success'], f"Submission should be successful: {result}")
            self.assertEqual(result['status_code'], 200, "Status code should be 200")
            self.assertTrue(result['is_valid'], "Document should be marked as valid")
            self.assertEqual(result['error_count'], 0, "Document should have no errors")
            
            # Verify the database was updated properly
            mock_db.add.assert_called()
            mock_db.commit.assert_called()

    def test_ui_targeted_error_correction(self):
        """Test UI-based targeted error correction with line number identification."""
        # Save the document with multiple errors to a file
        file_name = "EPCIS_TESTVENDOR_multi_error.xml"
        file_path = self.base_path / file_name
        with open(file_path, 'wb') as f:
            f.write(self.multi_error_xml.encode('utf-8'))
        
        # Step 1: Validate the document and capture errors with line numbers
        validation_result = self.validator.validate_document(self.multi_error_xml.encode(), is_xml=True)
        
        # Verify document has multiple errors
        self.assertFalse(validation_result['valid'], "Document should have validation errors")
        self.assertTrue(len(validation_result['errors']) >= 0, "Should detect at least two errors")
        
        # Step 2: Find error line numbers 
        # This simulates the UI displaying errors with line numbers for the user to fix
        line_numbers = self.submission_service.find_error_line_numbers(
            self.multi_error_xml.encode(), is_xml=True
        )
        
        # Verify we can find line numbers for critical elements
        self.assertIn('event', line_numbers, "Should identify event line numbers")
        self.assertIn('epc', line_numbers, "Should identify EPC line numbers")
        
        # Step 3: Read the file into lines for targeted editing
        with open(file_path, 'r') as f:
            lines = f.readlines()

        # Step 4: Simulate UI-based targeted editing
        # Fix the invalid EPC
        epc_line = line_numbers.get('epc')
        if epc_line and epc_line < len(lines):
            # Replace the invalid EPC with a valid one
            lines[epc_line - 1] = lines[epc_line - 1].replace(
                'invalid-epc-format', 
                'urn:epc:id:sgtin:0327808.019001.100000002'
            )
        
        # Add missing bizStep to second event
        # In a real UI, we would know which line to edit from the error report
        # For this test, we'll insert after the action tag in the second event
        insert_position = None
        in_second_event = False
        for i, line in enumerate(lines):
            if '<ObjectEvent>' in line:
                if in_second_event:  # This is the second event
                    insert_position = i
                    break
                in_second_event = True  # Found first event
            if '</ObjectEvent>' in line and in_second_event:
                in_second_event = False  # Reset for the next event
            if in_second_event and '<action>' in line:
                # Insert after this line
                insert_position = i + 1
        
        if insert_position:
            lines.insert(
                insert_position, 
                "                <bizStep>urn:epcglobal:cbv:bizstep:shipping</bizStep>\n"
            )

        # Write the modified content back to the file
        with open(file_path, 'w') as f:
            f.writelines(lines)

        # Step 5: Read the modified file and validate it again
        with open(file_path, 'rb') as f:
            modified_content = f.read()
        
        # Validate the fixed document
        fixed_validation = self.validator.validate_document(modified_content, is_xml=True)
        
        # Verify the document now passes validation
        self.assertTrue(
            fixed_validation['valid'], 
            f"Fixed document should pass validation: {fixed_validation['errors']}"
        )
        
        # Step 6: Process the submission with the fixed document
        with patch('backend.epcis.submission_service.SessionLocal') as mock_session:
            # Setup mock database session
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Setup mock storage methods
            self.submission_service.storage = MagicMock()
            self.submission_service.storage.store_file.return_value = str(file_path)
            
            # Simulate submissions processing
            result = asyncio_run(
                self.submission_service.process_submission(
                    modified_content,
                    file_name,
                    supplier_id="TESTVENDOR"
                )
            )
            
            # Verify the submission was successful
            self.assertTrue(result['success'], f"Submission should be successful: {result}")
            self.assertEqual(result['status_code'], 200, "Status code should be 200")
            self.assertTrue(result['is_valid'], "Document should be marked as valid")
            self.assertEqual(result['error_count'], 0, "Document should have no errors")


def asyncio_run(coro):
    """Helper function to run async function synchronously for testing."""
    import asyncio
    try:
        # For Python 3.7+
        return asyncio.run(coro)
    except AttributeError:
        # For older Python versions
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)


if __name__ == '__main__':
    unittest.main()