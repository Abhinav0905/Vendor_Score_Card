import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from collections import defaultdict
import xml.etree.ElementTree as ET
import json

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
        
        # Required elements for each event type
        self.required_elements = {
            'ObjectEvent': ['eventTime', 'eventTimeZoneOffset', 'epcList', 'action'],
            'AggregationEvent': ['eventTime', 'eventTimeZoneOffset', 'parentID', 'childEPCs', 'action'],
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
        # These would typically be populated from a database or reference data
        self.valid_product_codes = {
            # Format: Company prefix + item reference
            '0327808.023302', '0327808.026601',
            '0327808.315801', '0327808.323401',  # Added these from your error message
        }
    
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
        """Validate an individual EPCIS event
        
        Args:
            event: Dict containing event data
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check for None event
        if not event:
            errors.append({
                'type': 'structure',
                'severity': 'error',
                'message': "Empty event found"
            })
            return errors
        
        # Determine event type
        event_type = event.get('eventType', '')
        if not event_type and 'action' in event and 'epcList' in event:
            event_type = 'ObjectEvent'  # Assume ObjectEvent if not specified but has key attributes
        
        # Check for valid event type
        if event_type and event_type not in self.required_elements:
            errors.append({
                'type': 'field',
                'severity': 'error',
                'message': f"Invalid event type: {event_type}"
            })
        
        # Check required fields based on event type
        if event_type in self.required_elements:
            for field in self.required_elements[event_type]:
                if field not in event or not event.get(field):
                    errors.append({
                        'type': 'field',
                        'severity': 'error',
                        'message': f"Missing required field for {event_type}: {field}"
                    })
        else:
            # If event type not specified, check common required fields
            for field in ['eventTime', 'eventTimeZoneOffset']:
                if field not in event or not event.get(field):
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
                        'message': f"Invalid eventTime format: {event_time}"
                    })
        
        # Validate timezone offset format
        tz_offset = event.get('eventTimeZoneOffset')
        if tz_offset:
            if not re.match(r'^[+-]\d{2}:00$', tz_offset):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': f"Invalid eventTimeZoneOffset format: {tz_offset}"
                })
        
        # Validate action
        action = event.get('action')
        if action:
            if action not in self.valid_actions:
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
        
        # Validate disposition
        disposition = event.get('disposition')
        if disposition:
            disposition_name = disposition.split(':')[-1].lower()
            if disposition_name not in self.valid_dispositions:
                errors.append({
                    'type': 'field',
                    'severity': 'warning',
                    'message': f"Non-standard disposition: {disposition}"
                })
        
        # Validate EPCs
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
        
        # Validate child EPCs for AggregationEvent
        child_epcs = event.get('childEPCs', [])
        if child_epcs:
            if not isinstance(child_epcs, list):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': "childEPCs must be an array"
                })
            else:
                for epc in child_epcs:
                    if not self._validate_epc(epc):
                        errors.append({
                            'type': 'field',
                            'severity': 'error',
                            'message': f"Invalid child EPC format: {epc}"
                        })
        
        # Validate parent ID for AggregationEvent
        parent_id = event.get('parentID')
        if parent_id and not self._validate_epc(parent_id):
            errors.append({
                'type': 'field',
                'severity': 'error',
                'message': f"Invalid parentID format: {parent_id}"
            })
        
        # Validate read point and business location
        read_point = event.get('readPoint', {}).get('id')
        if read_point and not self._validate_location_id(read_point):
            errors.append({
                'type': 'field',
                'severity': 'warning',
                'message': f"Invalid readPoint format: {read_point}"
            })
        
        biz_location = event.get('bizLocation', {}).get('id')
        if biz_location and not self._validate_location_id(biz_location):
            errors.append({
                'type': 'field',
                'severity': 'warning',
                'message': f"Invalid bizLocation format: {biz_location}"
            })
        
        # Validate business transaction list
        biz_transactions = event.get('bizTransactionList', [])
        if biz_transactions:
            if not isinstance(biz_transactions, list):
                errors.append({
                    'type': 'field',
                    'severity': 'error',
                    'message': "bizTransactionList must be an array"
                })
            else:
                for tx in biz_transactions:
                    if not isinstance(tx, dict) or 'type' not in tx or 'value' not in tx:
                        errors.append({
                            'type': 'field',
                            'severity': 'error',
                            'message': f"Invalid business transaction format: {tx}"
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