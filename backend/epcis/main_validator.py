from typing import Dict
from .parser import EPCISParser
from .event_validation import EPCISEventValidator
from .sequence_validation import EPCISSequenceValidator
from .utils import logger

class EPCISValidator:
    """Main validator class that orchestrates EPCIS document validation"""
    
    def __init__(self):
        self.parser = EPCISParser()
        self.event_validator = EPCISEventValidator()
        self.sequence_validator = EPCISSequenceValidator()

    def validate_document(self, content: bytes, is_xml: bool = True) -> Dict:
        """Validate an EPCIS document
        
        Args:
            content: Raw document content
            is_xml: Whether content is XML (True) or JSON (False)
            
        Returns:
            Dict containing validation results and errors
        """
        try:
            # Parse document
            header, events, companies, parse_errors = self.parser.parse_document(content, is_xml)
            errors = parse_errors.copy()
            
            if not errors:
                # Validate individual events
                for event in events:
                    event_errors = self.event_validator.validate_event(event, companies)
                    errors.extend(event_errors)
                
                # Validate event sequence
                sequence_errors = self.sequence_validator.validate_sequence(events)
                errors.extend(sequence_errors)
                
                # Validate packaging hierarchy
                hierarchy_errors = self.sequence_validator.validate_packaging_hierarchy(events)
                errors.extend(hierarchy_errors)
            
            # Determine overall validity
            is_valid = len([e for e in errors if e['severity'] == 'error']) == 0
            
            return {
                'valid': is_valid,
                'header': header,
                'eventCount': len(events),
                'companies': list(companies),
                'errors': errors
            }
            
        except Exception as e:
            logger.exception(f"Validation error: {e}")
            return {
                'valid': False,
                'errors': [{
                    'type': 'system',
                    'severity': 'error',
                    'message': f"System error during validation: {str(e)}"
                }]
            }

    def summarize_errors(self, validation_result: Dict) -> Dict:
        """Generate a summary of validation errors
        
        Args:
            validation_result: Result from validate_document()
            
        Returns:
            Dict containing error summary
        """
        errors = validation_result.get('errors', [])
        summary = {
            'total': len(errors),
            'errors': len([e for e in errors if e['severity'] == 'error']),
            'warnings': len([e for e in errors if e['severity'] == 'warning']),
            'by_type': {},
            'critical_issues': []
        }
        
        # Group errors by type
        for error in errors:
            error_type = error['type']
            if error_type not in summary['by_type']:
                summary['by_type'][error_type] = {
                    'total': 0,
                    'errors': 0,
                    'warnings': 0
                }
            
            summary['by_type'][error_type]['total'] += 1
            if error['severity'] == 'error':
                summary['by_type'][error_type]['errors'] += 1
            else:
                summary['by_type'][error_type]['warnings'] += 1
            
            # Track critical sequence and hierarchy errors
            if error['severity'] == 'error' and error_type in ['sequence', 'hierarchy']:
                summary['critical_issues'].append(error['message'])
        
        return summary