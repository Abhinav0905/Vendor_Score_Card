import unittest
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.epcis import EPCISValidator  # Updated import path

class TestEPCISComplexSequence(unittest.TestCase):
    """Test complex EPCIS sequence validation with multiple products and levels"""
    
    def setUp(self):
        self.validator = EPCISValidator()
        
        # Complex EPCIS document with full commissioning -> aggregation -> shipping sequence
        self.complex_epcis_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ns4:EPCISDocument xmlns:cbvmda="urn:epcglobal:cbv:mda" xmlns:gs1ushc="http://epcis.gs1us.org/hc/ns" schemaVersion="1.2" creationDate="2025-01-08T22:40:18.950-06:00" xmlns:ns4="urn:epcglobal:epcis:xsd:1">
    <EPCISHeader>
        <StandardBusinessDocumentHeader>
            <HeaderVersion>1.0</HeaderVersion>
            <Sender>
                <Identifier Authority="SGLN">urn:epc:id:sgln:0327808.00000.0</Identifier>
            </Sender>
            <Receiver>
                <Identifier Authority="SGLN">urn:epc:id:sgln:08662890004.0.0</Identifier>
            </Receiver>
            <DocumentIdentification>
                <Standard>EPCglobal</Standard>
                <TypeVersion>1.0</TypeVersion>
                <InstanceIdentifier>test-instance-id</InstanceIdentifier>
                <Type>Events</Type>
                <CreationDateAndTime>2025-01-08T22:40:18.950-06:00</CreationDateAndTime>
            </DocumentIdentification>
        </StandardBusinessDocumentHeader>
    </EPCISHeader>
    <EPCISBody>
        <EventList>
            <!-- First product commissioning -->
            <ObjectEvent>
                <eventTime>2024-05-24T00:00:00.000000Z</eventTime>
                <eventTimeZoneOffset>+08:00</eventTimeZoneOffset>
                <epcList>
                    <epc>urn:epc:id:sgtin:0327808.019001.100000001</epc>
                    <epc>urn:epc:id:sgtin:0327808.019001.100000002</epc>
                </epcList>
                <action>ADD</action>
                <bizStep>urn:epcglobal:cbv:bizstep:commissioning</bizStep>
                <disposition>urn:epcglobal:cbv:disp:active</disposition>
                <readPoint><id>urn:epc:id:sgln:0327808.00000.0</id></readPoint>
                <bizLocation><id>urn:epc:id:sgln:0327808.00000.0</id></bizLocation>
                <extension>
                    <ilmd>
                        <cbvmda:lotNumber>TEST123</cbvmda:lotNumber>
                        <cbvmda:itemExpirationDate>2027-04-30</cbvmda:itemExpirationDate>
                    </ilmd>
                </extension>
            </ObjectEvent>
            
            <!-- Case commissioning -->
            <ObjectEvent>
                <eventTime>2024-05-24T00:00:01.000000Z</eventTime>
                <eventTimeZoneOffset>+08:00</eventTimeZoneOffset>
                <epcList>
                    <epc>urn:epc:id:sgtin:0327808.519001.200000001</epc>
                </epcList>
                <action>ADD</action>
                <bizStep>urn:epcglobal:cbv:bizstep:commissioning</bizStep>
                <disposition>urn:epcglobal:cbv:disp:active</disposition>
                <readPoint><id>urn:epc:id:sgln:0327808.00000.0</id></readPoint>
                <bizLocation><id>urn:epc:id:sgln:0327808.00000.0</id></bizLocation>
                <extension>
                    <ilmd>
                        <cbvmda:lotNumber>TEST123</cbvmda:lotNumber>
                        <cbvmda:itemExpirationDate>2027-04-30</cbvmda:itemExpirationDate>
                    </ilmd>
                </extension>
            </ObjectEvent>
            
            <!-- Aggregation of products into case -->
            <AggregationEvent>
                <eventTime>2024-05-24T00:00:02.000000Z</eventTime>
                <eventTimeZoneOffset>+08:00</eventTimeZoneOffset>
                <parentID>urn:epc:id:sgtin:0327808.519001.200000001</parentID>
                <childEPCs>
                    <epc>urn:epc:id:sgtin:0327808.019001.100000001</epc>
                    <epc>urn:epc:id:sgtin:0327808.019001.100000002</epc>
                </childEPCs>
                <action>ADD</action>
                <bizStep>urn:epcglobal:cbv:bizstep:packing</bizStep>
                <disposition>urn:epcglobal:cbv:disp:in_progress</disposition>
                <readPoint><id>urn:epc:id:sgln:0327808.00000.0</id></readPoint>
                <bizLocation><id>urn:epc:id:sgln:0327808.00000.0</id></bizLocation>
            </AggregationEvent>
            
            <!-- Shipping event -->
            <ObjectEvent>
                <eventTime>2024-05-24T00:00:03.000000Z</eventTime>
                <eventTimeZoneOffset>+08:00</eventTimeZoneOffset>
                <epcList>
                    <epc>urn:epc:id:sgtin:0327808.519001.200000001</epc>
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

    def test_valid_sequence(self):
        """Test validation of a valid complex event sequence"""
        result = self.validator.validate(self.complex_epcis_xml.encode(), is_xml=True)
        print("\nValidation result for valid sequence:")
        if not result['valid']:
            for error in result['errors']:
                print(f" - {error.get('type')}: {error.get('message')}")
        self.assertTrue(result['valid'], "Valid sequence should pass validation")

    def test_missing_commissioning(self):
        """Test detection of shipping without commissioning"""
        # Create invalid sequence by removing commissioning events
        invalid_sequence = self.complex_epcis_xml.replace(
            'urn:epcglobal:cbv:bizstep:commissioning',
            'urn:epcglobal:cbv:bizstep:packing'
        )
        
        result = self.validator.validate(invalid_sequence.encode(), is_xml=True)
        print("\nValidation result for missing commissioning:")
        for error in result['errors']:
            print(f" - {error.get('type')}: {error.get('message')}")
            
        self.assertFalse(result['valid'], "Invalid sequence should fail validation")
        has_commissioning_error = any(
            'commissioning' in err.get('message', '').lower()
            for err in result['errors']
        )
        self.assertTrue(has_commissioning_error, "Should report missing commissioning error")

    def test_out_of_order_events(self):
        """Test detection of out-of-order events"""
        # Create sequence with shipping before aggregation
        doc_lines = self.complex_epcis_xml.split('\n')
        shipping_event = None
        shipping_start = None
        shipping_end = None
        
        # Find the shipping event
        for i, line in enumerate(doc_lines):
            if 'bizStep>urn:epcglobal:cbv:bizstep:shipping' in line:
                # Find start of shipping event
                for j in range(i, -1, -1):
                    if '<ObjectEvent>' in doc_lines[j]:
                        shipping_start = j
                        break
                # Find end of shipping event
                for j in range(i, len(doc_lines)):
                    if '</ObjectEvent>' in doc_lines[j]:
                        shipping_end = j
                        break
                shipping_event = doc_lines[shipping_start:shipping_end+1]
                break
        
        # Remove original shipping event
        doc_lines = [line for i, line in enumerate(doc_lines) 
                    if i < shipping_start or i > shipping_end]
        
        # Find aggregation event and insert shipping before it
        for i, line in enumerate(doc_lines):
            if '<AggregationEvent>' in line:
                # Insert shipping event before aggregation
                doc_lines[i:i] = shipping_event
                break
                
        invalid_sequence = '\n'.join(doc_lines)
        
        result = self.validator.validate(invalid_sequence.encode(), is_xml=True)
        print("\nValidation result for out-of-order events:")
        for error in result['errors']:
            print(f" - {error.get('type')}: {error.get('message')}")
            
        self.assertFalse(result['valid'], "Out of order sequence should fail validation")
        has_sequence_error = any(
            'sequence' in err.get('type', '').lower() or
            'before' in err.get('message', '').lower()
            for err in result['errors']
        )
        self.assertTrue(has_sequence_error, "Should report sequence error")

    def test_missing_packing(self):
        """Test detection of shipping without packing"""
        # Create sequence without packing event
        invalid_sequence = '\n'.join(
            line for line in self.complex_epcis_xml.split('\n')
            if 'AggregationEvent' not in line
        )
        
        result = self.validator.validate(invalid_sequence.encode(), is_xml=True)
        print("\nValidation result for missing packing:")
        for error in result['errors']:
            print(f" - {error.get('type')}: {error.get('message')}")
            
        self.assertFalse(result['valid'], "Missing packing should fail validation")
        has_packing_error = any(
            'packing' in err.get('message', '').lower()
            for err in result['errors']
        )
        self.assertTrue(has_packing_error, "Should report missing packing error")

if __name__ == '__main__':
    unittest.main()