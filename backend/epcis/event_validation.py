from datetime import datetime
from typing import Dict, List, Set
from .utils import validate_date_format, add_error, validate_dates_order
from .identifier_validation import GS1IdentifierValidator

class EPCISEventValidator:
    """Validator for individual EPCIS events"""

    # Valid business steps from CBV (Core Business Vocabulary)
    VALID_BIZ_STEPS = {
        'accepting', 'arriving', 'collecting', 'commissioning', 'consigning',
        'creating_class_instance', 'cycle_counting', 'decommissioning',
        'departing', 'destroying', 'dispensing', 'encoding', 'entering_exiting',
        'holding', 'inspecting', 'installing', 'killing', 'loading', 'other',
        'packing', 'picking', 'receiving', 'removing', 'repackaging',
        'repairing', 'replacing', 'reserving', 'retail_selling', 'shipping',
        'staging_outbound', 'stock_taking', 'stocking', 'storing', 'transporting',
        'unloading', 'void_shipping'
    }

    # Valid dispositions from CBV
    VALID_DISPOSITIONS = {
        'active', 'container_closed', 'damaged', 'destroyed', 'dispensed', 
        'disposed', 'encoded', 'expired', 'in_progress', 'in_transit', 'inactive', 
        'no_pedigree_match', 'non_sellable_other', 'partially_dispensed', 'recalled', 
        'reserved', 'retail_sold', 'returned', 'sellable_accessible', 
        'sellable_not_accessible', 'stolen', 'unknown', 'available', 'unavailable'
    }

    # Required fields for each event type
    REQUIRED_FIELDS = {
        'ObjectEvent': ['eventTime', 'eventTimeZoneOffset', 'epcList', 'action'],
        'AggregationEvent': ['eventTime', 'eventTimeZoneOffset', 'childEPCs', 'action'],
        'TransactionEvent': ['eventTime', 'eventTimeZoneOffset', 'bizTransactionList', 'epcList', 'action'],
        'TransformationEvent': ['eventTime', 'eventTimeZoneOffset', 'inputEPCList', 'outputEPCList']
    }

    # Required fields for shipping events
    REQUIRED_SHIPPING_FIELDS = {
        'sourceList': ['owning_party', 'location'],
        'destinationList': ['owning_party', 'location']
    }

    # Required transaction types for shipping events
    REQUIRED_TRANSACTION_TYPES = {
        'shipping': ['urn:epcglobal:cbv:btt:po', 'urn:epcglobal:cbv:btt:desadv']
    }

    def __init__(self):
        self.gs1_validator = GS1IdentifierValidator()

    def validate_event(self, event: Dict, authorized_companies: Set[str]) -> List[Dict]:
        """Validate an individual EPCIS event
        
        Args:
            event: Event dictionary to validate
            authorized_companies: Set of authorized company prefixes
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Date-order validation for direct event inputs
        date_errors = validate_dates_order(event)
        if date_errors:
            errors.extend(date_errors)
        
        # Basic structure validation
        if not event:
            add_error(errors, 'structure', 'error', "Empty event found")
            return errors

        # Validate required fields
        self._validate_required_fields(event, errors)
        
        # Validate event time and timezone
        self._validate_event_time(event, errors)
        
        # Validate EPCs
        self._validate_epcs(event, authorized_companies, errors)
        
        # Validate business step and disposition
        self._validate_biz_step(event, errors)
        self._validate_disposition(event, errors)
        
        # Validate location identifiers
        self._validate_location_identifiers(event, errors)
        
        # Validate ILMD data for commissioning events
        self._validate_ilmd_data(event, errors)
        
        # Additional validations for specific event types
        event_type = event.get('eventType')
        if event_type == 'AggregationEvent':
            self._validate_aggregation_event(event, errors)
        elif event.get('bizStep', '').endswith('shipping'):
            self._validate_shipping_event(event, errors)

        return errors

    def _validate_required_fields(self, event: Dict, errors: List[Dict]):
        """Validate required fields based on event type"""
        event_type = event.get('eventType')
        if event_type in self.REQUIRED_FIELDS:
            for field in self.REQUIRED_FIELDS[event_type]:
                if field == 'parentID' and event_type == 'AggregationEvent':
                    if event.get('action') == 'ADD' and not event.get(field):
                        add_error(errors, 'field', 'error', 
                                f"parentID required for ADD AggregationEvent")
                elif not event.get(field):
                    add_error(errors, 'field', 'error',
                            f"Missing required field for {event_type}: {field}")

    def _validate_event_time(self, event: Dict, errors: List[Dict]):
        """Validate event time format and timezone"""
        event_time = event.get('eventTime')
        if event_time:
            try:
                datetime.strptime(event_time, "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                try:
                    datetime.strptime(event_time, "%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    add_error(errors, 'field', 'error',
                            f"Invalid eventTime format: {event_time}")

        tz_offset = event.get('eventTimeZoneOffset')
        if tz_offset and not self._is_valid_timezone(tz_offset):
            add_error(errors, 'field', 'error',
                    f"Invalid eventTimeZoneOffset format: {tz_offset}")

    def _validate_epcs(self, event: Dict, authorized_companies: Set[str], errors: List[Dict]):
        """Validate EPCs in the event"""
        # First check if we have detailed EPC data with line numbers
        if 'epcList_detailed' in event:
            for epc_entry in event['epcList_detailed']:
                epc = epc_entry.get('value', '')
                line_number = epc_entry.get('line_number', 0)
                
                if not self.gs1_validator.validate_epc_format(epc):
                    add_error(errors, 'field', 'error',
                            f"Invalid EPC format: {epc}", line_number=line_number)
                elif not self.gs1_validator.validate_company_prefix(epc, authorized_companies):
                    add_error(errors, 'field', 'error',
                            f"Unauthorized company prefix in EPC: {epc}", line_number=line_number)
        
        # Same for childEPCs
        if 'childEPCs_detailed' in event:
            for epc_entry in event['childEPCs_detailed']:
                epc = epc_entry.get('value', '')
                line_number = epc_entry.get('line_number', 0)
                
                if not self.gs1_validator.validate_epc_format(epc):
                    add_error(errors, 'field', 'error',
                            f"Invalid EPC format: {epc}", line_number=line_number)
                elif not self.gs1_validator.validate_company_prefix(epc, authorized_companies):
                    add_error(errors, 'field', 'error',
                            f"Unauthorized company prefix in EPC: {epc}", line_number=line_number)
        
        # Fallback to the old way (no line numbers) for backward compatibility
        epcs = event.get('epcList', []) + event.get('childEPCs', [])
        
        if isinstance(epcs, list):
            for epc in epcs:
                # Skip if already processed in the detailed lists
                if ('epcList_detailed' in event or 'childEPCs_detailed' in event):
                    continue
                
                # Default event line number for backward compatibility
                line_number = event.get('_line_number', 0)
                    
                if not self.gs1_validator.validate_epc_format(epc):
                    add_error(errors, 'field', 'error',
                            f"Invalid EPC format: {epc}", line_number=line_number)
                elif not self.gs1_validator.validate_company_prefix(epc, authorized_companies):
                    add_error(errors, 'field', 'error',
                            f"Unauthorized company prefix in EPC: {epc}", line_number=line_number)

    def _validate_biz_step(self, event: Dict, errors: List[Dict]):
        """Validate business step"""
        biz_step = event.get('bizStep', '')
        if biz_step:
            step = biz_step.split(':')[-1]
            if step not in self.VALID_BIZ_STEPS:
                add_error(errors, 'field', 'error',
                        f"Invalid business step: {step}")

    def _validate_disposition(self, event: Dict, errors: List[Dict]):
        """Validate disposition"""
        disposition = event.get('disposition', '')
        if disposition:
            disp = disposition.split(':')[-1]
            if disp not in self.VALID_DISPOSITIONS:
                add_error(errors, 'field', 'error',
                        f"Invalid disposition: {disp}")

    def _validate_location_identifiers(self, event: Dict, errors: List[Dict]):
        """Validate readPoint and bizLocation identifiers"""
        for location_type in ['readPoint', 'bizLocation']:
            if location_type in event:
                location = event[location_type]
                if not isinstance(location, dict) or 'id' not in location:
                    add_error(errors, 'format', 'error',
                            f"Invalid {location_type} format: must be object with 'id' field")
                else:
                    loc_id = location['id']
                    if not loc_id.startswith('urn:epc:id:sgln:'):
                        add_error(errors, 'format', 'error',
                                f"Invalid {location_type} identifier format: must be SGLN")

    def _validate_ilmd_data(self, event: Dict, errors: List[Dict]):
        """Validate ILMD data in commissioning events"""
        if event.get('bizStep', '').endswith('commissioning') and 'ilmd' in event:
            ilmd = event['ilmd']
            
            required_fields = {
                'lotNumber': str,
                'itemExpirationDate': str
            }
            
            for field, field_type in required_fields.items():
                value = ilmd.get(field)
                field_path = f"cbvmda:{field}" if field != 'lotNumber' else field
                full_value = ilmd.get(field_path, value)
                
                if not full_value:
                    add_error(errors, 'field', 'error',
                            f"Missing required ILMD field: {field}")
                elif not isinstance(full_value, field_type):
                    add_error(errors, 'field', 'error',
                            f"Invalid type for ILMD field {field}")
                
                if field.endswith('Date') and full_value:
                    if not validate_date_format(full_value):
                        add_error(errors, 'field', 'error',
                                f"Invalid date format in ILMD field {field}: {full_value}")

    def _validate_aggregation_event(self, event: Dict, errors: List[Dict]):
        """Validate aggregation event specific rules"""
        if event.get('action') == 'ADD':
            parent_id = event.get('parentID')
            child_epcs = event.get('childEPCs', [])
            
            if not parent_id and child_epcs:
                add_error(errors, 'field', 'error',
                        "parentID required for ADD AggregationEvent with children")

    def _validate_shipping_event(self, event: Dict, errors: List[Dict]):
        """Validate shipping event specific requirements"""
        # Validate business transactions
        biz_transactions = event.get('bizTransactionList', [])
        found_types = {bt.get('type') for bt in biz_transactions if isinstance(bt, dict)}
        
        for required_type in self.REQUIRED_TRANSACTION_TYPES['shipping']:
            if required_type not in found_types:
                add_error(errors, 'field', 'error',
                        f"Missing required transaction type in shipping event: {required_type}")

        # Validate source/destination lists
        extension = event.get('extension', {})
        for list_type, required_types in self.REQUIRED_SHIPPING_FIELDS.items():
            type_list = extension.get(list_type, [])
            found_types = {item.get('type', '').split(':')[-1] 
                         for item in type_list 
                         if isinstance(item, dict)}
            
            for required_type in required_types:
                if required_type not in found_types:
                    add_error(errors, 'field', 'error',
                            f"Missing required {list_type} type: {required_type}")

    @staticmethod
    def _is_valid_timezone(tz: str) -> bool:
        """Validate timezone offset format"""
        import re
        # Allow offsets in 15-minute increments
        if not re.match(r'^[+-]\d{2}:\d{2}$', tz):
            return False
        hours = int(tz[1:3]); minutes = int(tz[4:6])
        return 0 <= hours <= 14 and minutes in {0, 15, 30, 45}