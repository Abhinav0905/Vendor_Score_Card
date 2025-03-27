import os
import uuid
import logging
import hashlib
import traceback
import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from models.epcis_submission import EPCISSubmission, ValidationError, FileStatus, ValidEPCISSubmission, ErroredEPCISSubmission
from models.supplier import Supplier
from models.base import SessionLocal
from . import EPCISValidator
from .storage_handlers import LocalStorageHandler, S3StorageHandler
import xml.etree.ElementTree as ET
import json
from collections import defaultdict

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

    async def process_submission(
        self,
        file_content: bytes,
        file_name: str,
        supplier_id: Optional[str] = None,
        submitter_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process an EPCIS file submission"""
        db = SessionLocal()
        submission_id = str(uuid.uuid4())
        
        try:
            # Try to extract vendor from filename if not provided
            if not supplier_id:
                extracted_supplier = self.extract_vendor_from_filename(file_name)
                if extracted_supplier:
                    supplier_id = extracted_supplier
                    logger.info(f"Extracted supplier ID '{supplier_id}' from filename: {file_name}")
                else:
                    supplier_id = "unknown"
                    logger.warning(f"Could not extract supplier ID from filename: {file_name}")
            
            # Get or create supplier
            supplier = self.get_or_create_supplier(supplier_id, db)
            
            logger.info(f"Processing new submission: {file_name} for supplier: {supplier_id}")
            
            # Generate file hash for deduplication
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            # Check for duplicate submission
            existing = db.query(EPCISSubmission).filter_by(
                supplier_id=supplier.id,  # Use the normalized supplier ID
                file_hash=file_hash
            ).first()
            
            if existing:
                logger.info(f"Duplicate submission detected for file: {file_name}")
                return {
                    "success": False,
                    "message": "Duplicate submission detected",
                    "submission_id": existing.id,
                    "status": existing.status,
                    "status_code": 409
                }
            
            # Determine file type and find potential error locations
            is_xml = file_name.lower().endswith('.xml')
            error_line_numbers = self.find_error_line_numbers(file_content, is_xml)
            
            # Store the file with a unique name to prevent collisions
            storage_filename = f"{submission_id}{os.path.splitext(file_name)[1]}"
            
            logger.info(f"Storing file: {storage_filename} for submission: {submission_id}")
            
            try:
                file_location = self.storage.store_file(
                    file_content=file_content,
                    file_name=storage_filename, 
                    supplier_id=supplier.id  # Use the normalized supplier ID
                )
                logger.info(f"File stored successfully at: {file_location}")
            except Exception as storage_error:
                logger.error(f"Failed to store file: {str(storage_error)}")
                return {
                    "success": False,
                    "message": f"Failed to store file: {str(storage_error)}",
                    "error": str(storage_error),
                    "status_code": 500
                }
            
            # Create master submission record
            submission = EPCISSubmission(
                id=submission_id,
                supplier_id=supplier.id,  # Use the normalized supplier ID
                file_name=file_name,
                file_path=file_location,
                file_size=len(file_content),
                file_hash=file_hash,
                status=FileStatus.PROCESSING.value,
                submission_date=datetime.utcnow(),
                processing_date=datetime.utcnow()
            )
            
            # Save submission to database
            try:
                db.add(submission)
                db.commit()
                logger.info(f"Submission record created: {submission_id}")
            except Exception as db_error:
                logger.error(f"Database error when creating submission: {str(db_error)}")
                db.rollback()
                return {
                    "success": False,
                    "message": f"Database error: {str(db_error)}",
                    "error": str(db_error),
                    "status_code": 500
                }
            
            # Validate the file
            try:
                logger.info(f"Validating file for submission: {submission_id}")
                validation_result = self.validator.validate_document(file_content, is_xml=is_xml)
                logger.info(f"Validation complete for submission: {submission_id}")
                logger.info(f"Validation result: {validation_result}")
                
                # Find potential error line numbers
                error_line_numbers = self.find_error_line_numbers(file_content, is_xml=is_xml)
                
                # Attach line numbers to validation errors
                errors = validation_result.get('errors', [])
                for error in errors:
                    error_type = error.get('type', '')
                    message = error.get('message', '').lower()
                    
                    # Map common error messages to line numbers
                    if 'eventtime' in message:
                        error['line_number'] = error_line_numbers.get('eventTime')
                    elif 'timezone' in message:
                        error['line_number'] = error_line_numbers.get('eventTimeZoneOffset')
                    elif 'action' in message:
                        error['line_number'] = error_line_numbers.get('action')
                    elif 'epc' in message:
                        error['line_number'] = error_line_numbers.get('epc')
                    elif 'transaction' in message:
                        error['line_number'] = error_line_numbers.get('bizTransactionList')
                    elif 'step' in message:
                        error['line_number'] = error_line_numbers.get('bizStep')
                    else:
                        # Default to event line number for other errors
                        error['line_number'] = error_line_numbers.get('event')

                validation_result['errors'] = errors
                
            except Exception as validation_error:
                logger.error(f"Validation error: {str(validation_error)}")
                submission.status = FileStatus.FAILED.value
                submission.completion_date = datetime.utcnow()
                db.commit()
                return {
                    "success": False,
                    "message": f"Validation error: {str(validation_error)}",
                    "submission_id": submission_id,
                    "status": FileStatus.FAILED.value,
                    "status_code": 400
                }
            
            # Process validation results
            is_valid = validation_result.get('valid', False)
            errors = validation_result.get('errors', [])
            
            # Count errors and warnings
            error_count = sum(1 for e in errors if e.get('severity') == 'error')
            warning_count = sum(1 for e in errors if e.get('severity') == 'warning')
            
            # Determine if there are structure or sequence errors
            has_structure_errors = any(e.get('type') == 'structure' for e in errors)
            has_sequence_errors = any(e.get('type') == 'sequence' for e in errors)
            
            # Update submission status
            submission.status = FileStatus.VALIDATED.value if is_valid else FileStatus.HELD.value
            submission.is_valid = is_valid
            submission.error_count = error_count
            submission.warning_count = warning_count
            submission.completion_date = datetime.utcnow()
            submission.has_structure_errors = has_structure_errors
            submission.has_sequence_errors = has_sequence_errors
            
            # Create specialized submission record based on validation result
            if is_valid:
                # Create valid submission record
                valid_submission_id = str(uuid.uuid4())
                valid_submission = ValidEPCISSubmission(
                    id=valid_submission_id,
                    master_submission_id=submission_id,
                    supplier_id=supplier.id,  # Use the normalized supplier ID
                    file_name=file_name,
                    file_path=file_location,
                    file_size=len(file_content),
                    warning_count=warning_count,
                    processed_event_count=validation_result.get('eventCount', 0),
                    insertion_date=datetime.utcnow()
                )
                db.add(valid_submission)
                submission.valid_submission_id = valid_submission_id
                logger.info(f"Valid submission record created: {valid_submission_id}")
            else:
                # Create errored submission record
                errored_submission_id = str(uuid.uuid4())
                errored_submission = ErroredEPCISSubmission(
                    id=errored_submission_id,
                    master_submission_id=submission_id,
                    supplier_id=supplier.id,  # Use the normalized supplier ID
                    file_name=file_name,
                    file_path=file_location,
                    file_size=len(file_content),
                    error_count=error_count,
                    warning_count=warning_count,
                    has_structure_errors=has_structure_errors,
                    has_sequence_errors=has_sequence_errors,
                    insertion_date=datetime.utcnow(),
                    last_error_date=datetime.utcnow()
                )
                db.add(errored_submission)
                submission.errored_submission_id = errored_submission_id
                logger.info(f"Errored submission record created: {errored_submission_id}")
            
            # Save validation errors to database
            try:
                aggregated_errors = self._aggregate_validation_errors(errors)
                for error in aggregated_errors:
                    error_record = ValidationError(
                        id=str(uuid.uuid4()),
                        submission_id=submission_id,
                        error_type=error.get('type', 'unknown'),
                        severity=error.get('severity', 'error'),
                        message=error.get('message', 'Unknown error'),
                        line_number=error.get('line_number'),
                        created_at=datetime.utcnow()
                    )
                    db.add(error_record)
                
                db.commit()
                logger.info(f"Validation records saved for submission: {submission_id}")
            except Exception as error_save_error:
                logger.error(f"Error saving validation results: {str(error_save_error)}")
                db.rollback()
                submission.status = FileStatus.FAILED.value
                db.commit()
                return {
                    "success": False,
                    "message": f"Error saving validation results: {str(error_save_error)}",
                    "submission_id": submission_id,
                    "status": FileStatus.FAILED.value,
                    "status_code": 500
                }
            
            # Update supplier metrics
            try:
                # Update supplier's last submission date
                supplier.last_submission_date = datetime.utcnow()
                
                # Update error rate
                total_submissions = db.query(EPCISSubmission).filter_by(supplier_id=supplier.id).count()
                error_submissions = db.query(EPCISSubmission).filter_by(
                    supplier_id=supplier.id,
                    is_valid=False
                ).count()
                
                if total_submissions > 0:
                    supplier.error_rate = (error_submissions / total_submissions) * 100
                    supplier.data_accuracy = 100 - supplier.error_rate
                
                db.commit()
            except Exception as e:
                logger.error(f"Error updating supplier metrics: {str(e)}")
                # Don't fail the submission if metrics update fails
            
            response = {
                'success': True,
                'message': 'File processed successfully',
                'submission_id': submission_id,
                'supplier_id': supplier.id,
                'supplier_name': supplier.name,
                'status': submission.status,
                'error_count': error_count,
                'warning_count': warning_count,
                'is_valid': is_valid,
                'errors': errors,  # Always include errors in the response
                'status_code': 200
            }
            
            return response
                
        except Exception as e:
            logger.exception(f"Uncaught exception in process_submission: {e}")
            error_traceback = traceback.format_exc()
            logger.error(f"Traceback: {error_traceback}")
            
            try:
                if 'submission' in locals() and submission.id:
                    submission.status = FileStatus.FAILED.value
                    db.commit()
            except Exception:
                pass
                
            return {
                'success': False,
                'message': f"Error processing submission: {str(e)}",
                'error': str(e),
                'status_code': 500
            }
        finally:
            db.close()
            
    def get_valid_submission(self, submission_id: str) -> Dict[str, Any]:
        """Get details of a valid submission"""
        db = SessionLocal()
        try:
            valid_submission = db.query(ValidEPCISSubmission).filter_by(id=submission_id).first()
            if not valid_submission:
                return {
                    'success': False,
                    'message': f"Valid submission {submission_id} not found"
                }
                
            # Update last accessed date
            valid_submission.last_accessed_date = datetime.utcnow()
            db.commit()
            
            return {
                'success': True,
                'submission': {
                    'id': valid_submission.id,
                    'master_submission_id': valid_submission.master_submission_id,
                    'supplier_id': valid_submission.supplier_id,
                    'file_name': valid_submission.file_name,
                    'file_path': valid_submission.file_path,
                    'file_size': valid_submission.file_size,
                    'warning_count': valid_submission.warning_count,
                    'processed_event_count': valid_submission.processed_event_count,
                    'insertion_date': valid_submission.insertion_date.isoformat(),
                    'last_accessed_date': valid_submission.last_accessed_date.isoformat() if valid_submission.last_accessed_date else None
                }
            }
        finally:
            db.close()
    
    def get_errored_submission(self, submission_id: str) -> Dict[str, Any]:
        """Get details of an errored submission"""
        db = SessionLocal()
        try:
            errored_submission = db.query(ErroredEPCISSubmission).filter_by(id=submission_id).first()
            if not errored_submission:
                return {
                    'success': False,
                    'message': f"Errored submission {submission_id} not found"
                }
            
            # Get validation errors from master submission
            master_submission = db.query(EPCISSubmission).filter_by(id=errored_submission.master_submission_id).first()
            errors = []
            
            if master_submission:
                errors = db.query(ValidationError).filter_by(submission_id=master_submission.id).all()
            
            return {
                'success': True,
                'submission': {
                    'id': errored_submission.id,
                    'master_submission_id': errored_submission.master_submission_id,
                    'supplier_id': errored_submission.supplier_id,
                    'file_name': errored_submission.file_name,
                    'file_path': errored_submission.file_path,
                    'file_size': errored_submission.file_size,
                    'error_count': errored_submission.error_count,
                    'warning_count': errored_submission.warning_count,
                    'has_structure_errors': errored_submission.has_structure_errors,
                    'has_sequence_errors': errored_submission.has_sequence_errors,
                    'insertion_date': errored_submission.insertion_date.isoformat(),
                    'last_error_date': errored_submission.last_error_date.isoformat() if errored_submission.last_error_date else None,
                    'is_resolved': errored_submission.is_resolved,
                    'resolution_date': errored_submission.resolution_date.isoformat() if errored_submission.resolution_date else None,
                    'resolved_by': errored_submission.resolved_by,
                    'errors': [
                        {
                            'id': error.id,
                            'type': error.error_type,
                            'severity': error.severity,
                            'message': error.message,
                            'line_number': error.line_number,
                            'is_resolved': error.is_resolved,
                            'resolution_note': error.resolution_note,
                            'resolved_at': error.resolved_at.isoformat() if error.resolved_at else None,
                            'resolved_by': error.resolved_by
                        }
                        for error in errors
                    ]
                }
            }
        finally:
            db.close()
            
    def get_submission(self, submission_id: str) -> Dict[str, Any]:
        """Get submission details by ID"""
        db = SessionLocal()
        try:
            submission = db.query(EPCISSubmission).filter_by(id=submission_id).first()
            if not submission:
                return {
                    'success': False,
                    'message': f"Submission {submission_id} not found"
                }
            
            # Get validation errors
            errors = db.query(ValidationError).filter_by(submission_id=submission_id).all()
            
            result = {
                'success': True,
                'submission': {
                    'id': submission.id,
                    'supplier_id': submission.supplier_id,
                    'file_name': submission.file_name,
                    'file_path': submission.file_path,
                    'file_size': submission.file_size,
                    'status': submission.status,
                    'submission_date': submission.submission_date.isoformat(),
                    'processing_date': submission.processing_date.isoformat() if submission.processing_date else None,
                    'completion_date': submission.completion_date.isoformat() if submission.completion_date else None,
                    'is_valid': submission.is_valid,
                    'error_count': submission.error_count,
                    'warning_count': submission.warning_count,
                    'has_structure_errors': submission.has_structure_errors,
                    'has_sequence_errors': submission.has_sequence_errors,
                    'errors': [
                        {
                            'id': error.id,
                            'type': error.error_type,
                            'severity': error.severity,
                            'message': error.message,
                            'line_number': error.line_number,
                            'is_resolved': error.is_resolved,
                            'resolution_note': error.resolution_note,
                            'resolved_at': error.resolved_at.isoformat() if error.resolved_at else None,
                            'resolved_by': error.resolved_by
                        }
                        for error in errors
                    ]
                }
            }
            
            # Add references to specialized tables
            if submission.valid_submission_id:
                result['submission']['valid_submission_id'] = submission.valid_submission_id
            
            if submission.errored_submission_id:
                result['submission']['errored_submission_id'] = submission.errored_submission_id
                
            return result
        finally:
            db.close()
    
    def get_downloadable_url(self, submission_id: str) -> str:
        """Get a URL where the file can be downloaded"""
        db = SessionLocal()
        try:
            submission = db.query(EPCISSubmission).filter_by(id=submission_id).first()
            if not submission:
                raise ValueError(f"Submission {submission_id} not found")
            
            return self.storage.generate_presigned_url(submission.file_path)
        finally:
            db.close()
    
    def resolve_error(
        self, 
        error_id: str, 
        resolution_note: str,
        resolved_by: str
    ) -> Dict[str, Any]:
        """Resolve a validation error"""
        db = SessionLocal()
        try:
            error = db.query(ValidationError).filter_by(id=error_id).first()
            if not error:
                return {
                    'success': False,
                    'message': f"Error {error_id} not found"
                }
            
            error.is_resolved = True
            error.resolution_note = resolution_note
            error.resolved_at = datetime.utcnow()
            error.resolved_by = resolved_by
            
            # Check if all errors for this submission are resolved
            submission = db.query(EPCISSubmission).filter_by(id=error.submission_id).first()
            
            if submission:
                unresolved_errors = db.query(ValidationError).filter_by(
                    submission_id=submission.id,
                    severity='error',
                    is_resolved=False
                ).count()
                
                if unresolved_errors == 0 and submission.status == FileStatus.HELD.value:
                    submission.status = FileStatus.REPROCESSED.value
            
            db.commit()
            
            return {
                'success': True,
                'message': 'Error successfully resolved',
                'submission_status': submission.status if submission else None
            }
        finally:
            db.close()
    
    def _aggregate_validation_errors(self, errors):
        """Aggregate similar validation errors to reduce duplication"""
        error_groups = defaultdict(list)
        
        # First pass - group by type, severity, and base message
        for error in errors:
            if not isinstance(error, dict):
                continue
                
            message = error.get('message', '')
            # Extract base message (everything before the specific ID)
            if 'for urn:epc:' in message:
                base_message = message.split('for urn:epc:')[0].strip()
            else:
                base_message = message
                
            key = (error.get('type', ''), error.get('severity', ''), base_message)
            error_groups[key].append(error)
        
        # Second pass - create aggregated messages
        aggregated = []
        for (error_type, severity, base_message), group in error_groups.items():
            if len(group) == 1:
                # Single error - keep as is
                aggregated.append(group[0])
            else:
                # Multiple similar errors - create aggregated message
                example_ids = []
                for err in group[:3]:  # Take first 3 as examples
                    if 'for urn:epc:' in err['message']:
                        id_part = err['message'].split('for urn:epc:')[1].strip()
                        example_ids.append(f"urn:epc:{id_part}")
                
                agg_message = f"{base_message} ({len(group)} items)"
                if example_ids:
                    agg_message += f"\nExamples: {', '.join(example_ids)}"
                    if len(group) > 3:
                        agg_message += f"\n...and {len(group) - 3} more"
                
                aggregated.append({
                    'type': error_type,
                    'severity': severity,
                    'message': agg_message,
                    'count': len(group),
                    'line_number': group[0].get('line_number')  # Use line number from first occurrence
                })
        
        return aggregated