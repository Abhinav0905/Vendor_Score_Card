import re
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from collections import defaultdict
import xml.etree.ElementTree as ET
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EPCISValidator:
    """Validator for EPCIS files and events"""
    
    def __init__(self):
        # EPC URN patterns for validation
        self.epc_patterns = {
            'sgtin': r'^urn:epc:id:sgtin:\d+\.[0-9]+\.*[0-9]*$',
            'sscc': r'^urn:epc:id:sscc:\d+\.[0-9]+$',
            'sgln': r'^urn:epc:id:sgln:\d+\.[0-9]+\.*[0-9]*$',
            'grai': r'^urn:epc:id:grai:\d+\.[0-9]+\.*[0-9]*$',
            'giai': r'^urn:epc:id:giai:\d+\.*[0-9]+$',
        }
        
        # Valid business steps from CBV (Core Business Vocabulary)
        self.valid_biz_steps = {
            'accepting', 'arriving', 'collecting', 'commissioning', 'consigning',
            'creating_class_instance', 'cycle_counting', 'decommissioning',
            'departing', 'destroying', 'dispensing', 'encoding', 'entering_exiting',
            'holding', 'inspecting', 'installing', 'killing', 'loading', 'other',
            'packing', 'picking', 'receiving', 'removing', 'repackaging',
            'repairing', 'replacing', 'reserving', 'retail_selling', 'shipping',
            'staging_outbound', 'stock_taking', 'stocking', 'storing', 'transporting',
            'unloading', 'void_shipping'
        }
        
        # Valid actions
        self.valid_actions = {'ADD', 'OBSERVE', 'DELETE'}
    
    def validate(self, file_content: bytes, is_xml: bool = True) -> Dict[str, Any]:
        """Validate EPCIS file content
        
        Args:
            file_content: Raw content of the EPCIS file
            is_xml: Whether the content is XML (True) or JSON (False)
            
        Returns:
            Dict containing validation results
        """
        errors = []
        
        try:
            # Parse and validate format
            if is_xml:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(file_content)
                events = self._extract_xml_events(root)
            else:
                import json
                data = json.loads(file_content)
                events = data.get('eventList', [])
            
            # Validate each event
            for event in events:
                event_errors = self._validate_event(event)
                errors.extend(event_errors)
            
            return {
                'valid': len([e for e in errors if e.get('severity') == 'error']) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                'valid': False,
                'errors': [{
                    'type': 'format',
                    'severity': 'error',
                    'message': f"Invalid file format: {str(e)}"
                }]
            }
    
    def _validate_event(self, event: Dict[str, Any]) -> List[Dict[str, str]]:
        """Validate an individual EPCIS event
        
        Args:
            event: Dict containing event data
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check required fields
        required_fields = ['eventTime', 'eventTimeZoneOffset']
        for field in required_fields:
            if not event.get(field):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': f"Missing required field: {field}"
                })
        
        # Validate eventTime format
        event_time = event.get('eventTime')
        if event_time:
            try:
                datetime.strptime(event_time, "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                try:
                    datetime.strptime(event_time, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    errors.append({
                        'type': 'field',
                        'severity': 'error',
                        'message': "Invalid eventTime format"
                    })
        
        # Validate timezone offset format
        tz_offset = event.get('eventTimeZoneOffset')
        if tz_offset and not re.match(r'^[+-]\d{2}:00$', tz_offset):
            errors.append({
                'type': 'field',
                'severity': 'error',
                'message': "Invalid eventTimeZoneOffset format"
            })
        
        # Validate action
        action = event.get('action')
        if action and action not in self.valid_actions:
            errors.append({
                'type': 'field',
                'severity': 'error',
                'message': f"Invalid action: {action}"
            })
        
        # Validate business step
        biz_step = event.get('bizStep')
        if biz_step:
            biz_step_name = biz_step.split(':')[-1].lower()
            if biz_step_name not in self.valid_biz_steps:
                errors.append({
                    'type': 'field',
                    'severity': 'warning',
                    'message': f"Non-standard business step: {biz_step}"
                })
        
        # Validate EPCs
        epcs = event.get('epcList', [])
        for epc in epcs:
            if not self._validate_epc(epc):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': f"Invalid EPC format: {epc}"
                })
        
        # Validate read point and business location
        read_point = event.get('readPoint', {}).get('id')
        if read_point and not self._validate_epc(read_point):
            errors.append({
                'type': 'field',
                'severity': 'warning',
                'message': f"Invalid readPoint format: {read_point}"
            })
        
        biz_location = event.get('bizLocation', {}).get('id')
        if biz_location and not self._validate_epc(biz_location):
            errors.append({
                'type': 'field',
                'severity': 'warning',
                'message': f"Invalid bizLocation format: {biz_location}"
            })
        
        return errors
    
    def _validate_epc(self, epc: str) -> bool:
        """Validate an EPC URN format
        
        Args:
            epc: EPC URN string to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not epc.startswith('urn:epc:id:'):
            return False
            
        for pattern in self.epc_patterns.values():
            if re.match(pattern, epc):
                return True
                
        return False
    
    def _extract_xml_events(self, root) -> List[Dict[str, Any]]:
        """Extract events from XML root element
        
        Args:
            root: XML root element
            
        Returns:
            List of event dictionaries
        """
        events = []
        
        # Remove namespace for easier parsing
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]
        
        # Extract events
        for event_type in ['ObjectEvent', 'AggregationEvent', 'TransactionEvent', 'TransformationEvent']:
            for event_elem in root.findall(f'.//{event_type}'):
                event = {}
                
                # Extract basic fields
                for field in ['eventTime', 'eventTimeZoneOffset', 'action', 'bizStep', 'disposition']:
                    value = event_elem.findtext(field)
                    if value:
                        event[field] = value
                
                # Extract EPCs
                epc_list = event_elem.find('epcList')
                if epc_list is not None:
                    event['epcList'] = [epc.text for epc in epc_list.findall('epc')]
                
                # Extract locations
                read_point = event_elem.find('readPoint/id')
                if read_point is not None:
                    event['readPoint'] = {'id': read_point.text}
                
                biz_location = event_elem.find('bizLocation/id')
                if biz_location is not None:
                    event['bizLocation'] = {'id': biz_location.text}
                
                events.append(event)
        
        return events