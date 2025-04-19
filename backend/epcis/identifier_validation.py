import re
from typing import Dict, Optional

class GS1IdentifierValidator:
    """Validator for GS1 identifiers (SGTIN, SSCC, SGLN, etc.)"""
    
    # GS1 identifier patterns
    EPC_PATTERNS = {
        # Updated SGTIN pattern to properly validate SGTIN-198 format:
        # <CompanyPrefix>.<ItemReference>.<SerialNumber>
        # Where SerialNumber must be 1-20 alphanumeric characters
        'sgtin': r'^urn:epc:id:sgtin:(\d+)\.(\d+)\.([A-Za-z0-9]{1,20})$',
        'sscc': r'^urn:epc:id:sscc:\d+\.[0-9]+$',
        'sgln': r'^urn:epc:id:sgln:\d+\.[0-9]+\.*[0-9]*$',
        'grai': r'^urn:epc:id:grai:\d+\.[0-9]+\.*[0-9]*$',
        'giai': r'^urn:epc:id:giai:\d+\.*[0-9]+$',
    }

    @staticmethod
    def calculate_gs1_check_digit(number_str: str) -> str:
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

    @staticmethod
    def validate_gs1_check_digit(full_number: str) -> bool:
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
        
        return GS1IdentifierValidator.calculate_gs1_check_digit(number) == check_digit

    @classmethod
    def validate_epc_format(cls, epc: str) -> bool:
        """Validate if an EPC matches any of the valid patterns
        
        Args:
            epc: EPC string to validate
            
        Returns:
            bool: True if EPC matches a valid pattern
        """
        return any(re.match(pattern, epc) for pattern in cls.EPC_PATTERNS.values())

    @classmethod
    def get_epc_type(cls, epc: str) -> Optional[str]:
        """Get the type of an EPC (sgtin, sscc, etc.)
        
        Args:
            epc: EPC string to check
            
        Returns:
            str: EPC type if valid, None if invalid
        """
        if not epc:
            return None
            
        for epc_type, pattern in cls.EPC_PATTERNS.items():
            if re.match(pattern, epc):
                return epc_type
        return None

    @staticmethod
    def extract_company_prefix(epc: str) -> Optional[str]:
        """Extract company prefix from an EPC
        
        Args:
            epc: EPC string
            
        Returns:
            str: Company prefix if found, None otherwise
        """
        if not epc:
            return None
            
        parts = epc.split(':')
        if len(parts) >= 5:
            company_parts = parts[4].split('.')
            if company_parts:
                return company_parts[0]
        return None

    @staticmethod
    def validate_company_prefix(epc: str, authorized_companies: set) -> bool:
        """Validate that EPC company prefix is in authorized set
        
        Args:
            epc: EPC string
            authorized_companies: Set of authorized company prefixes
            
        Returns:
            bool: True if company prefix is authorized
        """
        company_prefix = GS1IdentifierValidator.extract_company_prefix(epc)
        return company_prefix in authorized_companies if company_prefix else False