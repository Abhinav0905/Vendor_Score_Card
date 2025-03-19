import os
import sys
import pytest
from fastapi.testclient import TestClient
from main import app
from models.base import SessionLocal
from models.epcis_submission import EPCISSubmission

client = TestClient(app)

# Sample EPCIS XML for testing
SAMPLE_EPCIS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<epcis:EPCISDocument xmlns:epcis="urn:epcglobal:epcis:xsd:1" xmlns:cbv="urn:epcglobal:cbv:mda">
    <EPCISBody>
        <EventList>
            <!-- First commission the item -->
            <ObjectEvent>
                <eventTime>2024-01-15T10:30:47.0Z</eventTime>
                <eventTimeZoneOffset>+01:00</eventTimeZoneOffset>
                <epcList>
                    <epc>urn:epc:id:sgtin:0614141.107346.2017</epc>
                </epcList>
                <action>ADD</action>
                <bizStep>urn:epcglobal:cbv:bizstep:commissioning</bizStep>
                <disposition>urn:epcglobal:cbv:disp:active</disposition>
                <readPoint><id>urn:epc:id:sgln:0614141.07346.1234</id></readPoint>
            </ObjectEvent>
            
            <!-- Then pack it -->
            <AggregationEvent>
                <eventTime>2024-01-15T11:00:47.0Z</eventTime>
                <eventTimeZoneOffset>+01:00</eventTimeZoneOffset>
                <parentID>urn:epc:id:sscc:0614141.1234567890</parentID>
                <childEPCs>
                    <epc>urn:epc:id:sgtin:0614141.107346.2017</epc>
                </childEPCs>
                <action>ADD</action>
                <bizStep>urn:epcglobal:cbv:bizstep:packing</bizStep>
                <disposition>urn:epcglobal:cbv:disp:in_progress</disposition>
                <readPoint><id>urn:epc:id:sgln:0614141.07346.1234</id></readPoint>
            </AggregationEvent>
            
            <!-- Finally ship it -->
            <ObjectEvent>
                <eventTime>2024-01-15T11:30:47.0Z</eventTime>
                <eventTimeZoneOffset>+01:00</eventTimeZoneOffset>
                <epcList>
                    <epc>urn:epc:id:sgtin:0614141.107346.2017</epc>
                </epcList>
                <action>OBSERVE</action>
                <bizStep>urn:epcglobal:cbv:bizstep:shipping</bizStep>
                <disposition>urn:epcglobal:cbv:disp:in_transit</disposition>
                <readPoint>
                    <id>urn:epc:id:sgln:0614141.07346.1234</id>
                </readPoint>
                <bizTransactionList>
                    <bizTransaction type="urn:epcglobal:cbv:btt:po">urn:epcglobal:cbv:bt:0614141073467:1234</bizTransaction>
                    <bizTransaction type="urn:epcglobal:cbv:btt:desadv">urn:epcglobal:cbv:bt:0614141073467:5678</bizTransaction>
                </bizTransactionList>
                <extension>
                    <sourceList>
                        <source type="urn:epcglobal:cbv:sdt:owning_party">urn:epc:id:sgln:0614141.00000.0</source>
                        <source type="urn:epcglobal:cbv:sdt:location">urn:epc:id:sgln:0614141.07346.0</source>
                    </sourceList>
                    <destinationList>
                        <destination type="urn:epcglobal:cbv:sdt:owning_party">urn:epc:id:sgln:0012345.00000.0</destination>
                        <destination type="urn:epcglobal:cbv:sdt:location">urn:epc:id:sgln:0012345.11111.0</destination>
                    </destinationList>
                </extension>
            </ObjectEvent>
        </EventList>
    </EPCISBody>
</epcis:EPCISDocument>"""

def test_validate_epcis_xml():
    """Test EPCIS XML validation"""
    from epcis import EPCISValidator
    validator = EPCISValidator()
    result = validator.validate_document(SAMPLE_EPCIS_XML.encode(), is_xml=True)
    print("\nValidation result:", result)  # Added debug print
    assert result['valid'] == True
    
    # The document is valid but has a warning about incomplete sequence
    errors = result['errors']
    assert len(errors) == 1
    assert errors[0]['type'] == 'sequence'
    assert errors[0]['severity'] == 'warning'
    assert 'Incomplete sequence' in errors[0]['message']
    assert 'ends with shipping' in errors[0]['message']

def test_upload_epcis_file():
    """Test EPCIS file upload endpoint"""
    # Delete any existing test files before running the test
    if os.path.exists("test_epcis.xml"):
        os.remove("test_epcis.xml")

    # Clean up any existing submissions from the database
    db = SessionLocal()
    try:
        db.query(EPCISSubmission).filter_by(supplier_id="supplier_test").delete()
        db.commit()
    finally:
        db.close()
        
    # Create test file
    with open("test_epcis.xml", "w") as f:
        f.write(SAMPLE_EPCIS_XML)
    
    try:
        # Test file upload
        with open("test_epcis.xml", "rb") as f:
            response = client.post(
                "/epcis/upload",
                files={"file": ("test_epcis.xml", f, "application/xml")},
                data={"supplier_id": "supplier_test"}
            )
        
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        assert "submission_id" in result
        
    finally:
        # Cleanup test file
        if os.path.exists("test_epcis.xml"):
            os.remove("test_epcis.xml")

def test_invalid_epcis_xml():
    """Test invalid EPCIS XML validation"""
    invalid_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <epcis:EPCISDocument xmlns:epcis="urn:epcglobal:epcis:xsd:1">
        <EPCISBody>
            <EventList>
                <ObjectEvent>
                    <eventTime>invalid-time</eventTime>
                    <eventTimeZoneOffset>invalid</eventTimeZoneOffset>
                </ObjectEvent>
            </EventList>
        </EPCISBody>
    </epcis:EPCISDocument>"""
    
    from epcis import EPCISValidator
    validator = EPCISValidator()
    result = validator.validate_document(invalid_xml.encode(), is_xml=True)  # Updated method name
    assert result['valid'] == False
    assert len(result['errors']) > 0

