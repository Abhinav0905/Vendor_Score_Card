import os
import uuid
import logging
import hashlib
import re
import json
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from backend.models.epcis_submission import EPCISSubmission, ValidationError, FileStatus, ValidEPCISSubmission, ErroredEPCISSubmission
from backend.models.supplier import Supplier
from backend.models.base import SessionLocal
from . import EPCISValidator
from  . storage_handlers import LocalStorageHandler, S3StorageHandler
import xml.etree.ElementTree as ET


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SubmissionService:
    """Service for handling EPCIS file submissions"""
    
    def __init__(self):
        self.validator = EPCISValidator()
        
        # Initialize storage handler based on configuration
        storage_type = os.getenv('STORAGE_TYPE', 'local').lower()
        if storage_type == 's3':
            config = {
                'bucket_name': os.getenv('S3_BUCKET'),
                'region': os.getenv('AWS_REGION', 'us-east-1'),
                'aws_access_key': os.getenv('AWS_ACCESS_KEY_ID'),
                'aws_secret_key': os.getenv('AWS_SECRET_ACCESS_KEY')
            }
            self.storage = S3StorageHandler(config)
        else:
            config = {
                'base_path': os.path.join(os.path.dirname(__file__), '..', 'storage', 'epcis')
            }
            self.storage = LocalStorageHandler(config)
    
    def extract_vendor_from_filename(self, filename: str) -> Optional[str]:
        """Extract vendor name from filename following the pattern EPCIS_VENDORNAME_*"""
        patterns = [
            r'EPCIS[._-]([^._-]+)',  # Match EPCIS[-._]VENDORNAME
            r'EPCIS_([^_]+)_',       # Match EPCIS_VENDORNAME_
            r'([^_]+)_EPCIS_',       # Match VENDORNAME_EPCIS_
            r'([^_]+)_[0-9]+\.xml',  # Match VENDORNAME_12345.xml
            r'^([A-Za-z0-9]+)[._-]', # Match starting with VENDORNAME
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                vendor_name = match.group(1).upper()
                logger.info(f"Extracted vendor name '{vendor_name}' from filename: {filename}")
                return vendor_name
        
        logger.warning(f"Could not extract vendor name from filename: {filename}")
        return None
    
    def get_or_create_supplier(self, supplier_id: str, db) -> Supplier:
        """Get an existing supplier or create a new one"""
        supplier = db.query(Supplier).filter_by(id=supplier_id).first()
        if not supplier:
            # Check if we have a supplier with this name
            supplier = db.query(Supplier).filter_by(name=supplier_id).first()
            if supplier:
                return supplier
                
            # Create new supplier with id as supplier_<name>
            normalized_id = supplier_id.lower().replace(' ', '_')
            new_id = f"supplier_{normalized_id}"
            
            supplier = Supplier(
                id=new_id,
                name=supplier_id,  # Use original name for display
                is_active=True,
                data_accuracy=100.0,
                error_rate=0.0,
                compliance_score=100.0,
                response_time=0
            )
            db.add(supplier)
            db.commit()
            logger.info(f"Created new supplier: {supplier_id} with ID {new_id}")
        return supplier

    def find_error_line_numbers(self, file_content: bytes, is_xml: bool) -> Dict[str, int]:
        """Find line numbers for common validation issues"""
        try:
            if is_xml:
                return self._find_xml_error_lines(file_content)
            return self._find_json_error_lines(file_content)
        except Exception as e:
            logger.error(f"Error finding line numbers: {str(e)}")
            return {}

    def _find_xml_error_lines(self, file_content: bytes) -> Dict[str, int]:
        """Find line numbers for XML validation issues"""
        line_numbers = {}
        try:
            content_str = file_content.decode('utf-8')
            lines = content_str.splitlines()
            
            for i, line in enumerate(lines, 1):
                # Store line numbers by content for better error matching
                if '<ObjectEvent>' in line or '<AggregationEvent>' in line:
                    line_numbers['event'] = i
                
                # Mark locations of required fields
                if 'eventTime' in line:
                    line_numbers['eventTime'] = i
                if 'eventTimeZoneOffset' in line:
                    line_numbers['eventTimeZoneOffset'] = i
                if 'action' in line:
                    line_numbers['action'] = i
                if '<epc>' in line:
                    line_numbers['epc'] = i
                if '<bizStep>' in line:
                    line_numbers['bizStep'] = i

                # Store parent element line numbers
                if '<epcList>' in line:
                    line_numbers['epcList'] = i
                if '<bizTransactionList>' in line:
                    line_numbers['bizTransactionList'] = i

        except Exception as e:
            logger.error(f"Error processing XML for line numbers: {str(e)}")
        
        return line_numbers

    def _find_json_error_lines(self, file_content: bytes) -> Dict[str, int]:
        """Find line numbers for JSON validation issues"""
        line_numbers = {}
        try:
            # Convert bytes to string and split into lines
            content_str = file_content.decode('utf-8')
            lines = content_str.splitlines()
            
            # Look for common JSON validation points
            for i, line in enumerate(lines, 1):
                # Check for event types
                if '"type":' in line and any(event in line for event in ['ObjectEvent', 'AggregationEvent', 'TransactionEvent', 'TransformationEvent']):
                    line_numbers[f'event_{len(line_numbers)}'] = i
                
                # Check for required fields
                if any(field in line for field in ['"eventTime":', '"eventTimeZoneOffset":', '"action":']):
                    line_numbers[f'field_{len(line_numbers)}'] = i
                
                # Check for identifiers
                if any(id_field in line for id_field in ['"epcList":', '"bizTransactionList":', '"parentID":']):
                    line_numbers[f'identifier_{len(line_numbers)}'] = i
        except Exception as e:
            logger.error(f"Error processing JSON for line numbers: {str(e)}")
        
        return line_numbers

    def _validate_sgtin_format(self, sgtin_str):
        """
        Validates an SGTIN-198 formatted string.
        
        Expected format:
          urn:epc:id:sgtin:<CompanyPrefix>.<ItemReference>.<SerialNumber>
          
        - CompanyPrefix: one or more digits
        - ItemReference: one or more digits
        - SerialNumber: 1 to 20 alphanumeric characters
        
        Returns True if valid, otherwise False.
        """
        pattern = r"^urn:epc:id:sgtin:(\d+)\.(\d+)\.([A-Za-z0-9]{1,20})$"
        return bool(re.match(pattern, sgtin_str))
    
    def _extract_sgtin_identifiers(self, file_content, is_xml):
        """Extract SGTIN identifiers from file for pre-validation"""
        sgtins = []
        try:
            content_str = file_content.decode('utf-8')
            if is_xml:
                # Extraction using regex from top-level import
                matches = re.findall(r'urn:epc:id:sgtin:[^<"\s]+', content_str)
                sgtins.extend(matches)
            else:
                matches = re.findall(r'"urn:epc:id:sgtin:[^"]+', content_str)
                sgtins = [m.strip('"') for m in matches]
            
            return sgtins
        except Exception as e:
            logger.error(f"Error extracting SGTINs: {str(e)}")
            return []

    def extract_instance_identifier(self, file_content: bytes) -> Optional[str]:
        """Extract InstanceIdentifier from EPCIS document"""
        try:
            content_str = file_content.decode('utf-8')
            
            # For XML files
            if '<ns2:InstanceIdentifier>' in content_str or '<InstanceIdentifier>' in content_str:
                root = ET.fromstring(content_str)
                # Search for InstanceIdentifier with and without namespace
                for ns in ['{urn:gs1:epcis:epcis:xsd:1}', '']:
                    instance_id = root.find(f'.//{ns}InstanceIdentifier')
                    if instance_id is not None:
                        return instance_id.text
            
            # For JSON files (if you support JSON format)
            elif '"InstanceIdentifier":' in content_str:
                data = json.loads(content_str)
                if 'DocumentIdentification' in data:
                    return data['DocumentIdentification'].get('InstanceIdentifier')
            
            return None
        except Exception as e:
            logger.error(f"Error extracting InstanceIdentifier: {str(e)}")
            return None

    def check_duplicate_submission(self, file_hash: str, instance_identifier: Optional[str], db) -> Tuple[Optional[EPCISSubmission], str]:
        """Check for duplicate submission using both file hash and instance identifier"""
        if instance_identifier:
            # First check by instance identifier as it's more reliable
            existing = db.query(EPCISSubmission).filter_by(instance_identifier=instance_identifier).first()
            if existing:
                logger.info(f"Duplicate detected by instance identifier: {instance_identifier}")
                logger.info(f"Original submission: ID={existing.id}, File={existing.file_name}, Date={existing.submission_date}")
                return existing, "instance_identifier"
        
        # Fallback to file hash check
        existing = db.query(EPCISSubmission).filter_by(file_hash=file_hash).first()
        if existing:
            logger.info(f"Duplicate detected by file hash: {file_hash}")
            logger.info(f"Original submission: ID={existing.id}, File={existing.file_name}, Date={existing.submission_date}")
            return existing, "content_hash"
            
        return None, ""

    async def process_submission(self, file_content: bytes, file_name: str, supplier_id: Optional[str] = None) -> Dict[str, Any]:
        """Process an EPCIS file submission"""
        db = SessionLocal()
        try:
            # Extract supplier ID from filename if not provided
            if not supplier_id:
                supplier_id = self.extract_vendor_from_filename(file_name)
                if not supplier_id:
                    return {
                        'success': False,
                        'status_code': 400,
                        'message': 'Could not determine supplier ID from filename'
                    }

            # Extract instance identifier from document
            instance_identifier = self.extract_instance_identifier(file_content)
            if instance_identifier:
                logger.info(f"Extracted instance identifier from file: {instance_identifier}")
            
            # Calculate file hash
            file_hash = hashlib.sha256(file_content).hexdigest()
            logger.info(f"Calculated file hash: {file_hash}")

            # Check for duplicate submission using both methods
            existing_submission, duplicate_type = self.check_duplicate_submission(file_hash, instance_identifier, db)
            if existing_submission:
                return {
                    'success': False,
                    'status_code': 409,
                    'message': 'Duplicate submission detected',
                    'detail': {
                        'duplicate_type': duplicate_type,
                        'instance_identifier': instance_identifier,
                        'original_submission': {
                            'id': existing_submission.id,
                            'file_name': existing_submission.file_name,
                            'submission_date': existing_submission.submission_date.isoformat() if existing_submission.submission_date else None,
                            'status': existing_submission.status,
                            'instance_identifier': existing_submission.instance_identifier
                        }
                    }
                }

            # Get or create supplier
            supplier = self.get_or_create_supplier(supplier_id, db)
            if not supplier:
                return {
                    'success': False,
                    'status_code': 400,
                    'message': f'Invalid supplier ID: {supplier_id}'
                }

            # Store the file
            try:
                file_path = self.storage.store_file(
                    file_content=file_content,
                    file_name=file_name,
                    supplier_id=supplier.id
                )
                file_size = len(file_content)
            except Exception as e:
                logger.error(f"Error storing file: {str(e)}")
                return {
                    'success': False,
                    'status_code': 500,
                    'message': f'Error storing file: {str(e)}'
                }

            # Create submission record with instance identifier
            submission = EPCISSubmission(
                id=str(uuid.uuid4()),
                supplier_id=supplier.id,
                file_name=file_name,
                file_path=file_path,
                file_size=file_size,
                file_hash=file_hash,
                instance_identifier=instance_identifier,  # Store the instance identifier
                status=FileStatus.RECEIVED.value
            )
            db.add(submission)
            db.commit()

            # Validate the file
            validation_results = self.validator.validate_document(file_content, is_xml=file_name.lower().endswith('.xml'))
            
            # Update submission based on validation results
            submission.error_count = len([e for e in validation_results.get('errors', []) if e['severity'] == 'error'])
            submission.warning_count = len([e for e in validation_results.get('errors', []) if e['severity'] == 'warning'])
            submission.has_structure_errors = any(e['type'] == 'structure' for e in validation_results.get('errors', []))
            submission.has_sequence_errors = any(e['type'] == 'sequence' for e in validation_results.get('errors', []))
            submission.is_valid = submission.error_count == 0
            submission.status = FileStatus.VALIDATED.value if submission.is_valid else FileStatus.FAILED.value
            submission.processing_date = datetime.utcnow()

            # Create validation error records
            for error in validation_results.get('errors', []):
                validation_error = ValidationError(
                    id=str(uuid.uuid4()),
                    submission_id=submission.id,
                    error_type=error['type'],
                    severity=error['severity'],
                    message=error['message'],
                    line_number=error.get('line_number')
                )
                db.add(validation_error)

            # Create valid or errored submission record
            if submission.is_valid:
                valid_submission = ValidEPCISSubmission(
                    id=str(uuid.uuid4()),
                    master_submission_id=submission.id,
                    supplier_id=supplier.id,
                    file_name=file_name,
                    file_path=file_path,
                    file_size=file_size,
                    warning_count=submission.warning_count
                )
                db.add(valid_submission)
                submission.valid_submission_id = valid_submission.id
                logger.info(f"Valid submission record created: {valid_submission.id}")
            else:
                errored_submission = ErroredEPCISSubmission(
                    id=str(uuid.uuid4()),
                    master_submission_id=submission.id,
                    supplier_id=supplier.id,
                    file_name=file_name,
                    file_path=file_path,
                    file_size=file_size,
                    error_count=submission.error_count,
                    warning_count=submission.warning_count,
                    has_structure_errors=submission.has_structure_errors,
                    has_sequence_errors=submission.has_sequence_errors
                )
                db.add(errored_submission)
                submission.errored_submission_id = errored_submission.id

            submission.completion_date = datetime.utcnow()
            db.commit()
            
            logger.info(f"Validation records saved for submission: {submission.id}")
            
            return {
                'success': True,
                'status_code': 200,
                'message': 'File processed successfully',
                'submission_id': submission.id,
                'is_valid': submission.is_valid,
                'error_count': submission.error_count,
                'warning_count': submission.warning_count
            }

        except Exception as e:
            logger.error(f"Uncaught exception in process_submission: {str(e)}")
            logger.exception(e)
            if 'submission' in locals() and submission.id:
                try:
                    submission.status = FileStatus.FAILED.value
                    submission.completion_date = datetime.utcnow()
                    db.commit()
                except:
                    pass
            return {
                'success': False,
                'status_code': 500,
                'message': f'Internal server error: {str(e)}'
            }
        finally:
            db.close()