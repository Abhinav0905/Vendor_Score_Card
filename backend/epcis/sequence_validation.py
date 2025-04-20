from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Set, Any
from .utils import add_error, validate_dates_order

class EPCISSequenceValidator:
    """Validator for EPCIS event sequences according to DSCSA rules"""
    
    # Complete DSCSA event sequence steps
    EVENT_SEQUENCE = [
        'commissioning',      # Initial product serialization
        'packing',           # Aggregation into cases/pallets
        'shipping',          # Product leaving facility
        'receiving',         # Product arrival at destination
        'storing',           # Warehouse storage
        'dispensing',        # Final dispensing to patient
        'decommissioning',   # Product state change (destroyed/damaged)
        'returns'            # Product returns processing
    ]

    # Define the complete DSCSA chain-of-custody sequence rules
    SEQUENCE_RULES = {
        'commissioning': {
            'predecessors': [],  # No prerequisites
            'successors': ['packing', 'shipping', 'storing'],
            'required_fields': ['lotNumber', 'itemExpirationDate'],
            'allowed_dispositions': ['active', 'in_progress']
        },
        'packing': {
            'predecessors': ['commissioning'],
            'successors': ['shipping', 'storing'],
            'required_fields': ['parentID', 'childEPCs'],
            'allowed_dispositions': ['in_progress', 'active']
        },
        'shipping': {
            'predecessors': ['commissioning', 'packing'],
            'successors': ['receiving'],
            'required_fields': ['bizTransactionList', 'sourceList', 'destinationList'],
            'allowed_dispositions': ['in_transit']
        },
        'receiving': {
            'predecessors': ['shipping'],
            'successors': ['storing', 'dispensing', 'returns'],
            'required_fields': ['bizTransactionList'],
            'allowed_dispositions': ['in_progress', 'active']
        },
        'storing': {
            'predecessors': ['receiving', 'commissioning'],
            'successors': ['shipping', 'dispensing', 'decommissioning'],
            'allowed_dispositions': ['active', 'sellable_accessible']
        },
        'dispensing': {
            'predecessors': ['receiving', 'storing'],
            'successors': ['returns'],
            'allowed_dispositions': ['dispensed', 'partially_dispensed']
        },
        'decommissioning': {
            'predecessors': ['receiving', 'storing'],
            'successors': [],  # Terminal state
            'allowed_dispositions': ['destroyed', 'expired', 'recalled']
        },
        'returns': {
            'predecessors': ['dispensing', 'storing'],
            'successors': ['shipping', 'decommissioning'],
            'allowed_dispositions': ['returned'],
            'required_fields': ['bizTransactionList']
        }
    }

    def __init__(self):
        # Track commissioned and aggregated items
        self.commissioned_items: Dict[str, Set[str]] = {
            'SGTIN': set(),  # Track commissioned SGTINs
            'SSCC': set(),   # Track commissioned SSCCs
        }
        self.aggregated_items: Dict[str, str] = {}  # child_epc -> parent_epc
        self.event_times: Dict[str, Dict[str, datetime]] = defaultdict(dict)  # epc -> {step -> time}

    def validate_sequence(self, events: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Validate a sequence of EPCIS events
        
        Args:
            events: List of events to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        event_sequence = defaultdict(list)  # EPC -> list of (bizStep, time) tuples
        
        # First pass: collect all commissioned items
        for event in events:
            if event.get('bizStep', '').endswith('commissioning'):
                self._process_commissioning(event)
        
        # Second pass: validate event sequence
        for event in events:
            self._validate_event_sequence(event, event_sequence, errors)
            
        # Final validation of complete sequence
        self._validate_complete_sequence(event_sequence, errors)
        
        return errors

    def _process_commissioning(self, event: Dict[str, Any]):
        """Process commissioning event to track commissioned items"""
        epcs = event.get('epcList', [])
        for epc in epcs:
            if epc.startswith('urn:epc:id:sgtin:'):
                self.commissioned_items['SGTIN'].add(epc)
            elif epc.startswith('urn:epc:id:sscc:'):
                self.commissioned_items['SSCC'].add(epc)

    def _validate_event_sequence(self, event: Dict[str, Any], event_sequence: Dict[str, List], errors: List[Dict[str, str]]):
        """Validate single event in sequence context"""
        try:
            event_dt = datetime.fromisoformat(event['eventTime'].replace('Z', '+00:00'))
            biz_step = event.get('bizStep', '').split(':')[-1]
            epcs = event.get('epcList', []) + event.get('childEPCs', [])

            # date-order validation using recordTime
            if 'recordTime' in event:
                date_errors = validate_dates_order(event)
                if date_errors:
                    errors.extend(date_errors)

            # Validate each EPC's sequence
            for epc in epcs:
                # enforce chronological order per EPC
                prev_times = self.event_times.get(epc, {})
                if prev_times:
                    max_prev = max(prev_times.values())
                    if event_dt < max_prev:
                        add_error(errors, 'sequence', 'error',
                                  f"Event time {event_dt.isoformat()} for {biz_step} is before previous event time {max_prev.isoformat()} for {epc}")
                
                # Check if item was commissioned
                if epc.startswith('urn:epc:id:sgtin:'):
                    if epc not in self.commissioned_items['SGTIN']:
                        add_error(errors, 'sequence', 'error',
                                f"SGTIN {epc} not commissioned before {biz_step}")
                elif epc.startswith('urn:epc:id:sscc:'):
                    if epc not in self.commissioned_items['SSCC']:
                        add_error(errors, 'sequence', 'error',
                                f"SSCC {epc} not commissioned before {biz_step}")
                
                # Check sequence rules
                if biz_step in self.SEQUENCE_RULES:
                    # Check predecessors
                    valid_predecessors = self.SEQUENCE_RULES[biz_step]['predecessors']
                    if valid_predecessors:
                        predecessors = [step for step, _ in event_sequence[epc]]
                        if not any(pred in predecessors for pred in valid_predecessors):
                            add_error(errors, 'sequence', 'error',
                                    f"EPC {epc} has {biz_step} event without required predecessor(s): {valid_predecessors}")
                    
                    # Store event in sequence
                    event_sequence[epc].append((biz_step, event_dt))
                    self.event_times[epc][biz_step] = event_dt
                    
                    # Validate disposition
                    if 'disposition' in event:
                        disp = event['disposition'].split(':')[-1]
                        allowed_disp = self.SEQUENCE_RULES[biz_step]['allowed_dispositions']
                        if disp not in allowed_disp:
                            add_error(errors, 'sequence', 'error',
                                    f"Invalid disposition {disp} for {biz_step} event")
        
        except ValueError as e:
            add_error(errors, 'sequence', 'error',
                    f"Error processing event sequence: {str(e)}")

    def _validate_complete_sequence(self, event_sequence: Dict[str, List], errors: List[Dict[str, str]]):
        """Validate the complete sequence of events for all EPCs"""
        for epc, steps in event_sequence.items():
            # Sort steps by time
            steps.sort(key=lambda x: x[1])
            
            # Check for missing steps
            current_step_idx = -1
            for step, _ in steps:
                if step in self.EVENT_SEQUENCE:
                    step_idx = self.EVENT_SEQUENCE.index(step)
                    
                    # Check if step is out of order
                    if step_idx <= current_step_idx:
                        add_error(errors, 'sequence', 'error',
                                f"Out of order event for {epc}: {step} after {self.EVENT_SEQUENCE[current_step_idx]}")
                    current_step_idx = step_idx
            
            # Check for incomplete sequences
            if steps:
                last_step = steps[-1][0]
                if last_step not in ['dispensing', 'decommissioning', 'returns']:
                    add_error(errors, 'sequence', 'warning',
                            f"Incomplete sequence for {epc}: ends with {last_step}")

    def validate_packaging_hierarchy(self, events: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Validate packaging hierarchy across events"""
        errors = []
        for event in events:
            if event.get('eventType') == 'AggregationEvent':
                action = event.get('action')
                parent_id = event.get('parentID')
                child_epcs = event.get('childEPCs', [])
                
                if action == 'ADD':
                    # Validate parent-child relationships
                    for child in child_epcs:
                        if child in self.aggregated_items:
                            add_error(errors, 'hierarchy', 'error',
                                    f"Item {child} already aggregated to {self.aggregated_items[child]}")
                        else:
                            self.aggregated_items[child] = parent_id
                            
                elif action == 'DELETE':
                    # Validate disaggregation
                    for child in child_epcs:
                        if child in self.aggregated_items:
                            if self.aggregated_items[child] != parent_id:
                                add_error(errors, 'hierarchy', 'error',
                                        f"Cannot disaggregate {child} from {parent_id}, was aggregated to {self.aggregated_items[child]}")
                            del self.aggregated_items[child]
                        else:
                            add_error(errors, 'hierarchy', 'error',
                                    f"Cannot disaggregate {child}, was not previously aggregated")
        
        return errors