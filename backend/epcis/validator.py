import re
import logging
from typing import Dict, List, Tuple, Optional, Any, Set
from datetime import datetime
from collections import defaultdict
import xml.etree.ElementTree as ET
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EPCISValidator:
    """Validator for EPCIS files and events"""
    
    # Valid event sequence steps
    EVENT_SEQUENCE = ['commissioning', 'packing', 'shipping']
    
    def __init__(self):
        # Previous patterns remain unchanged
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
        
        # Packaging levels for event ordering validation
        self.packaging_levels = {
            'SKU': 1,      # Base level
            'CASE': 2,     # Secondary packaging
            'PALLET': 3    # Tertiary packaging
        }
        
        # Event sequence rules - defines valid predecessor events
        self.event_sequence_rules = {
            'commissioning': [],  # No prerequisites
            'packing': ['commissioning'],
            'shipping': ['packing', 'commissioning'],
            'receiving': ['shipping'],
            'storing': ['receiving', 'commissioning']
        }
        
        # Required elements for each event type, updated for flexible parentID
        self.required_elements = {
            'ObjectEvent': ['eventTime', 'eventTimeZoneOffset', 'epcList', 'action'],
            'AggregationEvent': ['eventTime', 'eventTimeZoneOffset', 'childEPCs', 'action'],  # parentID not always required
            'TransactionEvent': ['eventTime', 'eventTimeZoneOffset', 'bizTransactionList', 'epcList', 'action'],
            'TransformationEvent': ['eventTime', 'eventTimeZoneOffset', 'inputEPCList', 'outputEPCList'],
        }
        
        # Valid dispositions from CBV
        self.valid_dispositions = {
            'active', 'container_closed', 'damaged', 'destroyed', 'dispensed', 
            'disposed', 'encoded', 'expired', 'in_progress', 'in_transit', 'inactive', 
            'no_pedigree_match', 'non_sellable_other', 'partially_dispensed', 'recalled', 
            'reserved', 'retail_sold', 'returned', 'sellable_accessible', 
            'sellable_not_accessible', 'stolen', 'unknown', 'available', 'unavailable'
        }
        
        # Known valid product codes (from master data)
        self.valid_product_codes = {
            '0327808.023302', '0327808.026601',
            '0327808.315801', '0327808.323401',
        }
        
        # Track commissioned items for packaging hierarchy validation
        self.commissioned_items = {
            'SKU': set(),
            'CASE': set(),
            'PALLET': set()
        }
        
        # Track event sequence for validation
        self.event_sequence = []

        # Define packaging level transitions
        self.packaging_transitions = {
            'SKU_TO_CASE': {
                'parent_type': 'sscc',
                'child_type': 'sgtin',
                'max_children': 500  # Example limit
            },
            'CASE_TO_PALLET': {
                'parent_type': 'sscc',
                'child_type': 'sscc',
                'max_children': 50   # Example limit
            }
        }
        
        # Track commissioned and aggregated items
        self.commissioned_items: Dict[str, Set[str]] = {
            'SGTIN': set(),  # Track commissioned SGTINs
            'SSCC': set(),   # Track commissioned SSCCs
        }
        
        self.aggregated_items: Dict[str, str] = {}  # child_epc -> parent_epc
        
        # Track ILMD data for commissioned items
        self.ilmd_data: Dict[str, Dict[str, Any]] = {}
        
        # Initialize event sequence tracking
        self.event_sequence = []
        
        # Known product codes (from master data)
        self.valid_product_codes = {
            '0327808.023302', '0327808.026601',
            '0327808.315801', '0327808.323401',
        }

        # Add new validation rules
        self.required_shipping_fields = {
            'sourceList': ['owning_party', 'location'],
            'destinationList': ['owning_party', 'location']
        }

        self.required_transaction_types = {
            'shipping': ['urn:epcglobal:cbv:btt:po', 'urn:epcglobal:cbv:btt:desadv']
        }

    def calculate_gs1_check_digit(self, number_str: str) -> str:
        """Calculate GS1 check digit for a number string
        
        Args:
            number_str: String of digits to calculate check digit for
            
        Returns:
            Check digit as string
        """
        # Reverse the string to start from right
        total = 0
        for i, digit in enumerate(reversed(number_str)):
            multiplier = 3 if i % 2 == 0 else 1
            total += int(digit) * multiplier
        
        check_digit = (10 - (total % 10)) % 10
        return str(check_digit)

    def validate_gs1_check_digit(self, full_number: str) -> bool:
        """Validate GS1 check digit in a number
        
        Args:
            full_number: Complete number including check digit
            
        Returns:
            True if check digit is valid
        """
        if not full_number.isdigit():
            return False
            
        number = full_number[:-1]  # All but last digit
        check_digit = full_number[-1]  # Last digit
        
        return self.calculate_gs1_check_digit(number) == check_digit

    def _validate_sgtin_attributes(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Validate required attributes for SGTIN commissioning
        
        Args:
            event: Event dictionary
            errors: List to append any validation errors to
        """
        if (event.get('bizStep', '').endswith('commissioning') and 
            any(epc.startswith('urn:epc:id:sgtin:') for epc in event.get('epcList', []))):
            
            # Check for lot number
            ilmd = event.get('ilmd', {})
            if not ilmd.get('lotNumber'):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': "Missing lotNumber for SGTIN commissioning"
                })
            
            # Check for expiration date
            if not ilmd.get('itemExpirationDate'):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': "Missing itemExpirationDate for SGTIN commissioning"
                })
            else:
                # Validate expiration date format
                try:
                    expdate = ilmd['itemExpirationDate']
                    datetime.strptime(expdate, "%Y-%m-%d")
                except ValueError:
                    errors.append({
                        'type': 'field',
                        'severity': 'error',
                        'message': f"Invalid itemExpirationDate format: {expdate}. Expected YYYY-MM-DD"
                    })

    def _validate_packaging_hierarchy(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Validate packaging hierarchy and event ordering
        
        Args:
            event: Event dictionary
            errors: List to append any validation errors to
        """
        event_type = event.get('eventType')
        biz_step = event.get('bizStep', '').split(':')[-1]
        
        if event_type == 'ObjectEvent' and biz_step == 'commissioning':
            # Determine packaging level from EPC type
            epcs = event.get('epcList', [])
            for epc in epcs:
                if epc.startswith('urn:epc:id:sgtin:'):
                    self.commissioned_items['SKU'].add(epc)
                elif epc.startswith('urn:epc:id:sscc:'):
                    # Determine if CASE or PALLET based on additional attributes or context
                    # For this example, we'll assume CASE
                    self.commissioned_items['CASE'].add(epc)
        
        elif event_type == 'AggregationEvent' and event.get('action') == 'ADD':
            parent_id = event.get('parentID')
            child_epcs = event.get('childEPCs', [])
            
            # Check if all child items were commissioned
            for child in child_epcs:
                if (child not in self.commissioned_items['SKU'] and 
                    child not in self.commissioned_items['CASE']):
                    errors.append({
                        'type': 'sequence',
                        'severity': 'error',
                        'message': f"Item {child} not commissioned before aggregation"
                    })
            
            # Validate aggregation level
            if parent_id and parent_id.startswith('urn:epc:id:sscc:'):
                if any(child.startswith('urn:epc:id:sgtin:') for child in child_epcs):
                    # SKUs into CASE
                    for child in child_epcs:
                        if child not in self.commissioned_items['SKU']:
                            errors.append({
                                'type': 'sequence',
                                'severity': 'error',
                                'message': f"SKU {child} must be commissioned before case aggregation"
                            })
                elif any(child.startswith('urn:epc:id:sscc:') for child in child_epcs):
                    # CASEs into PALLET
                    for child in child_epcs:
                        if child not in self.commissioned_items['CASE']:
                            errors.append({
                                'type': 'sequence',
                                'severity': 'error',
                                'message': f"Case {child} must be commissioned before pallet aggregation"
                            })

    def validate(self, file_content: bytes, is_xml: bool = True) -> Dict[str, Any]:
        """Validate EPCIS file content
        
        Args:
            file_content: Raw content of the EPCIS file
            is_xml: Whether the content is XML (True) or JSON (False)
            
        Returns:
            Dict containing validation results
        """
        errors = []
        products_in_doc = set()
        
        try:
            # Parse and validate format
            if is_xml:
                try:
                    import xml.etree.ElementTree as ET
                    
                    # Try to parse XML and check for well-formedness
                    try:
                        root = ET.fromstring(file_content)
                    except ET.ParseError as xml_error:
                        logger.error(f"XML parsing error: {xml_error}")
                        return {
                            'valid': False,
                            'errors': [{
                                'type': 'format',
                                'severity': 'error',
                                'message': f"Invalid XML format: {str(xml_error)}"
                            }]
                        }
                    
                    # Extract product codes from master data for validation
                    master_product_codes = self._extract_master_product_codes(root)
                    if master_product_codes:
                        # Update our valid product codes with those found in the document's master data
                        self.valid_product_codes.update(master_product_codes)
                    
                    # Check for EPCIS namespace
                    namespaces = self._extract_namespaces(file_content.decode('utf-8'))
                    if not any('epcis' in ns.lower() for ns in namespaces):
                        errors.append({
                            'type': 'structure',
                            'severity': 'error',
                            'message': "Missing EPCIS namespace declaration"
                        })
                    
                    # Check for EPCISDocument root element
                    if 'EPCISDocument' not in str(root.tag):
                        errors.append({
                            'type': 'structure',
                            'severity': 'error',
                            'message': "Root element must be EPCISDocument"
                        })
                    
                    # Extract events
                    events = self._extract_xml_events(root)
                    
                    # Check event count
                    if not events:
                        logger.warning("No events found in XML document")
                        errors.append({
                            'type': 'structure',
                            'severity': 'error',
                            'message': "No EPCIS events found in the document"
                        })
                except Exception as e:
                    logger.exception(f"XML structure validation error: {e}")
                    errors.append({
                        'type': 'structure',
                        'severity': 'error',
                        'message': f"XML structure validation error: {str(e)}"
                    })
            else:
                try:
                    import json
                    
                    # Try to parse JSON
                    try:
                        data = json.loads(file_content)
                    except json.JSONDecodeError as json_error:
                        logger.error(f"JSON parsing error: {json_error}")
                        return {
                            'valid': False,
                            'errors': [{
                                'type': 'format',
                                'severity': 'error',
                                'message': f"Invalid JSON format: {str(json_error)}"
                            }]
                        }
                    
                    # Check for EPCIS context
                    if '@context' not in data or not any('epcis' in str(ctx).lower() for ctx in data.get('@context', [])):
                        errors.append({
                            'type': 'structure',
                            'severity': 'error',
                            'message': "Missing EPCIS context in JSON"
                        })
                    
                    # Check for events
                    events = data.get('eventList', [])
                    if not events:
                        logger.warning("No events found in JSON document")
                        errors.append({
                            'type': 'structure',
                            'severity': 'error',
                            'message': "Empty eventList in document"
                        })
                except Exception as e:
                    logger.exception(f"JSON structure validation error: {e}")
                    errors.append({
                        'type': 'structure',
                        'severity': 'error',
                        'message': f"JSON structure validation error: {str(e)}"
                    })
            
            # Validate each event
            for event in events:
                event_errors = self._validate_event(event)
                errors.extend(event_errors)
                
                # Collect product codes from SGTINs for validation
                self._collect_product_codes(event, products_in_doc)
                
            # Check for product code mismatches
            product_code_errors = self._validate_product_codes(products_in_doc)
            errors.extend(product_code_errors)
            
            # Validate sequence and relationships
            sequence_errors = self._validate_event_sequence(events)
            errors.extend(sequence_errors)
            
            # Determine overall validity - document is valid only if there are NO errors
            # (warnings are acceptable)
            is_valid = len([e for e in errors if e.get('severity') == 'error']) == 0
            
            return {
                'valid': is_valid,
                'errors': errors
            }
            
        except Exception as e:
            logger.exception(f"Validation error: {e}")
            return {
                'valid': False,
                'errors': [{
                    'type': 'format',
                    'severity': 'error',
                    'message': f"Invalid file format or unexpected error: {str(e)}"
                }]
            }
    
    def _extract_master_product_codes(self, root) -> set:
        """Extract product codes from vocabulary master data
        
        Args:
            root: XML root element
            
        Returns:
            Set of product codes
        """
        product_codes = set()
        
        try:
            # Remove namespace for easier parsing
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}', 1)[1]
            
            # Look for vocabulary elements of type EPCClass
            vocab_elements = root.findall('.//Vocabulary[@type="urn:epcglobal:epcis:vtype:EPCClass"]/VocabularyElementList/VocabularyElement')
            
            for element in vocab_elements:
                element_id = element.get('id', '')
                if element_id.startswith('urn:epc:idpat:sgtin:'):
                    # Extract the company prefix and item reference
                    parts = element_id.split(':')
                    if len(parts) >= 5:
                        product_code = parts[4].rsplit('.', 1)[0]  # Get everything before the last dot
                        product_codes.add(product_code)
        except Exception as e:
            logger.warning(f"Error extracting master product codes: {e}")
        
        return product_codes
    
    def _collect_product_codes(self, event: Dict[str, Any], products_set: set):
        """Collect product codes from event EPCs
        
        Args:
            event: Event dictionary
            products_set: Set to collect product codes into
        """
        # Process epcList
        epcs = event.get('epcList', [])
        for epc in epcs:
            if epc.startswith('urn:epc:id:sgtin:'):
                parts = epc.split(':')
                if len(parts) >= 5:
                    # Extract company prefix and item reference
                    epc_parts = parts[4].rsplit('.', 1)
                    if len(epc_parts) >= 1:
                        products_set.add(epc_parts[0])
        
        # Process childEPCs
        child_epcs = event.get('childEPCs', [])
        if isinstance(child_epcs, list):
            for epc in child_epcs:
                if epc.startswith('urn:epc:id:sgtin:'):
                    parts = epc.split(':')
                    if len(parts) >= 5:
                        epc_parts = parts[4].rsplit('.', 1)
                        if len(epc_parts) >= 1:
                            products_set.add(epc_parts[0])
    
    def _validate_product_codes(self, product_codes: set) -> List[Dict[str, str]]:
        """Validate that product codes match expected values
        
        Args:
            product_codes: Set of product codes found in document
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Skip validation if no product codes were found
        if not product_codes:
            return errors
            
        # Check for unexpected product codes
        for code in product_codes:
            # Look for valid SGTIN formats that don't match our known products
            if code not in self.valid_product_codes:
                errors.append({
                    'type': 'sequence',
                    'severity': 'error',
                    'message': f"Unexpected product code found: {code}. This may cause aggregation conflicts."
                })
        
        return errors

    def _extract_namespaces(self, xml_string: str) -> List[str]:
        """Extract namespace declarations from XML string
        
        Args:
            xml_string: XML document as string
            
        Returns:
            List of namespace URIs
        """
        ns_matches = re.findall(r'xmlns(?:\:\w+)?=[\"\']([^\"\']+)[\"\']', xml_string)
        return ns_matches
    
    def _validate_event(self, event: Dict[str, Any]) -> List[Dict[str, str]]:
        """Validate an individual EPCIS event"""
        errors = []
        
        # Basic validation
        if not event:
            errors.append({
                'type': 'structure',
                'severity': 'error',
                'message': "Empty event found"
            })
            return errors
        
        # Determine event type and validate required fields
        event_type = event.get('eventType', '')
        if not event_type and 'action' in event and 'epcList' in event:
            event_type = 'ObjectEvent'
        
        # Validate required fields based on event type
        if event_type in self.required_elements:
            for field in self.required_elements[event_type]:
                # Special handling for parentID in AggregationEvent
                if field == 'parentID' and event_type == 'AggregationEvent':
                    if event.get('action') == 'ADD' and not event.get(field):
                        errors.append({
                            'type': 'field',
                            'severity': 'error',
                            'message': f"parentID required for ADD AggregationEvent"
                        })
                elif not event.get(field):
                    errors.append({
                        'type': 'field',
                        'severity': 'error',
                        'message': f"Missing required field for {event_type}: {field}"
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
                        'message': f"Invalid eventTime format: {event_time}"
                    })
        
        # Validate timezone offset
        tz_offset = event.get('eventTimeZoneOffset')
        if tz_offset and not re.match(r'^[+-]\d{2}:00$', tz_offset):
            errors.append({
                'type': 'field',
                'severity': 'error',
                'message': f"Invalid eventTimeZoneOffset format: {tz_offset}"
            })
        
        # Validate EPCs and check digits
        epcs = event.get('epcList', [])
        if epcs:
            if not isinstance(epcs, list):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': "epcList must be an array"
                })
            else:
                for epc in epcs:
                    if not self._validate_epc(epc):
                        errors.append({
                            'type': 'field',
                            'severity': 'error',
                            'message': f"Invalid EPC format: {epc}"
                        })
                    else:
                        # Validate check digit for SGTINs
                        if epc.startswith('urn:epc:id:sgtin:'):
                            parts = epc.split(':')[4].split('.')
                            if len(parts) >= 2:
                                number = parts[0] + parts[1]
                                if not self.validate_gs1_check_digit(number):
                                    errors.append({
                                        'type': 'field',
                                        'severity': 'error',
                                        'message': f"Invalid GS1 check digit in SGTIN: {epc}"
                                    })
        
        # Validate SGTIN commissioning attributes
        self._validate_sgtin_attributes(event, errors)
        
        # Validate packaging hierarchy and event sequence
        self._validate_packaging_hierarchy(event, errors)
        
        # Add event to sequence for later validation
        self.event_sequence.append({
            'type': event_type,
            'bizStep': event.get('bizStep', ''),
            'action': event.get('action', ''),
            'time': event_time
        })
        
        return errors
    
    def _validate_event_sequence(self, events: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Validate sequence relationships between events
        
        Args:
            events: List of EPCIS events
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Skip if less than 2 events
        if len(events) < 2:
            return []
        
        # Check for timeorder - events should be in chronological order
        last_event_time = None
        for i, event in enumerate(events):
            event_time = event.get('eventTime')
            if event_time and last_event_time:
                try:
                    current_dt = datetime.strptime(event_time, "%Y-%m-%dT%H:%M:%S.%fZ") if '.' in event_time else datetime.strptime(event_time, "%Y-%m-%dT%H:%M:%SZ")
                    last_dt = datetime.strptime(last_event_time, "%Y-%m-%dT%H:%M:%S.%fZ") if '.' in last_event_time else datetime.strptime(last_event_time, "%Y-%m-%dT%H:%M:%SZ")
                    
                    # Check if events are out of order
                    if current_dt < last_dt:
                        errors.append({
                            'type': 'sequence',
                            'severity': 'warning',
                            'message': f"Events may be out of chronological order. Event {i+1} occurs before event {i}."
                        })
                except (ValueError, TypeError):
                    # Skip time comparison if dates can't be parsed
                    pass
            
            last_event_time = event_time
            
        # Check for consistency in aggregations
        aggregations = {}
        for i, event in enumerate(events):
            if event.get('action') == 'ADD' and 'parentID' in event and 'childEPCs' in event:
                parent_id = event.get('parentID')
                child_epcs = event.get('childEPCs', [])
                
                # Record the aggregation
                for child in child_epcs:
                    if child in aggregations:
                        errors.append({
                            'type': 'sequence',
                            'severity': 'error',
                            'message': f"EPC {child} is aggregated to multiple parents: {aggregations[child]} and {parent_id}"
                        })
                    aggregations[child] = parent_id
            
            elif event.get('action') == 'DELETE' and 'parentID' in event and 'childEPCs' in event:
                parent_id = event.get('parentID')
                child_epcs = event.get('childEPCs', [])
                
                # Check for consistent disaggregation
                for child in child_epcs:
                    if child in aggregations and aggregations[child] != parent_id:
                        errors.append({
                            'type': 'sequence',
                            'severity': 'error',
                            'message': f"EPC {child} is disaggregated from {parent_id} but was aggregated to {aggregations[child]}"
                        })
                    
                    # Remove from aggregations
                    if child in aggregations:
                        del aggregations[child]
        
        return errors
    
    def _validate_epc(self, epc: str) -> bool:
        """Validate an EPC URN format
        
        Args:
            epc: EPC URN string to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not epc or not isinstance(epc, str):
            return False
            
        if not epc.startswith('urn:epc:id:'):
            return False
            
        for pattern in self.epc_patterns.values():
            if re.match(pattern, epc):
                return True
                
        return False
    
    def _validate_location_id(self, location_id: str) -> bool:
        """Validate a location identifier
        
        Args:
            location_id: Location identifier string
            
        Returns:
            True if valid, False otherwise
        """
        if not location_id or not isinstance(location_id, str):
            return False
        
        # Check for SGLN pattern (most common for locations)
        if location_id.startswith('urn:epc:id:sgln:'):
            sgln_pattern = self.epc_patterns['sgln']
            return bool(re.match(sgln_pattern, location_id))
        
        # For other patterns, allow if they start with urn:
        return location_id.startswith('urn:')
    
    def _extract_xml_events(self, root) -> List[Dict[str, Any]]:
        """Extract events from XML root element
        
        Args:
            root: XML root element
            
        Returns:
            List of event dictionaries
        """
        try:
            events = []
            
            # Remove namespace for easier parsing
            for elem in root.iter():
                if '}' in elem.tag:
                    elem.tag = elem.tag.split('}', 1)[1]
            
            # Try to find EPCISBody which should contain events
            epcis_body = root.find('.//EPCISBody')
            
            # If EPCISBody not found, search at the document level
            if epcis_body is None:
                logger.warning("EPCISBody element not found, searching at root level")
                epcis_body = root
            
            # Find EventList
            event_list = epcis_body.find('.//EventList')
            if event_list is None:
                logger.warning("EventList element not found, searching at EPCISBody level")
                event_list = epcis_body
            
            # Extract events
            event_types = ['ObjectEvent', 'AggregationEvent', 'TransactionEvent', 'TransformationEvent']
            
            for event_type in event_types:
                # Try different paths to find events
                for event_elem in event_list.findall(f'.//{event_type}'):
                    event = self._extract_event_data(event_elem, event_type)
                    if event:
                        events.append(event)
            
            return events
        except Exception as e:
            logger.exception(f"Error extracting XML events: {e}")
            return []
    
    def _extract_event_data(self, event_elem, event_type: str) -> Dict[str, Any]:
        """Extract data from an event element
        
        Args:
            event_elem: XML element containing event data
            event_type: Type of EPCIS event
            
        Returns:
            Dict containing event data
        """
        event = {'eventType': event_type}
        
        # Extract basic fields
        for field in ['eventTime', 'eventTimeZoneOffset', 'action', 'bizStep', 'disposition']:
            value = event_elem.findtext(field)
            if value:
                event[field] = value
        
        # Extract EPCs
        epc_list = event_elem.find('epcList')
        if epc_list is not None:
            event['epcList'] = [epc.text for epc in epc_list.findall('epc') if epc.text]
        
        # Extract parent ID and child EPCs for AggregationEvent
        if event_type == 'AggregationEvent':
            parent_id = event_elem.findtext('parentID')
            if parent_id:
                event['parentID'] = parent_id
                
            child_epcs = event_elem.find('childEPCs')
            if child_epcs is not None:
                event['childEPCs'] = [epc.text for epc in child_epcs.findall('epc') if epc.text]
        
        # Extract input/output EPCs for TransformationEvent
        if event_type == 'TransformationEvent':
            input_list = event_elem.find('inputEPCList')
            if input_list is not None:
                event['inputEPCList'] = [epc.text for epc in input_list.findall('epc') if epc.text]
                
            output_list = event_elem.find('outputEPCList')
            if output_list is not None:
                event['outputEPCList'] = [epc.text for epc in output_list.findall('epc') if epc.text]
        
        # Extract business transaction list
        biz_tx_list = event_elem.find('bizTransactionList')
        if biz_tx_list is not None:
            biz_txs = []
            for biz_tx in biz_tx_list.findall('bizTransaction'):
                tx_type = biz_tx.get('type')
                tx_value = biz_tx.text
                if tx_value:
                    biz_txs.append({'type': tx_type, 'value': tx_value})
            
            if biz_txs:
                event['bizTransactionList'] = biz_txs
        
        # Extract locations
        read_point = event_elem.find('readPoint/id')
        if read_point is not None and read_point.text:
            event['readPoint'] = {'id': read_point.text}
        
        biz_location = event_elem.find('bizLocation/id')
        if biz_location is not None and biz_location.text:
            event['bizLocation'] = {'id': biz_location.text}
        
        return event

    def _validate_sgtin_commission(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Enhanced SGTIN commissioning validation including ILMD data"""
        if (event.get('bizStep', '').endswith('commissioning') and 
            any(epc.startswith('urn:epc:id:sgtin:') for epc in event.get('epcList', []))):
            
            ilmd = event.get('ilmd', {})
            epcs = event.get('epcList', [])
            
            # Required ILMD fields for SGTIN commissioning
            required_ilmd = {
                'lotNumber': str,
                'itemExpirationDate': str,
                'productionDate': str,
            }
            
            # Validate required ILMD fields
            for field, field_type in required_ilmd.items():
                value = ilmd.get(field)
                if not value:
                    errors.append({
                        'type': 'field',
                        'severity': 'error',
                        'message': f"Missing required ILMD field for SGTIN commissioning: {field}"
                    })
                elif not isinstance(value, field_type):
                    errors.append({
                        'type': 'field',
                        'severity': 'error',
                        'message': f"Invalid type for ILMD field {field}: expected {field_type.__name__}"
                    })
            
            # Validate date formats
            date_fields = ['itemExpirationDate', 'productionDate']
            for field in date_fields:
                if field in ilmd:
                    try:
                        datetime.strptime(ilmd[field], "%Y-%m-%d")
                    except ValueError:
                        errors.append({
                            'type': 'field',
                            'severity': 'error',
                            'message': f"Invalid date format in ILMD {field}: {ilmd[field]}. Expected YYYY-MM-DD"
                        })
            
            # Store ILMD data for each SGTIN
            for epc in epcs:
                if epc.startswith('urn:epc:id:sgtin:'):
                    self.ilmd_data[epc] = ilmd.copy()
                    self.commissioned_items['SGTIN'].add(epc)
    
    def _validate_packaging_hierarchy(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Enhanced packaging hierarchy validation"""
        if event.get('eventType') == 'AggregationEvent':
            action = event.get('action')
            parent_id = event.get('parentID')
            child_epcs = event.get('childEPCs', [])
            
            if action == 'ADD':
                if not parent_id and child_epcs:
                    errors.append({
                        'type': 'hierarchy',
                        'severity': 'error',
                        'message': "parentID required for ADD AggregationEvent with children"
                    })
                    return
                
                # Determine packaging level transition
                parent_type = 'sscc' if parent_id and parent_id.startswith('urn:epc:id:sscc:') else None
                child_type = None
                if child_epcs:
                    first_child = child_epcs[0]
                    if first_child.startswith('urn:epc:id:sgtin:'):
                        child_type = 'sgtin'
                    elif first_child.startswith('urn:epc:id:sscc:'):
                        child_type = 'sscc'
                
                # Validate packaging transition
                if parent_type and child_type:
                    valid_transition = False
                    max_children = 0
                    
                    for transition in self.packaging_transitions.values():
                        if transition['parent_type'] == parent_type and transition['child_type'] == child_type:
                            valid_transition = True
                            max_children = transition['max_children']
                            break
                    
                    if not valid_transition:
                        errors.append({
                            'type': 'hierarchy',
                            'severity': 'error',
                            'message': f"Invalid packaging hierarchy: cannot aggregate {child_type} into {parent_type}"
                        })
                    
                    if len(child_epcs) > max_children:
                        errors.append({
                            'type': 'hierarchy',
                            'severity': 'warning',
                            'message': f"Number of child EPCs ({len(child_epcs)}) exceeds recommended maximum ({max_children})"
                        })
                
                # Check if children were commissioned
                for child in child_epcs:
                    child_commissioned = False
                    if child.startswith('urn:epc:id:sgtin:'):
                        child_commissioned = child in self.commissioned_items['SGTIN']
                    elif child.startswith('urn:epc:id:sscc:'):
                        child_commissioned = child in self.commissioned_items['SSCC']
                    
                    if not child_commissioned:
                        errors.append({
                            'type': 'sequence',
                            'severity': 'error',
                            'message': f"Item {child} not commissioned before aggregation"
                        })
                    
                    # Check if child is already aggregated elsewhere
                    if child in self.aggregated_items:
                        errors.append({
                            'type': 'hierarchy',
                            'severity': 'error',
                            'message': f"Item {child} is already aggregated to {self.aggregated_items[child]}"
                        })
                    else:
                        self.aggregated_items[child] = parent_id
            
            elif action == 'DELETE':
                # For DELETE, validate that items were previously aggregated to this parent
                for child in child_epcs:
                    if child in self.aggregated_items:
                        if self.aggregated_items[child] != parent_id:
                            errors.append({
                                'type': 'hierarchy',
                                'severity': 'error',
                                'message': f"Cannot disaggregate {child} from {parent_id}, it was aggregated to {self.aggregated_items[child]}"
                            })
                        else:
                            # Remove the aggregation
                            del self.aggregated_items[child]
                    else:
                        errors.append({
                            'type': 'hierarchy',
                            'severity': 'error',
                            'message': f"Cannot disaggregate {child}, it was not previously aggregated"
                        })

    def _validate_event_timing(self, events: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Validate event timing and sequence"""
        errors = []
        event_times = defaultdict(dict)  # epc -> {event_type -> datetime}
        commissioned_items = set()  # Track commissioned items
        packed_items = set()       # Track packed items
        shipped_items = set()      # Track shipped items
        
        valid_sequence = ['commissioning', 'packing', 'shipping']
        
        for event in events:
            try:
                event_dt = datetime.fromisoformat(event['eventTime'].replace('Z', '+00:00'))
                biz_step = event.get('bizStep', '').split(':')[-1]
                epcs = event.get('epcList', []) + event.get('childEPCs', [])

                # Track items through workflow
                if biz_step == 'commissioning':
                    commissioned_items.update(epcs)
                elif biz_step == 'packing':
                    packed_items.update(epcs)
                elif biz_step == 'shipping':
                    shipped_items.update(epcs)
                
                for epc in epcs:
                    if biz_step in valid_sequence:
                        # Check sequence
                        step_idx = valid_sequence.index(biz_step)
                        for required_step in valid_sequence[:step_idx]:
                            if not event_times[epc].get(required_step):
                                errors.append({
                                    'type': 'sequence',
                                    'severity': 'error',
                                    'message': f"EPC {epc} has {biz_step} event before required {required_step} event"
                                })
                        
                        # Check for duplicate events
                        if event_times[epc].get(biz_step):
                            errors.append({
                                'type': 'sequence', 
                                'severity': 'error',
                                'message': f"Duplicate {biz_step} event found for EPC {epc}"
                            })
                            
                        # Store event time
                        event_times[epc][biz_step] = event_dt
                        
                        # Validate time order if previous step exists
                        if step_idx > 0:
                            prev_step = valid_sequence[step_idx - 1]
                            if event_times[epc].get(prev_step) and event_times[epc][prev_step] > event_dt:
                                errors.append({
                                    'type': 'sequence',
                                    'severity': 'error',  
                                    'message': f"EPC {epc} has {biz_step} event before {prev_step} event"
                                })
                        
            except ValueError:
                # Time parsing errors handled elsewhere
                continue

        # Verify all commissioned items are packed and shipped
        unpacked = commissioned_items - packed_items
        if unpacked:
            errors.append({
                'type': 'sequence',
                'severity': 'error',
                'message': f"Found {len(unpacked)} commissioned items that were not packed"
            })

        unshipped = packed_items - shipped_items
        if unshipped:
            errors.append({
                'type': 'sequence',
                'severity': 'error',
                'message': f"Found {len(unshipped)} packed items that were not shipped"
            })
                
        return errors

    def _validate_location_identifiers(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Validate readPoint and bizLocation identifiers"""
        for location_type in ['readPoint', 'bizLocation']:
            if location_type in event:
                location = event[location_type]
                if not isinstance(location, dict) or 'id' not in location:
                    errors.append({
                        'type': 'format',
                        'severity': 'error',
                        'message': f"Invalid {location_type} format: must be object with 'id' field"
                    })
                else:
                    loc_id = location['id']
                    if not loc_id.startswith('urn:epc:id:sgln:'):
                        errors.append({
                            'type': 'format',
                            'severity': 'error',
                            'message': f"Invalid {location_type} identifier: must be SGLN format"
                        })

    def _validate_ilmd_data(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Enhanced ILMD data validation including date formats and required fields"""
        if 'ilmd' in event:
            ilmd = event['ilmd']
            
            # Required fields for SGTIN commissioning
            if (event.get('bizStep', '').endswith('commissioning') and 
                any(epc.startswith('urn:epc:id:sgtin:') for epc in event.get('epcList', []))):
                
                required_fields = {
                    'lotNumber': str,
                    'itemExpirationDate': str,
                    'productionDate': str
                }
                
                for field, field_type in required_fields.items():
                    # Check presence and type
                    value = ilmd.get(field)
                    field_path = f"cbvmda:{field}" if field != 'lotNumber' else field
                    full_value = ilmd.get(field_path, value)
                    
                    if not full_value:
                        errors.append({
                            'type': 'missing_field',
                            'severity': 'error',
                            'message': f"Missing required ILMD field for SGTIN commissioning: {field}"
                        })
                    elif not isinstance(full_value, field_type):
                        errors.append({
                            'type': 'invalid_type',
                            'severity': 'error',
                            'message': f"Invalid type for ILMD field {field}: expected {field_type.__name__}"
                        })
                    
                    # Validate date formats
                    if field.endswith('Date') and full_value:
                        try:
                            datetime.strptime(full_value, "%Y-%m-%d")
                        except ValueError:
                            errors.append({
                                'type': 'invalid_format',
                                'severity': 'error',
                                'message': f"Invalid date format in ILMD {field}: {full_value}. Expected YYYY-MM-DD"
                            })
                            
                # Validate that expiration date is after production date
                try:
                    prod_date = ilmd.get('cbvmda:productionDate', ilmd.get('productionDate'))
                    exp_date = ilmd.get('cbvmda:itemExpirationDate', ilmd.get('itemExpirationDate'))
                    if prod_date and exp_date:
                        prod_dt = datetime.strptime(prod_date, "%Y-%m-%d")
                        exp_dt = datetime.strptime(exp_date, "%Y-%m-%d")
                        if exp_dt <= prod_dt:
                            errors.append({
                                'type': 'invalid_date',
                                'severity': 'error',
                                'message': f"Expiration date {exp_date} must be after production date {prod_date}"
                            })
                except ValueError:
                    # Date format errors already caught above
                    pass

    def _validate_company_prefix(self, epc: str, header_companies: Set[str]) -> bool:
        """Validate company prefix in EPCs matches document header"""
        if epc.startswith('urn:epc:id:sgtin:'):
            company = epc.split(':')[4].split('.')[0]
            return company in header_companies
        return True

    def _validate_aggregation_event(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Enhanced aggregation event validation"""
        if event.get('eventType') == 'AggregationEvent':
            parent_id = event.get('parentID')
            child_epcs = event.get('childEPCs', [])
            action = event.get('action')

            # Validate non-empty childEPCs for ADD actions
            if action == 'ADD' and not child_epcs:
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': "Empty childEPCs in ADD AggregationEvent"
                })

            # Check for duplicate child EPCs
            if len(child_epcs) != len(set(child_epcs)):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': "Duplicate EPCs found in childEPCs"
                })

            # Validate parent-child relationship
            if parent_id:
                parent_type = self._get_epc_type(parent_id)
                child_types = [self._get_epc_type(epc) for epc in child_epcs]

                # Validate packaging hierarchy
                if parent_type == 'sscc' and any(ct == 'sscc' for ct in child_types):
                    # Case-to-pallet validation
                    if len(child_epcs) > self.packaging_transitions['CASE_TO_PALLET']['max_children']:
                        errors.append({
                            'type': 'hierarchy',
                            'severity': 'error',
                            'message': f"Number of cases ({len(child_epcs)}) exceeds maximum allowed in pallet"
                        })
                elif parent_type == 'sgtin' and any(ct == 'sgtin' for ct in child_types):
                    # Unit-to-case validation
                    if len(child_epcs) > self.packaging_transitions['SKU_TO_CASE']['max_children']:
                        errors.append({
                            'type': 'hierarchy',
                            'severity': 'error', 
                            'message': f"Number of units ({len(child_epcs)}) exceeds maximum allowed in case"
                        })

    def _validate_shipping_event(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Validate shipping event requirements"""
        if event.get('bizStep', '').endswith('shipping'):
            # Check for required business transactions
            biz_transactions = event.get('bizTransactionList', [])
            found_types = {bt.get('type') for bt in biz_transactions}
            
            for required_type in self.required_transaction_types['shipping']:
                if required_type not in found_types:
                    errors.append({
                        'type': 'field',
                        'severity': 'error',
                        'message': f"Missing required transaction type in shipping event: {required_type}"
                    })

            # Validate source/destination lists
            extension = event.get('extension', {})
            for list_type, required_types in self.required_shipping_fields.items():
                type_list = extension.get(list_type, [])
                found_types = {item.get('type').split(':')[-1] for item in type_list}
                
                for required_type in required_types:
                    if required_type not in found_types:
                        errors.append({
                            'type': 'field',
                            'severity': 'error',
                            'message': f"Missing required {list_type} type: {required_type}"
                        })

    def validate_event(self, event: Dict[str, Any], header_companies: Set[str]) -> List[Dict[str, str]]:
        """Validate a single EPCIS event"""
        errors = []
        
        # Validate basic structure and required fields
        self._validate_event_structure(event, errors)
        
        # Validate business step and disposition
        if 'bizStep' in event:
            self._validate_business_step(event['bizStep'], errors)
        if 'disposition' in event:
            self._validate_disposition(event['disposition'], errors)
            
        # Validate EPCs and hierarchical relationships
        self._validate_epcs(event, errors)
        self._validate_packaging_hierarchy(event, errors)
        
        # Enhanced validations
        self._validate_location_identifiers(event, errors)
        self._validate_ilmd_data(event, errors)
        self._validate_event_timing(event, errors)
        self._validate_aggregation_event(event, errors)
        self._validate_shipping_event(event, errors)
        
        # Company prefix validation
        epcs = event.get('epcList', []) + event.get('childEPCs', [])
        for epc in epcs:
            if not self._validate_company_prefix(epc, header_companies):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': f"Company prefix in EPC {epc} does not match authorized companies in document header"
                })
        
        return errors

    def _get_epc_type(self, epc: str) -> str:
        """Extract the type (sgtin/sscc) from an EPC"""
        if not epc:
            return ''
        parts = epc.split(':')
        return parts[3] if len(parts) > 3 else ''
        
    def _get_party_id(self, party: Dict[str, Any]) -> str:
        """Extract party identifier from header"""
        identifier = party.get('Identifier', {})
        if isinstance(identifier, dict):
            return identifier.get('value', '')
        return identifier
        
    def _get_parties_from_list(self, party_list: List[Dict[str, Any]]) -> Set[str]:
        """Extract party identifiers from source/destination lists"""
        parties = set()
        for party in party_list:
            if party.get('type', '').endswith('owning_party'):
                parties.add(party.get('id', ''))
        return parties

    def _validate_document_header(self, header: Dict[str, Any], events: List[Dict[str, Any]], errors: List[Dict[str, str]]):
        """Validate EPCIS document header structure and references"""
        if 'StandardBusinessDocumentHeader' not in header:
            errors.append({
                'type': 'header',
                'severity': 'error',
                'message': 'Missing StandardBusinessDocumentHeader'
            })
            return
        
        sbdh = header['StandardBusinessDocumentHeader']
        sender_id = self._get_party_id(sbdh.get('Sender', {}))
        receiver_id = self._get_party_id(sbdh.get('Receiver', {}))
        
        # Validate sender/receiver match events
        for event in events:
            if event.get('bizStep', '').endswith('shipping'):
                sources = self._get_parties_from_list(
                    event.get('extension', {}).get('sourceList', []))
                destinations = self._get_parties_from_list(
                    event.get('extension', {}).get('destinationList', []))
                
                if sender_id not in sources:
                    errors.append({
                        'type': 'reference',
                        'severity': 'error',
                        'message': f'Document sender {sender_id} not found in event source list'
                    })
                    
                if receiver_id not in destinations:
                    errors.append({
                        'type': 'reference',
                        'severity': 'error',
                        'message': f'Document receiver {receiver_id} not found in event destination list'
                    })

    def _validate_event_structure(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Validate basic event structure and required fields"""
        # Check for empty events
        if not event or not any(event.values()):
            errors.append({
                'type': 'structure',
                'severity': 'error',
                'message': 'Empty or incomplete event found'
            })
            return

        # Validate EPCs match authorized companies
        epcs = event.get('epcList', []) + event.get('childEPCs', [])
        for epc in epcs:
            if not self._validate_company_prefix(epc, header_companies):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': f"Company prefix in EPC {epc} does not match authorized companies in document header"
                })
        
        # Validate business transactions if shipping event
        if event.get('bizStep', '').endswith('shipping'):
            self._validate_business_transaction(event, errors)
            
        # Validate locations
        self._validate_location_identifiers(event, errors)
        
        return errors

    def _validate_event_timing(self, events: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        errors = []
        event_times = defaultdict(dict)
        valid_sequence = ['commissioning', 'packing', 'shipping']
                
        # Track all events by step to validate same-step timing
        step_events = defaultdict(list)
        
        for event in events:
            try:
                event_dt = datetime.fromisoformat(event['eventTime'].replace('Z', '+00:00'))
                biz_step = event.get('bizStep', '').split(':')[-1]
                epcs = event.get('epcList', []) + event.get('childEPCs', [])
                
                # Track event for same-step validation
                step_events[biz_step].append((event_dt, event))
                
                for epc in epcs:
                    if biz_step in valid_sequence:
                        # Check sequence
                        step_idx = valid_sequence.index(biz_step)
                        for required_step in valid_sequence[:step_idx]:
                            if not event_times[epc].get(required_step):
                                errors.append({
                                    'type': 'sequence',
                                    'severity': 'error',
                                    'message': f"EPC {epc} has {biz_step} event before required {required_step} event"
                                })
                        
                        # Store event time
                        event_times[epc][biz_step] = event_dt
                        
                        # Validate time order if previous step exists
                        if step_idx > 0:
                            prev_step = valid_sequence[step_idx - 1]
                            if event_times[epc].get(prev_step) and event_times[epc][prev_step] > event_dt:
                                errors.append({
                                    'type': 'sequence',
                                    'severity': 'error',  
                                    'message': f"EPC {epc} has {biz_step} event before {prev_step} event"
                                })
                        
            except ValueError:
                errors.append({
                    'type': 'format',
                    'severity': 'error',
                    'message': f"Invalid event time format in event"
                })

        # Validate same-step event timing
        for step, events in step_events.items():
            events.sort()  # Sort by timestamp
            for i in range(1, len(events)):
                if (events[i][0] - events[i-1][0]).total_seconds() < 0:  # Negative time difference
                    errors.append({
                        'type': 'sequence',
                        'severity': 'error',
                        'message': f"Invalid event timing order within {step} step"
                    })
                    
        return errors

    def _validate_location_identifiers(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Validate readPoint and bizLocation identifiers"""
        for location_type in ['readPoint', 'bizLocation']:
            if location_type in event:
                location = event[location_type]
                if not isinstance(location, dict) or 'id' not in location:
                    errors.append({
                        'type': 'format',
                        'severity': 'error',
                        'message': f"Invalid {location_type} format: must be object with 'id' field"
                    })
                else:
                    loc_id = location['id']
                    if not loc_id.startswith('urn:epc:id:sgln:'):
                        errors.append({
                            'type': 'format',
                            'severity': 'error',
                            'message': f"Invalid {location_type} identifier format: must be SGLN"
                        })

    def _validate_business_transaction(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Validate business transaction references"""
        if 'bizTransactionList' in event:
            transactions = event['bizTransactionList']
            if not isinstance(transactions, list):
                errors.append({
                    'type': 'format', 
                    'severity': 'error',
                    'message': 'bizTransactionList must be an array'
                })
            else:
                for txn in transactions:
                    if not isinstance(txn, dict) or 'type' not in txn:
                        errors.append({
                            'type': 'format',
                            'severity': 'error', 
                            'message': 'Each business transaction must have a type'
                        })
                    elif txn['type'] not in ['urn:epcglobal:cbv:btt:po', 'urn:epcglobal:cbv:btt:desadv']:
                        errors.append({
                            'type': 'format',
                            'severity': 'error',
                            'message': f"Invalid business transaction type: {txn['type']}"
                        })

    def validate_event(self, event: Dict[str, Any], header_companies: Set[str]) -> List[Dict[str, str]]:
        errors = []
        
        # Validate EPCs match authorized companies
        epcs = event.get('epcList', []) + event.get('childEPCs', [])
        for epc in epcs:
            if not self._validate_company_prefix(epc, header_companies):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': f"Company prefix in EPC {epc} does not match authorized companies in document header"
                })
        
        # Validate business transactions if shipping event
        if event.get('bizStep', '').endswith('shipping'):
            self._validate_business_transaction(event, errors)
            
        # Validate locations
        self._validate_location_identifiers(event, errors)
        
        return errors

    # def _validate_event_timing(self, events: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    #     # ...existing code...

    def _validate_aggregation_relationships(self, events: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Validate parent-child relationships and uniqueness in aggregation events"""
        errors = []
        epc_to_parent = {}
        parent_to_children = {}
        
        for event in events:
            if event.get('eventType') == 'AggregationEvent':
                parent_id = event.get('parentID')
                child_epcs = event.get('childEPCs', [])
                
                # Check for duplicate children across different parents
                for child in child_epcs:
                    if child in epc_to_parent:
                        existing_parent = epc_to_parent[child]
                        if existing_parent != parent_id:
                            errors.append({
                                'type': 'relationship',
                                'severity': 'error',
                                'message': f"EPC {child} is aggregated under multiple parents: {parent_id} and {existing_parent}"
                            })
                    epc_to_parent[child] = parent_id
                
                # Track children for each parent
                if parent_id not in parent_to_children:
                    parent_to_children[parent_id] = set()
                parent_to_children[parent_id].update(child_epcs)

                # Validate no parent is also a child
                if parent_id in epc_to_parent:
                    errors.append({
                        'type': 'relationship',
                        'severity': 'error',
                        'message': f"Invalid hierarchy - parent {parent_id} is also a child in another aggregation"
                    })

        return errors

    def _validate_business_transaction(self, event: Dict[str, Any], errors: List[Dict[str, str]]):
        """Validate business transaction references"""
        if event.get('bizStep', '').endswith('shipping'):
            transactions = event.get('bizTransactionList', [])
            if not isinstance(transactions, list):
                errors.append({
                    'type': 'format', 
                    'severity': 'error',
                    'message': 'bizTransactionList must be an array'
                })
                return

            # Track found transaction types
            found_types = set()
            for txn in transactions:
                if not isinstance(txn, dict):
                    errors.append({
                        'type': 'format',
                        'severity': 'error',
                        'message': 'Each business transaction must be an object'
                    })
                    continue

                txn_type = txn.get('type')
                if not txn_type:
                    errors.append({
                        'type': 'format',
                        'severity': 'error',
                        'message': 'Each business transaction must have a type'
                    })
                    continue

                if txn_type not in ['urn:epcglobal:cbv:btt:po', 'urn:epcglobal:cbv:btt:desadv']:
                    errors.append({
                        'type': 'format',
                        'severity': 'error',
                        'message': f"Invalid business transaction type: {txn_type}"
                    })
                    continue

                found_types.add(txn_type)

                # Validate transaction ID format
                txn_id = txn.get('bizTransaction')
                if not txn_id or not isinstance(txn_id, str):
                    errors.append({
                        'type': 'format',
                        'severity': 'error',
                        'message': f"Missing or invalid business transaction ID for type {txn_type}"
                    })

            # Shipping events must have both PO and DESADV
            required_types = {'urn:epcglobal:cbv:btt:po', 'urn:epcglobal:cbv:btt:desadv'}
            missing_types = required_types - found_types
            if missing_types:
                errors.append({
                    'type': 'format',
                    'severity': 'error',
                    'message': f"Shipping event missing required transaction types: {', '.join(missing_types)}"
                })
    
    def validate_event(self, event: Dict[str, Any], header_companies: Set[str]) -> List[Dict[str, str]]:
        errors = []
        
        # Validate EPCs match authorized companies
        epcs = event.get('epcList', []) + event.get('childEPCs', [])
        for epc in epcs:
            if not self._validate_company_prefix(epc, header_companies):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': f"Company prefix in EPC {epc} does not match authorized companies in document header"
                })
        
        # Validate business transactions if shipping event
        if event.get('bizStep', '').endswith('shipping'):
            self._validate_business_transaction(event, errors)
            
        # Validate locations
        self._validate_location_identifiers(event, errors)
        
        return errors

    # ...existing code...