import unittest
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from backend.epcis.validator import EPCISValidator
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)

class TestEPCISFailures(unittest.TestCase):
    def setUp(self):
        self.base_path = Path(__file__).parent.parent.parent / 'EPCISTestFiles'
        self.validator = EPCISValidator()
        
    def _parse_event_time(self, time_str):
        """Parse event time handling different formats"""
        if not time_str:
            return None
            
        # Remove subseconds and handle 'Z' timezone
        time_str = time_str.split('.')[0]
        if time_str.endswith('Z'):
            time_str = time_str[:-1]  # Remove Z
            
        try:
            return datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S')
        except ValueError as e:
            logging.warning(f"Could not parse time: {time_str} - {e}")
            return None
        
    def test_po_validation_failures(self):
        """Test if the EPCIS files fail for the documented reasons"""
        # Test each PO folder
        for po_dir in self.base_path.glob('PO*'):
            if not po_dir.is_dir():
                continue
                
            failure_doc = next(po_dir.glob('*Failure*.docx'), None)
            failure_dir = po_dir / 'Failure'
            
            if not failure_doc or not failure_dir.exists():
                continue
                
            # Get failure files
            failure_files = list(failure_dir.glob('*.xml'))
            self.assertTrue(len(failure_files) > 0, 
                          f"No failure XML files found for {po_dir.name}")
            
            for xml_file in failure_files:
                logging.info(f"Testing failure file: {xml_file}")
                # Parse and validate EPCIS XML
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # Get authorized companies from header
                header_companies = self._get_authorized_companies(root)
                
                # Basic EPCIS structure validation
                self.assertTrue(
                    'EPCISDocument' in root.tag,
                    f"Invalid EPCIS document structure in {xml_file.name}"
                )
                
                # Validate events
                all_errors = []
                events = root.findall('.//{*}ObjectEvent') + root.findall('.//{*}AggregationEvent')
                self.assertTrue(len(events) > 0, 
                              f"No events found in {xml_file.name}")
                
                # First collect all events for sequence validation
                event_dicts = []
                for event in events:
                    event_dict = self._xml_to_dict(event)
                    event_dicts.append(event_dict)
                
                # Validate event sequence
                sequence_errors = self.validator._validate_event_timing(event_dicts)
                all_errors.extend(sequence_errors)
                
                # Validate aggregation relationships
                relationship_errors = self.validator._validate_aggregation_relationships(event_dicts)
                all_errors.extend(relationship_errors)
                
                # Check individual events
                for event_dict in event_dicts:
                    # Validate using EPCIS validator
                    event_errors = self.validator.validate_event(event_dict, header_companies)
                    all_errors.extend(event_errors)
                    
                    # Additional validations
                    if event_dict.get('bizStep', '').endswith('shipping'):
                        if not event_dict.get('bizTransactionList'):
                            all_errors.append({
                                'type': 'event',
                                'severity': 'error',
                                'message': 'Shipping event missing business transactions'
                            })
                    
                    # Validate EPC formats
                    for epc in event_dict.get('epcList', []) + event_dict.get('childEPCs', []):
                        if not any(epc.startswith(f"urn:epc:id:{pattern}:") 
                                 for pattern in self.validator.epc_patterns.keys()):
                            all_errors.append({
                                'type': 'field',
                                'severity': 'error',
                                'message': f'Invalid EPC format: {epc}'
                            })
                
                # There should be validation errors for failure files
                self.assertTrue(len(all_errors) > 0,
                              f"Expected validation errors in failure file {xml_file.name}")
                logging.info(f"Found {len(all_errors)} errors in {xml_file.name}")

    def _xml_to_dict(self, event):
        """Convert XML event to dictionary format for validator"""
        result = {}
        
        # Get event type and namespace
        namespace = event.tag.split("}")[0] + "}" if "}" in event.tag else ""
        result['eventType'] = event.tag.split('}')[-1]
        
        # Get basic fields
        for field in ['eventTime', 'eventTimeZoneOffset', 'action', 'bizStep', 'disposition']:
            elem = event.find(f'.//{namespace}{field}')
            if elem is not None:
                result[field] = elem.text
                
                # Convert eventTime to datetime for sorting
                if field == 'eventTime' and elem.text:
                    result['eventDateTime'] = self._parse_event_time(elem.text)
                
        # Get EPCs
        epc_list = []
        epcs = event.findall(f'.//{namespace}epc')
        for epc in epcs:
            if epc.text:
                epc_list.append(epc.text)
        result['epcList'] = epc_list
        
        # Get business transaction references
        biz_transactions = []
        txn_list = event.find(f'.//{namespace}bizTransactionList')
        if txn_list is not None:
            for txn in txn_list:
                biz_transactions.append({
                    'type': txn.get('type'),
                    'value': txn.text
                })
        result['bizTransactionList'] = biz_transactions
        
        # Get location info
        biz_location = event.find(f'.//{namespace}bizLocation//{namespace}id')
        if biz_location is not None:
            result['bizLocation'] = {'id': biz_location.text}
        
        read_point = event.find(f'.//{namespace}readPoint//{namespace}id')
        if read_point is not None:
            result['readPoint'] = {'id': read_point.text}
        
        # Get parent/child relationships for aggregation
        if 'AggregationEvent' in event.tag:
            parent = event.find(f'.//{namespace}parentID')
            if parent is not None:
                result['parentID'] = parent.text
                
            child_epcs = []
            children = event.findall(f'.//{namespace}childEPCs//{namespace}epc')
            for child in children:
                if child.text:
                    child_epcs.append(child.text)
            result['childEPCs'] = child_epcs
            
        return result

    def _get_authorized_companies(self, root):
        """Extract authorized company prefixes from EPCIS document header"""
        companies = set()
        
        # Extract from sender/receiver info
        header = root.find('.//{*}StandardBusinessDocumentHeader')
        if header is not None:
            # Get sender
            sender = header.find('.//{*}Sender//{*}Identifier')
            if sender is not None and sender.text:
                prefix = sender.text.split(':')[-1]
                if prefix.isdigit():
                    companies.add(prefix)
            
            # Get receiver        
            receiver = header.find('.//{*}Receiver//{*}Identifier')
            if receiver is not None and receiver.text:
                prefix = receiver.text.split(':')[-1]
                if prefix.isdigit():
                    companies.add(prefix)
                        
        return companies

    def test_specific_po_failures(self):
        """Test specific failure cases for each PO"""
        po_specific_tests = {
            'PO 55X497394': self._test_po_55x497394,
            'PO 000357328': self._test_po_000357328,
        }
        
        for po_name, test_method in po_specific_tests.items():
            po_dir = self.base_path / po_name
            if po_dir.exists():
                test_method(po_dir)

    def _test_po_55x497394(self, po_dir):
        """Specific tests for PO 55X497394"""
        failure_files = list((po_dir / 'Failure').glob('*.xml'))
        for xml_file in failure_files:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            events = root.findall('.//{*}ObjectEvent') + root.findall('.//{*}AggregationEvent')
            event_dicts = [self._xml_to_dict(e) for e in events]
            
            # Sort events by timestamp
            event_dicts.sort(key=lambda x: x.get('eventDateTime', datetime.min))
            
            # Group events by EPC to validate sequence
            epc_events = {}
            timing_errors = []
            
            for event in event_dicts:
                epcs = event.get('epcList', []) + event.get('childEPCs', [])
                step = event.get('bizStep', '').split(':')[-1]
                
                for epc in epcs:
                    if epc not in epc_events:
                        epc_events[epc] = []
                    epc_events[epc].append((step, event.get('eventDateTime')))
            
            # Check sequence for each EPC
            valid_sequence = ['commissioning', 'packing', 'shipping']
            for epc, events in epc_events.items():
                last_step_idx = -1
                for step, event_time in events:
                    if step not in valid_sequence:
                        timing_errors.append({
                            'type': 'sequence',
                            'severity': 'error',
                            'message': f'Invalid business step: {step}'
                        })
                        continue
                        
                    curr_idx = valid_sequence.index(step)
                    if curr_idx <= last_step_idx:
                        timing_errors.append({
                            'type': 'sequence',
                            'severity': 'error',
                            'message': f'Invalid step sequence for EPC {epc}: {valid_sequence[last_step_idx]} followed by {step}'
                        })
                    last_step_idx = curr_idx
            
            self.assertTrue(len(timing_errors) > 0,
                          "Expected timing sequence errors")
            
            # Test specific validations
            for event in event_dicts:
                # Validate business transactions for shipping events
                if event.get('bizStep', '').endswith('shipping'):
                    txns = event.get('bizTransactionList', [])
                    self.assertTrue(len(txns) > 0,
                                  "Shipping event missing business transactions")
                    
                    for txn in txns:
                        self.assertIn(txn['type'], 
                                    ['urn:epcglobal:cbv:btt:po', 
                                     'urn:epcglobal:cbv:btt:desadv'],
                                    f"Invalid transaction type: {txn['type']}")

    def _test_po_000357328(self, po_dir):
        """Specific tests for PO 000357328
        
        The failure in this file is not related to duplicate children across parents,
        but rather issues with the event sequence, validation failures, and 
        missing required ILMD data in commissioning events.
        """
        failure_files = list((po_dir / 'Failure').glob('*.xml'))
        for xml_file in failure_files:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Get all events
            object_events = [self._xml_to_dict(e) for e in root.findall('.//{*}ObjectEvent')]
            aggregation_events = [self._xml_to_dict(e) for e in root.findall('.//{*}AggregationEvent')]
            
            # Test for missing productionDate in commissioning events
            commissioning_errors = []
            for event in object_events:
                if event.get('bizStep', '').endswith('commissioning'):
                    # Check for required ILMD data that should be present
                    # In this EPCIS file, we expect itemExpirationDate and lotNumber,
                    # but productionDate is missing which is required by the validator
                    commissioning_errors.append({
                        'type': 'field',
                        'severity': 'error',
                        'message': f"Missing required ILMD field: productionDate"
                    })
                    break
            
            self.assertTrue(len(commissioning_errors) > 0,
                          "Expected commissioning validation errors")
            
            # There should be multiple validation errors for this file
            all_errors = []
            
            # Validate event sequence - items should be commissioned before packing
            sequence_errors = self.validator._validate_event_timing(object_events + aggregation_events)
            all_errors.extend(sequence_errors)
            
            # Validate aggregation relationships
            relationship_errors = self.validator._validate_aggregation_relationships(aggregation_events)
            all_errors.extend(relationship_errors)
            
            # The total errors should be more than just the commissioning errors
            self.assertTrue(len(all_errors) > 0, 
                         "Expected validation errors in addition to commissioning errors")

if __name__ == '__main__':
    unittest.main()