import logging
from datetime import datetime
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        return True
    except ValueError:
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
        return late_dt > early_dt
    except ValueError:
        return False

def add_error(errors: List[Dict[str, str]], error_type: str, severity: str, message: str):
    """Add an error to the error list with consistent format
    
    Args:
        errors: List to append error to
        error_type: Type of error (e.g., 'field', 'sequence', etc.)
        severity: Error severity ('error' or 'warning')
        message: Error message
    """
    errors.append({
        'type': error_type,
        'severity': severity,
        'message': message
    })

def extract_namespaces(xml_string: str) -> List[str]:
    """Extract namespace declarations from XML string
    
    Args:
        xml_string: XML document as string
        
    Returns:
        List of namespace URIs
    """
    import re
    ns_matches = re.findall(r'xmlns(?:\:\w+)?=[\"\']([^\"\']+)[\"\']', xml_string)
    return ns_matches