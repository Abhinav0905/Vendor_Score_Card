import os
import shutil
from pathlib import Path

# Test EPCIS XML content
TEST_EPCIS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<epcis:EPCISDocument xmlns:epcis="urn:epcglobal:epcis:xsd:1" schemaVersion="1.2">
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
                <disposition>urn:epcglobal:cbv:disp:in_transit</disposition>
                <readPoint>
                    <id>urn:epc:id:sgln:0614141.07346.1234</id>
                </readPoint>
            </ObjectEvent>
        </EventList>
    </EPCISBody>
</epcis:EPCISDocument>"""

def setup_test_environment():
    """Set up test directories and files"""
    # Create base directories
    drop_dir = Path("epcis_drop")
    if drop_dir.exists():
        shutil.rmtree(drop_dir)
    
    # Create supplier directories
    suppliers = ["supplier_a", "supplier_b", "supplier_c"]
    for supplier in suppliers:
        supplier_dir = drop_dir / supplier
        supplier_dir.mkdir(parents=True, exist_ok=True)
        
        # Create archived directory for each supplier
        archive_dir = supplier_dir / "archived"
        archive_dir.mkdir(exist_ok=True)

def create_test_file(supplier: str, index: int = 1):
    """Create a test EPCIS file in the supplier's directory"""
    file_path = Path("epcis_drop") / supplier / f"test_epcis_{index}.xml"
    with open(file_path, "w") as f:
        f.write(TEST_EPCIS_XML)
    print(f"Created test file: {file_path}")

if __name__ == "__main__":
    # Set up test environment
    setup_test_environment()
    print("Test environment set up completed")
    
    # Create test files
    create_test_file("supplier_a", 1)
    print("\nTest files created. The file watcher should detect and process these files.")
    print("\nWatch the application logs for processing status.")