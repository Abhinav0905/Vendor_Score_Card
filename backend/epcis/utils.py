import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("epcis.utils")


class ErrorAggregator:
    def __init__(self):
        self.error_groups = defaultdict(list)
        
    def add_error(self, error_type: str, severity: str, message: str, line_number: int = None):
        """Add an error to be aggregated"""
        # Extract base message and identifier
        if 'for urn:epc:' in message:
            base_message, identifier = message.split('for urn:epc:', 1)
            base_message = base_message.strip()
            identifier = f"urn:epc:{identifier.strip()}"
        else:
            base_message = message
            identifier = None
            
        # Use line number as part of the key to prevent aggregation of errors from different lines
        # This ensures each line's errors are reported separately
        key = (error_type, severity, base_message, line_number)
        self.error_groups[key].append({
            'message': message,
            'identifier': identifier,
            'line_number': line_number
        })
    
    def get_aggregated_errors(self) -> List[Dict[str, Any]]:
        """Get the aggregated error list"""
        aggregated = []
        
        for (error_type, severity, base_message, line_number), errors in self.error_groups.items():
            if len(errors) == 1:
                error = errors[0]
                aggregated.append({
                    'type': error_type,
                    'severity': severity,
                    'message': error['message'],
                    'line_number': error['line_number']
                })
            else:
                # Create an aggregated message
                examples = [e['identifier'] for e in errors[:3] if e['identifier']]
                message = f"{base_message} ({len(errors)} items)"
                if examples:
                    message += f"\nExamples: {', '.join(examples)}"
                    if len(errors) > 3:
                        message += f"\n...and {len(errors) - 3} more"
                
                aggregated.append({
                    'type': error_type,
                    'severity': severity,
                    'message': message,
                    'count': len(errors),
                    'line_number': line_number
                })
                
                # Log only once for the group
                logger.warning(f"Aggregated {len(errors)} {severity} messages of type '{error_type}' at line {line_number}: {base_message}")
        
        return aggregated

# Global error aggregator instance
error_aggregator = ErrorAggregator()

def log_validation_warning(warning_type: str, message: str, line_number: int = None) -> None:
    """Log validation warnings with aggregation"""
    error_aggregator.add_error(warning_type, 'warning', message, line_number)
    
def log_validation_error(error_type: str, message: str, line_number: int = None) -> None:
    """Log validation errors with aggregation"""
    error_aggregator.add_error(error_type, 'error', message, line_number)

def get_aggregated_validation_results() -> List[Dict[str, Any]]:
    """Get aggregated validation results and clear the aggregator"""
    results = error_aggregator.get_aggregated_errors()
    error_aggregator.error_groups.clear()
    return results

def validate_date_format(date_str: str, format: str = "%Y-%m-%d") -> bool:
    """Validate if a string matches the expected date format
    
    Args:
        date_str: Date string to validate
        format: Expected date format (default: YYYY-MM-DD)
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        datetime.strptime(date_str, format)
        logger.debug(f"Date validation successful for: {date_str}")
        return True
    except ValueError as e:
        log_validation_warning('date_format', f"Date validation failed for '{date_str}' with format '{format}': {str(e)}")
        return False

def validate_dates_order(earlier_date: str, later_date: str, format: str = "%Y-%m-%d") -> bool:
    """Validate that one date is after another
    
    Args:
        earlier_date: The date that should be earlier
        later_date: The date that should be later
        format: Date format (default: YYYY-MM-DD)
        
    Returns:
        bool: True if later_date is after earlier_date
    """
    try:
        early_dt = datetime.strptime(earlier_date, format)
        late_dt = datetime.strptime(later_date, format)
        is_valid = late_dt > early_dt
        if not is_valid:
            log_validation_warning('date_order', f"Date order validation failed: {later_date} is not after {earlier_date}")
        return is_valid
    except ValueError as e:
        log_validation_error('date_order', f"Date order validation error: {str(e)}")
        return False

def extract_namespaces(xml_string: str) -> List[str]:
    """Extract namespace declarations from XML string
    
    Args:
        xml_string: XML document as string
        
    Returns:
        List of namespace URIs
    """
    import re
    ns_matches = re.findall(r'xmlns(?:\:\w+)?=[\"\']([^\"\']+)[\"\']', xml_string)
    if ns_matches:
        logger.debug(f"Extracted {len(ns_matches)} namespaces from XML")
    else:
        log_validation_warning('namespace', "No namespaces found in XML document")
    return ns_matches

def add_error(errors: List[Dict[str, Any]], error_type: str, severity: str, message: str, line_number: Optional[int] = None) -> None:
    """Add an error to the list of validation errors
    
    Args:
        errors: List to append the error to
        error_type: Type of error (e.g., 'structure', 'field', 'sequence')
        severity: Error severity ('error' or 'warning')
        message: Error message
        line_number: Line number where the error occurred (optional)
    """
    error = {
        'type': error_type,
        'severity': severity,
        'message': message
    }
    if line_number is not None:
        error['line_number'] = line_number
    errors.append(error)
    
    # Also log the error using our logging system
    if severity == 'error':
        logger.error(f"{error_type}: {message}")
    else:
        logger.warning(f"{error_type}: {message}")