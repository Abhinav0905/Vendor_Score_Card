import os
import pytest
import json
from fastapi.testclient import TestClient
from ..main import app
from ..epcis.validator import EPCISValidator
from ..epcis.submission_service import SubmissionService

client = TestClient(app)

# Sample EPCIS XML for testing
SAMPLE_EPCIS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<epcis:EPCISDocument xmlns:epcis="urn:epcglobal:epcis:xsd:1">
    <EPCISBody>
        <EventList>
            <ObjectEvent>
                <eventTime>2024-01-15T11:30:47.0Z</eventTime>
                <eventTimeZoneOffset>+01:00</eventTimeZoneOffset>
                <epcList>
                    <epc>urn:epc:id:sgtin:0614141.107346.2017</epc>
                </epcList>
                <action>OBSERVE</action>
                <bizStep>shipping</bizStep>
                <readPoint>
                    <id>urn:epc:id:sgln:0614141.07346.1234</id>
                </readPoint>
            </ObjectEvent>
        </EventList>
    </EPCISBody>
</epcis:EPCISDocument>"""

def test_validate_epcis_xml():
    """Test EPCIS XML validation"""
    validator = EPCISValidator()
    result = validator.validate(SAMPLE_EPCIS_XML.encode(), is_xml=True)
    assert result['valid'] == True
    assert len(result['errors']) == 0

def test_upload_epcis_file():
    """Test EPCIS file upload endpoint"""
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
    
    validator = EPCISValidator()
    result = validator.validate(invalid_xml.encode(), is_xml=True)
    assert result['valid'] == False
    assert len(result['errors']) > 0