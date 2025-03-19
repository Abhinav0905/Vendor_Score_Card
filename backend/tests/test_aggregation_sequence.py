import unittest
import os
import xml.etree.ElementTree as ET
import re
import sys
import logging
import json
from datetime import datetime
from pathlib import Path

# Import the correct EPCISValidator from the reorganized modules
from backend.epcis import EPCISValidator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestAggregationSequence(unittest.TestCase):
    """Test to verify that aggregation events out of sequence are correctly detected"""
    
    def setUp(self):
        self.validator = EPCISValidator()
        
        # XML templates
        self.xml_header = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<epcis:EPCISDocument xmlns:epcis="urn:epcglobal:epcis:xsd:1" 
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                    creationDate="2025-02-08T10:00:47.0Z" 
                    schemaVersion="1.2">
  <EPCISBody>
    <EventList>"""
        
        self.xml_footer = """
    </EventList>
  </EPCISBody>
</epcis:EPCISDocument>"""
        
        # Create a shipping-only XML with valid SGTINs without P prefix
        self.shipping_only_xml = self.xml_header + """
      <ObjectEvent>
        <eventTime>2025-02-08T10:00:47Z</eventTime>
        <eventTimeZoneOffset>+00:00</eventTimeZoneOffset>
        <epcList>
          <epc>urn:epc:id:sgtin:0324478.532204.0000065002</epc>
          <epc>urn:epc:id:sgtin:0324478.532204.0000047856</epc>
          <epc>urn:epc:id:sgtin:0324478.532204.0000082614</epc>
        </epcList>
        <action>OBSERVE</action>
        <bizStep>urn:epcglobal:cbv:bizstep:shipping</bizStep>
        <disposition>urn:epcglobal:cbv:disp:in_transit</disposition>
        <readPoint>
          <id>urn:epc:id:sgln:0327808.00000.0</id>
        </readPoint>
        <bizLocation>
          <id>urn:epc:id:sgln:0327808.00000.0</id>
        </bizLocation>
        <bizTransactionList>
          <bizTransaction type="urn:epcglobal:cbv:btt:po">56343</bizTransaction>
          <bizTransaction type="urn:epcglobal:cbv:btt:desadv">56343</bizTransaction>
        </bizTransactionList>
      </ObjectEvent>""" + self.xml_footer
        
        # Create a complete sequence XML with valid SGTINs and proper event ordering
        self.complete_sequence_xml = self.xml_header + """
      <ObjectEvent>
        <eventTime>2025-02-08T08:00:00Z</eventTime>
        <eventTimeZoneOffset>+00:00</eventTimeZoneOffset>
        <epcList>
          <epc>urn:epc:id:sgtin:0324478.532204.0000065002</epc>
          <epc>urn:epc:id:sgtin:0324478.532204.0000047856</epc>
          <epc>urn:epc:id:sgtin:0324478.532204.0000082614</epc>
        </epcList>
        <action>ADD</action>
        <bizStep>urn:epcglobal:cbv:bizstep:commissioning</bizStep>
        <disposition>urn:epcglobal:cbv:disp:active</disposition>
        <readPoint>
          <id>urn:epc:id:sgln:0327808.00000.0</id>
        </readPoint>
        <bizLocation>
          <id>urn:epc:id:sgln:0327808.00000.0</id>
        </bizLocation>
        <ilmd>
          <lotNumber>56343</lotNumber>
          <itemExpirationDate>2026-01-31</itemExpirationDate>
          <productionDate>2025-01-31</productionDate>
        </ilmd>
      </ObjectEvent>
      <AggregationEvent>
        <eventTime>2025-02-08T09:00:00Z</eventTime>
        <eventTimeZoneOffset>+00:00</eventTimeZoneOffset>
        <parentID>urn:epc:id:sscc:0324478.0000000001</parentID>
        <childEPCs>
          <epc>urn:epc:id:sgtin:0324478.532204.0000065002</epc>
          <epc>urn:epc:id:sgtin:0324478.532204.0000047856</epc>
          <epc>urn:epc:id:sgtin:0324478.532204.0000082614</epc>
        </childEPCs>
        <action>ADD</action>
        <bizStep>urn:epcglobal:cbv:bizstep:packing</bizStep>
        <disposition>urn:epcglobal:cbv:disp:in_progress</disposition>
        <readPoint>
          <id>urn:epc:id:sgln:0327808.00000.0</id>
        </readPoint>
        <bizLocation>
          <id>urn:epc:id:sgln:0327808.00000.0</id>
        </bizLocation>
      </AggregationEvent>
      <ObjectEvent>
        <eventTime>2025-02-08T10:00:47Z</eventTime>
        <eventTimeZoneOffset>+00:00</eventTimeZoneOffset>
        <epcList>
          <epc>urn:epc:id:sscc:0324478.0000000001</epc>
        </epcList>
        <action>OBSERVE</action>
        <bizStep>urn:epcglobal:cbv:bizstep:shipping</bizStep>
        <disposition>urn:epcglobal:cbv:disp:in_transit</disposition>
        <readPoint>
          <id>urn:epc:id:sgln:0327808.00000.0</id>
        </readPoint>
        <bizLocation>
          <id>urn:epc:id:sgln:0327808.00000.0</id>
        </bizLocation>
        <bizTransactionList>
          <bizTransaction type="urn:epcglobal:cbv:btt:po">56343</bizTransaction>
          <bizTransaction type="urn:epcglobal:cbv:btt:desadv">56343</bizTransaction>
        </bizTransactionList>
      </ObjectEvent>""" + self.xml_footer
    
    def test_missing_commissioning(self):
        """Test that validator flags shipping without commissioning"""
        # Create XML with shipping but no commissioning
        xml_content = self.shipping_only_xml.encode('utf-8')
        
        # Validate the XML - using validate_document instead of validate
        result = self.validator.validate_document(xml_content, is_xml=True)
        
        # Check that validation fails
        self.assertFalse(result['valid'], "Validation should fail for shipping without commissioning")
        
        # Check for specific sequence errors or events out of order
        all_errors = result['errors']
        print("\nValidation errors for shipping without commissioning:")
        for error in all_errors:
            print(f" - {error.get('type')}: {error.get('message')}")
            
        # Look for event timing/sequence errors specifically related to aggregation events being out of order
        sequence_errors = [e for e in all_errors if 
                         (e.get('type') == 'sequence' and 
                          ('sequence' in e.get('message', '').lower() or
                           'before' in e.get('message', '').lower() or
                           'aggregation' in e.get('message', '').lower() or
                           'without being commissioned' in e.get('message', '').lower() or
                           'not commissioned before' in e.get('message', '').lower() or
                           'without required predecessor' in e.get('message', '').lower()))]
                          
        self.assertTrue(len(sequence_errors) > 0, "Should have sequence errors")
        
        # Updated to match actual error messages - check for updated error format
        has_missing_commissioning = any(
            ('not commissioned before' in e.get('message', '').lower() or
             'without required predecessor' in e.get('message', '').lower() or
             'without being commissioned' in e.get('message', '').lower())
            for e in sequence_errors
        )
        
        self.assertTrue(has_missing_commissioning, "Should have error about shipping without commissioning")
    
    def test_direct_event_timing(self):
        """Test the sequence validator directly with out of sequence events"""
        # Create test events with shipping but no commissioning
        events = [{
            'eventTime': '2025-02-08T10:00:47Z',
            'bizStep': 'urn:epcglobal:cbv:bizstep:shipping',  # Use full URN format
            'epcList': [
                'urn:epc:id:sgtin:0324478.532204.0000065002',
                'urn:epc:id:sgtin:0324478.532204.0000047856'
            ]
        }]
        
        # Call sequence validator directly through the main validator
        timing_errors = self.validator.sequence_validator.validate_sequence(events)
        
        # Print results
        print("\nDirect validation timing errors:")
        for error in timing_errors:
            print(f" - {error.get('message')}")
        
        # Check that we have at least one sequence error
        sequence_errors = [e for e in timing_errors if e.get('type') == 'sequence']
        self.assertTrue(len(sequence_errors) > 0, "Should have sequence errors")
        
        # Check for sequence errors - updated to match new error formats
        has_commissioning_error = any(
            ('commissioning' in err.get('message', '').lower() or 
             'not commissioned' in err.get('message', '').lower() or
             'predecessor' in err.get('message', '').lower())
            for err in sequence_errors
        )
        self.assertTrue(has_commissioning_error, "Should have error about missing commissioning event")
    
    def test_nonstandard_format(self):
        """Test that our validator rejects the non-standard format like the example"""
        nonstandard_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ttt:itemsShipEvent xmlns:eee="http://xmlns.rfxcel.com/events/1.4.2" xmlns:ttt="http://xmlns.rfxcel.com/traceabilityEvents/1.4.2" xmlns:dis="http://xmlns.rfxcel.com/1.4.2">
    <eee:eventTpId qlfr="EXTERNAL_DEF">urn:epc:id:sgln:0327808.00000.0</eee:eventTpId>
    <eee:eventDateTime>2025-02-08T10:00:47Z</eee:eventDateTime>
    <ttt:bizTxnInfoList>
        <eee:bizTxnInfo bizTxnType="Purchase Order Number">
            <eee:bizTxnId>56343</eee:bizTxnId>
            <eee:bizTxnTypeExtId>urn:epcglobal:cbv:btt:po</eee:bizTxnTypeExtId>
        </eee:bizTxnInfo>
    </ttt:bizTxnInfoList>
    <ttt:traceableEntityList>
        <eee:itemAggr>
            <eee:itemInfo>
                <eee:itemId qlfr="SGTIN">urn:epc:id:sgtin:0324478.532204.0000065002</eee:itemId>
            </eee:itemInfo>
            <eee:itemInfo>
                <eee:itemId qlfr="SGTIN">urn:epc:id:sgtin:0324478.532204.0000047856</eee:itemId>
            </eee:itemInfo>
        </eee:itemAggr>
    </ttt:traceableEntityList>
</ttt:itemsShipEvent>"""
        
        # Validate the XML - using validate_document instead of validate
        result = self.validator.validate_document(nonstandard_xml.encode('utf-8'), is_xml=True)
        
        # Check that validation fails
        self.assertFalse(result['valid'], "Validation should fail for non-standard format")
        
        # Print all errors for inspection
        print("\nNon-standard format validation errors:")
        for error in result['errors']:
            print(f" - {error.get('type')}: {error.get('message')}")
        
        # Check for structure errors specifically
        structure_errors = [e for e in result['errors'] if e.get('type') == 'structure']
        self.assertTrue(len(structure_errors) > 0, "Should have structure errors")
        
        # Updated to check for Missing EPCIS namespace - the error this test is checking for
        has_epcis_namespace_error = any('Missing EPCIS namespace' in e.get('message', '') for e in structure_errors)
        self.assertTrue(has_epcis_namespace_error, "Should flag missing EPCIS namespace")

if __name__ == '__main__':
    unittest.main()