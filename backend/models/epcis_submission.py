from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .base import Base

class FileStatus(enum.Enum):
    """Enum for submission file status"""
    RECEIVED = "received"
    PROCESSING = "processing"
    VALIDATED = "validated"
    FAILED = "failed"
    HELD = "held"
    REPROCESSED = "reprocessed"

class EPCISSubmission(Base):
    """Master EPCIS file submission tracking model"""
    __tablename__ = "epcis_submissions"
    
    id = Column(String, primary_key=True)
    supplier_id = Column(String, nullable=False)
    
    # File information
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Storage location
    file_size = Column(Integer, nullable=True)
    file_hash = Column(String, nullable=True)  # For deduplication
    instance_identifier = Column(String, nullable=True)  # Unique document instance identifier
    
    # Processing status
    status = Column(String, nullable=False)
    is_valid = Column(Boolean, default=False)
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    
    # Error flags
    has_structure_errors = Column(Boolean, default=False)
    has_sequence_errors = Column(Boolean, default=False)
    
    # Timestamps
    submission_date = Column(DateTime, default=datetime.utcnow)
    processing_date = Column(DateTime, nullable=True)
    completion_date = Column(DateTime, nullable=True)
    
    # Submitter information
    submitter_id = Column(String, nullable=True)
    
    # Relationships
    errors = relationship("ValidationError", back_populates="submission", cascade="all, delete-orphan")
    
    # References to specialized submissions
    valid_submission_id = Column(String, nullable=True)
    errored_submission_id = Column(String, nullable=True)
    
    def __repr__(self):
        return f"<EPCISSubmission(id='{self.id}', file_name='{self.file_name}', status='{self.status}')>"

class ValidEPCISSubmission(Base):
    """Model for valid EPCIS file submissions"""
    __tablename__ = "valid_epcis_submissions"
    
    id = Column(String, primary_key=True)
    master_submission_id = Column(String, ForeignKey("epcis_submissions.id"), nullable=False)
    supplier_id = Column(String, nullable=False)
    
    # File information
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Storage location
    file_size = Column(Integer, nullable=True)
    
    # Processing information
    warning_count = Column(Integer, default=0)
    processed_event_count = Column(Integer, default=0)
    
    # Timestamps
    insertion_date = Column(DateTime, default=datetime.utcnow)
    last_accessed_date = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<ValidEPCISSubmission(id='{self.id}', file_name='{self.file_name}')>"

class ErroredEPCISSubmission(Base):
    """Model for EPCIS file submissions with errors"""
    __tablename__ = "errored_epcis_submissions"
    
    id = Column(String, primary_key=True)
    master_submission_id = Column(String, ForeignKey("epcis_submissions.id"), nullable=False)
    supplier_id = Column(String, nullable=False)
    
    # File information
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Storage location
    file_size = Column(Integer, nullable=True)
    
    # Error information
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    has_structure_errors = Column(Boolean, default=False)
    has_sequence_errors = Column(Boolean, default=False)
    
    # Timestamps
    insertion_date = Column(DateTime, default=datetime.utcnow)
    last_error_date = Column(DateTime, nullable=True)
    
    # Resolution information
    is_resolved = Column(Boolean, default=False)
    resolution_date = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)
    
    def __repr__(self):
        return f"<ErroredEPCISSubmission(id='{self.id}', file_name='{self.file_name}', resolved={self.is_resolved})>"

class ValidationError(Base):
    """Model for validation errors in EPCIS submissions"""
    __tablename__ = "validation_errors"
    
    id = Column(String, primary_key=True)
    submission_id = Column(String, ForeignKey("epcis_submissions.id"))
    
    # Error information
    error_type = Column(String, nullable=False)  # structure, field, sequence
    severity = Column(String, nullable=False)  # error, warning
    message = Column(Text, nullable=False)
    line_number = Column(Integer, nullable=True)  # Line number in the file where error occurred
    
    # Error resolution
    is_resolved = Column(Boolean, default=False)
    resolution_note = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    submission = relationship("EPCISSubmission", back_populates="errors")
    
    def __repr__(self):
        return f"<ValidationError(id='{self.id}', type='{self.error_type}', severity='{self.severity}', resolved={self.is_resolved})>"