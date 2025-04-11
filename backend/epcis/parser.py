import json
import lxml.etree as ET  # Replacing standard ElementTree with lxml
from typing import Dict, List, Set, Tuple, Optional
from .utils import extract_namespaces, logger

class EPCISParser:
    """Parser for EPCIS XML and JSON documents"""
    
    @staticmethod
    def parse_document(content: bytes, is_xml: bool = True) -> Tuple[Optional[Dict], List[Dict], Set[str], List[Dict]]:
        """Parse an EPCIS document and extract header, events, and company info
        
        Args:
            content: Raw document content
            is_xml: Whether content is XML (True) or JSON (False)
            
        Returns:
            Tuple containing:
            - Document header (Dict or None)
            - List of events (List[Dict])
            - Set of company prefixes (Set[str])
            - List of validation errors (List[Dict])
        """
        errors = []
        header = None
        events = []
        companies = set()
        try:
            if is_xml:
                header, events, companies, xml_errors = EPCISParser._parse_xml(content)
                errors.extend(xml_errors)
            else:
                header, events, companies, json_errors = EPCISParser._parse_json(content)
                errors.extend(json_errors)
                
            # Additional header processing to extract instance identifier
            if header:
                # Extract unique instance identifier if available
                doc_id = header.get('DocumentIdentification', {})
                instance_id = doc_id.get('InstanceIdentifier')
                if instance_id:
                    header['instance_identifier'] = instance_id
                    logger.info(f"Found instance identifier: {instance_id}")
        except Exception as e:
            logger.exception(f"Document parsing error: {e}")
            errors.append({
                'type': 'format',
                'severity': 'error',
                'message': f"Document parsing error: {str(e)}"
            })
        return header, events, companies, errors
    
    @staticmethod
    def _parse_xml(content: bytes) -> Tuple[Optional[Dict], List[Dict], Set[str], List[Dict]]:
        """Parse XML EPCIS document
        
        Args:
            content: Raw XML content
            
        Returns:
            Tuple of (header, events, companies, errors)
        """
        errors = []
        events = []
        companies = set()
        header = None
        try:
            # Use lxml parser which maintains line numbers
            parser = ET.XMLParser(remove_blank_text=True)
            root = ET.fromstring(content, parser)
            
            # Validate EPCIS namespace
            namespaces = extract_namespaces(content.decode('utf-8'))
            if not any('epcis' in ns.lower() for ns in namespaces):
                errors.append({
                    'type': 'structure',
                    'severity': 'error',
                    'message': "Missing EPCIS namespace declaration"
                })
                
            # Extract header
            header_elem = root.find('.//StandardBusinessDocumentHeader')
            if header_elem is not None:
                header = EPCISParser._xml_to_dict(header_elem)
                
            # Extract events with line number information
            for event_elem in root.findall('.//ObjectEvent') + root.findall('.//AggregationEvent'):
                try:
                    # Basic event structure with event-level line number
                    event = EPCISParser._xml_to_dict(event_elem)
                    event['_line_number'] = event_elem.sourceline
                    
                    # Process EPCs with detailed line number tracking
                    epc_list_elem = event_elem.find('.//epcList')
                    if epc_list_elem is not None:
                        epc_elements = []
                        for epc_elem in epc_list_elem.findall('.//epc'):
                            if epc_elem.text:
                                epc_value = epc_elem.text.strip()
                                # Store each EPC with its own line number
                                epc_elements.append({
                                    'value': epc_value,
                                    'line_number': epc_elem.sourceline
                                })
                                
                                # Extract company prefixes
                                company = epc_value.split(':')[4].split('.')[0] if len(epc_value.split(':')) > 4 else None
                                if company:
                                    companies.add(company)
                        
                        # Replace string list with detailed info
                        event['epcList_detailed'] = epc_elements
                    
                    # Similarly process childEPCs
                    child_epcs_elem = event_elem.find('.//childEPCs')
                    if child_epcs_elem is not None:
                        child_epc_elements = []
                        for epc_elem in child_epcs_elem.findall('.//epc'):
                            if epc_elem.text:
                                epc_value = epc_elem.text.strip()
                                # Store each EPC with its own line number
                                child_epc_elements.append({
                                    'value': epc_value,
                                    'line_number': epc_elem.sourceline
                                })
                                
                                # Extract company prefixes
                                company = epc_value.split(':')[4].split('.')[0] if len(epc_value.split(':')) > 4 else None
                                if company:
                                    companies.add(company)
                        
                        # Replace string list with detailed info
                        event['childEPCs_detailed'] = child_epc_elements
                    
                    events.append(event)
                            
                except Exception as e:
                    errors.append({
                        'type': 'format',
                        'severity': 'error',
                        'message': f"Error parsing event: {str(e)}"
                    })
        except ET.ParseError as e:
            errors.append({
                'type': 'format',
                'severity': 'error',
                'message': f"Invalid XML format: {str(e)}"
            })
        except Exception as e:
            errors.append({
                'type': 'format',
                'severity': 'error',
                'message': f"XML parsing error: {str(e)}"
            })
        return header, events, companies, errors

    @staticmethod
    def _parse_json(content: bytes) -> Tuple[Optional[Dict], List[Dict], Set[str], List[Dict]]:
        """Parse JSON EPCIS document
        
        Args:
            content: Raw JSON content
            
        Returns:
            Tuple of (header, events, companies, errors)
        """
        errors = []
        events = []
        companies = set()
        header = None

        try:
            data = json.loads(content)
            
            # Validate EPCIS context
            if '@context' not in data or not any('epcis' in str(ctx).lower() for ctx in data.get('@context', [])):
                errors.append({
                    'type': 'structure',
                    'severity': 'error',
                    'message': "Missing EPCIS context in JSON"
                })

            # Extract header
            header = data.get('header')

            # Extract events
            for event in data.get('eventList', []):
                try:
                    events.append(event)
                    
                    # Extract company prefixes
                    for epc in event.get('epcList', []) + event.get('childEPCs', []):
                        company = epc.split(':')[4].split('.')[0] if len(epc.split(':')) > 4 else None
                        if company:
                            companies.add(company)
                            
                except Exception as e:
                    errors.append({
                        'type': 'format',
                        'severity': 'error',
                        'message': f"Error parsing event: {str(e)}"
                    })

        except json.JSONDecodeError as e:
            errors.append({
                'type': 'format',
                'severity': 'error',
                'message': f"Invalid JSON format: {str(e)}"
            })
        except Exception as e:
            errors.append({
                'type': 'format',
                'severity': 'error',
                'message': f"JSON parsing error: {str(e)}"
            })

        return header, events, companies, errors

    @staticmethod
    def _xml_to_dict(element: ET.Element) -> Dict:
        """Convert XML element to dictionary
        
        Args:
            element: XML element to convert
            
        Returns:
            Dict representation of XML element
        """
        result = {}
        
        # Handle attributes
        for key, value in element.attrib.items():
            result[key] = value
            
        # Handle child elements
        for child in element:
            tag = child.tag.split('}')[-1]  # Remove namespace
            
            # Special handling for known array fields
            if tag in ['epcList', 'childEPCs']:
                # These should contain a list of epc elements
                if tag not in result:
                    result[tag] = []
                for epc in child.findall('.//epc'):
                    if epc.text:
                        result[tag].append(epc.text.strip())
            elif tag == 'bizTransactionList':
                # Handle business transactions
                if tag not in result:
                    result[tag] = []
                for txn in child.findall('.//bizTransaction'):
                    if txn.text:
                        result[tag].append({
                            'type': txn.get('type'),
                            'bizTransaction': txn.text.strip()
                        })
            elif tag in ['readPoint', 'bizLocation']:
                # Handle location identifiers
                id_elem = child.find('.//id')
                if id_elem is not None and id_elem.text:
                    result[tag] = {'id': id_elem.text.strip()}
            elif tag == 'extension':
                # Handle extension elements
                if tag not in result:
                    result[tag] = {}
                
                # Process source and destination lists
                source_list = child.find('.//sourceList')
                if source_list is not None:
                    result[tag]['sourceList'] = [
                        {'type': src.get('type'), 'source': src.text.strip()}
                        for src in source_list.findall('.//source')
                        if src.text
                    ]
                
                dest_list = child.find('.//destinationList')
                if dest_list is not None:
                    result[tag]['destinationList'] = [
                        {'type': dest.get('type'), 'destination': dest.text.strip()}
                        for dest in dest_list.findall('.//destination')
                        if dest.text
                    ]
            else:
                # Handle other elements normally
                child_data = EPCISParser._xml_to_dict(child)
                if tag in result:
                    if isinstance(result[tag], list):
                        result[tag].append(child_data)
                    else:
                        result[tag] = [result[tag], child_data]
                else:
                    result[tag] = child_data
                
        # Handle text content
        if element.text and element.text.strip():
            text = element.text.strip()
            if len(result) == 0:
                # If no children/attributes, just return the text
                return text
            else:
                # Add as value field if we have other data
                result['value'] = text
                
        return result