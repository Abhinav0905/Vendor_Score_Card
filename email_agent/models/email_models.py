"""Email data models for the EPCIS Error Correction Agent"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class EmailData(BaseModel):
    """Model for email data"""
    message_id: str
    subject: str
    sender: str
    body: str
    attachments: List[str] = Field(default_factory=list)
    received_date: str


class ExtractedData(BaseModel):
    """Model for extracted data from emails"""
    po_number: str
    lot_number: Optional[str] = None
    vendor_name: str
    vendor_email: str
    error_description: str
    error_types: List[str] = Field(default_factory=list)
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)


class ValidationError(BaseModel):
    """Model for validation errors"""
    error_type: str
    severity: str
    description: str
    location: str
    recommendation: str

class ActionPlan(BaseModel):
    """Model for vendor action plan"""
    summary: str = "No EPCIS errors found"
    email_subject: str = "EPCIS Validation Results"
    email_body_text: str = "No action required"
    email_body_html: str = "<p>No action required</p>"
    po_number: str = "UNKNOWN"
    vendor_name: str = "UNKNOWN"
    vendor_email: str = "UNKNOWN"
    due_date: Optional[datetime] = None
    error_count: int = 0
    recommendations: List[str] = Field(default_factory=list)

# class ActionPlan(BaseModel):
#     """Model for action plans"""
#     vendor_name: str
#     vendor_email: str
#     po_number: str
#     lot_number: Optional[str] = None
#     summary: str
#     recommendations: List[str]
#     email_subject: str
#     email_body_text: str
#     email_body_html: str


class AgentState(BaseModel):
    """Model for agent state during workflow execution"""
    emails: List[EmailData] = Field(default_factory=list)
    current_email: Optional[EmailData] = None
    extracted_data: Optional[ExtractedData] = None
    validation_errors: List[ValidationError] = Field(default_factory=list)
    action_plan: Optional[ActionPlan] = None
    processed_count: int = 0
    failed_count: int = 0
    start_time: datetime

    class Config:
        arbitrary_types_allowed = True
