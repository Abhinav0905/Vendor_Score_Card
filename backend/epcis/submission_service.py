import os
import uuid
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from models.epcis_submission import EPCISSubmission, ValidationError, FileStatus
from models.supplier import Supplier
from models.base import SessionLocal
from .validator import EPCISValidator
from .storage_handlers import LocalStorageHandler, S3StorageHandler

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
    
    async def process_submission(
        self,
        file_content: bytes,
        file_name: str,
        supplier_id: str,
        submitter_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process an EPCIS file submission"""
        db = SessionLocal()
        try:
            # Generate a unique submission ID
            submission_id = str(uuid.uuid4())
            
            # Generate file hash for deduplication
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            # Check for duplicate submission
            existing = db.query(EPCISSubmission).filter_by(
                supplier_id=supplier_id,
                file_hash=file_hash
            ).first()
            
            if existing:
                return {
                    "success": False,
                    "message": "Duplicate submission detected",
                    "submission_id": existing.id,
                    "status": existing.status
                }
            
            # Determine file type
            is_xml = file_name.lower().endswith('.xml')
            
            # Store the file with a unique name to prevent collisions
            storage_filename = f"{submission_id}{os.path.splitext(file_name)[1]}"
            
            # Store the file using the appropriate storage handler
            file_location = self.storage.store_file(
                file_content=file_content,
                file_name=storage_filename, 
                supplier_id=supplier_id
            )
            
            # Create submission record
            submission = EPCISSubmission(
                id=submission_id,
                supplier_id=supplier_id,
                file_name=file_name,
                file_path=file_location,
                file_size=len(file_content),
                file_hash=file_hash,
                status=FileStatus.PROCESSING.value,
                submission_date=datetime.utcnow(),
                processing_date=datetime.utcnow()
            )
            
            # Save submission to database
            db.add(submission)
            db.commit()
            
            # Validate the file
            validation_result = self.validator.validate(file_content, is_xml=is_xml)
            
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
            submission.status = (
                FileStatus.VALIDATED.value if is_valid 
                else FileStatus.HELD.value
            )
            submission.is_valid = is_valid
            submission.error_count = error_count
            submission.warning_count = warning_count
            submission.completion_date = datetime.utcnow()
            submission.has_structure_errors = has_structure_errors
            submission.has_sequence_errors = has_sequence_errors
            
            # Save validation errors to database
            for error in errors:
                error_record = ValidationError(
                    id=str(uuid.uuid4()),
                    submission_id=submission_id,
                    error_type=error.get('type', 'unknown'),
                    severity=error.get('severity', 'error'),
                    message=error.get('message', 'Unknown error'),
                    created_at=datetime.utcnow()
                )
                db.add(error_record)
            
            db.commit()
            
            return {
                'success': is_valid,
                'message': (
                    'File successfully processed and validated' 
                    if is_valid 
                    else 'File processed but has validation errors'
                ),
                'submission_id': submission_id,
                'status': submission.status,
                'error_count': error_count,
                'warning_count': warning_count
            }
                
        except Exception as e:
            logger.exception(f"Error processing submission: {e}")
            if 'submission' in locals():
                submission.status = FileStatus.FAILED.value
                db.commit()
            return {
                'success': False,
                'message': f"Error processing submission: {str(e)}"
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
            
            return {
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
    
    def get_downloadable_url(self, submission_id: str) -> str:
        """Get a URL where the file can be downloaded"""
        db = SessionLocal()
        try:
            submission = db.query(EPCISSubmission).filter_by(id=submission_id).first()
            if not submission:
                raise ValueError(f"Submission {submission_id} not found")
            
            # Generate URL based on storage type
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