def test_extract_vendor_from_filename():
    """Test vendor name extraction from filenames"""
    from epcis.submission_service import SubmissionService
    
    service = SubmissionService()
    
    # Test standard format
    assert service.extract_vendor_from_filename('EPCIS_RFXIS_XML_GS1_1803334398798080.xml') == 'RFXIS'
    
    # Test alternative format
    assert service.extract_vendor_from_filename('VENDOR123_EPCIS_file.xml') == 'VENDOR123'
    
    # Test with different separators
    assert service.extract_vendor_from_filename('EPCIS-SUPPLIER1-test.xml') == 'SUPPLIER1'
    assert service.extract_vendor_from_filename('EPCIS.VENDOR2.file.xml') == 'VENDOR2'
    
    # Test invalid formats
    assert service.extract_vendor_from_filename('invalid_filename.xml') is None
    assert service.extract_vendor_from_filename('test.xml') is None

def test_find_error_line_numbers():
    """Test error line number detection"""
    from epcis.submission_service import SubmissionService
    
    service = SubmissionService()
    
    # Test XML content
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<epcis:EPCISDocument xmlns:epcis="urn:epcglobal:epcis:xsd:1">
    <EPCISBody>
        <EventList>
            <ObjectEvent>
                <eventTime>2024-01-15T11:30:47.0Z</eventTime>
                <eventTimeZoneOffset>+00:00</eventTimeZoneOffset>
                <epcList>
                    <epc>urn:epc:id:sgtin:0614141.107346.2017</epc>
                </epcList>
                <action>OBSERVE</action>
                <bizStep>urn:epcglobal:cbv:bizstep:shipping</bizStep>
            </ObjectEvent>
        </EventList>
    </EPCISBody>
</epcis:EPCISDocument>'''.encode('utf-8')
    
    # Check XML error line detection
    xml_lines = service.find_error_line_numbers(xml_content, is_xml=True)
    assert len(xml_lines) > 0
    assert any(5 <= line <= 7 for line in xml_lines.values())  # ObjectEvent lines
    assert any(8 <= line <= 10 for line in xml_lines.values())  # Required fields lines

def test_epcis_file_upload():
    """Test EPCIS file upload endpoint"""
    # Clean up any existing submissions
    db = SessionLocal()
    try:
        db.query(EPCISSubmission).filter_by(supplier_id="TESTVENDOR").delete()
        db.commit()
    finally:
        db.close()
        
    # Create test file content
    test_content = '''<?xml version="1.0" encoding="UTF-8"?>
<epcis:EPCISDocument xmlns:epcis="urn:epcglobal:epcis:xsd:1">
    <EPCISBody>
        <EventList>
            <ObjectEvent>
                <eventTime>2024-01-15T11:30:47.0Z</eventTime>
                <eventTimeZoneOffset>+00:00</eventTimeZoneOffset>
                <epcList>
                    <epc>urn:epc:id:sgtin:0614141.107346.2017</epc>
                </epcList>
                <action>OBSERVE</action>
                <bizStep>urn:epcglobal:cbv:bizstep:shipping</bizStep>
            </ObjectEvent>
        </EventList>
    </EPCISBody>
</epcis:EPCISDocument>'''
    
    # Test file upload with vendor name in filename
    files = {
        'file': ('EPCIS_TESTVENDOR_file.xml', test_content, 'application/xml')
    }
    
    response = client.post("/epcis/upload", files=files)
    assert response.status_code == 200
    
    data = response.json()
    assert data['success'] is True
    assert data['supplier_name'] == 'TESTVENDOR'
    assert 'submission_id' in data
    
    # Test file upload with invalid format
    invalid_files = {
        'file': ('test.txt', 'invalid content', 'text/plain')
    }
    response = client.post("/epcis/upload", files=invalid_files)
    assert response.status_code == 415  # Unsupported Media Type

def test_submission_error_handling():
    """Test submission error handling and line number reporting"""
    # Clean up any existing submissions
    db = SessionLocal()
    try:
        db.query(EPCISSubmission).filter_by(supplier_id="TESTVENDOR").delete()
        db.commit()
    finally:
        db.close()
        
    # Create test file with deliberate errors
    test_content = '''<?xml version="1.0" encoding="UTF-8"?>
<epcis:EPCISDocument xmlns:epcis="urn:epcglobal:epcis:xsd:1">
    <EPCISBody>
        <EventList>
            <ObjectEvent>
                <!-- Missing required eventTime -->
                <eventTimeZoneOffset>+00:00</eventTimeZoneOffset>
                <epcList>
                    <epc>invalid-epc-format</epc>
                </epcList>
                <action>INVALID_ACTION</action>
            </ObjectEvent>
        </EventList>
    </EPCISBody>
</epcis:EPCISDocument>'''
    
    files = {
        'file': ('EPCIS_TESTVENDOR_error.xml', test_content, 'application/xml')
    }
    
    response = client.post("/epcis/upload", files=files)
    assert response.status_code in [400, 200]  # Either validation failed or held for review
    
    data = response.json()
    assert 'errors' in data
    
    # Check if errors contain line numbers
    has_line_numbers = any(error.get('line_number') is not None for error in data['errors'])
    assert has_line_numbers, "No line numbers found in validation errors"