"""Tests for email models"""

import pytest
from datetime import datetime
from email_agent.models.email_models import (
    EmailData, ExtractedData, ValidationError, ActionPlan, AgentState
)


class TestEmailModels:
    """Test cases for email data models"""
    
    def test_email_data_creation(self):
        """Test EmailData model creation"""
        email = EmailData(
            message_id="test_123",
            subject="Test Subject",
            sender="test@example.com",
            body="Test body content",
            attachments=[],
            received_date="2024-01-15T10:30:00Z"
        )
        
        assert email.message_id == "test_123"
        assert email.subject == "Test Subject"
        assert email.sender == "test@example.com"
        assert email.body == "Test body content"
        assert email.attachments == []
        assert email.received_date == "2024-01-15T10:30:00Z"
    
    def test_extracted_data_creation(self):
        """Test ExtractedData model creation"""
        data = ExtractedData(
            po_number="PO12345",
            lot_number="LOT123",
            vendor_name="Test Vendor",
            vendor_email="vendor@example.com",
            error_description="Test error",
            extracted_fields={"key": "value"}
        )
        
        assert data.po_number == "PO12345"
        assert data.lot_number == "LOT123"
        assert data.vendor_name == "Test Vendor"
        assert data.vendor_email == "vendor@example.com"
        assert data.error_description == "Test error"
        assert data.extracted_fields == {"key": "value"}
    
    def test_validation_error_creation(self):
        """Test ValidationError model creation"""
        error = ValidationError(
            error_type="SEQUENCE_ERROR",
            severity="HIGH",
            description="Test error description",
            location="Event #1",
            recommendation="Fix the issue"
        )
        
        assert error.error_type == "SEQUENCE_ERROR"
        assert error.severity == "HIGH"
        assert error.description == "Test error description"
        assert error.location == "Event #1"
        assert error.recommendation == "Fix the issue"
    
    def test_action_plan_creation(self):
        """Test ActionPlan model creation"""
        plan = ActionPlan(
            vendor_name="Test Vendor",
            vendor_email="vendor@example.com",
            po_number="PO12345",
            lot_number="LOT123",
            summary="Test summary",
            recommendations=["Fix 1", "Fix 2"],
            email_subject="Test Subject",
            email_body_text="Text body",
            email_body_html="<html>HTML body</html>"
        )
        
        assert plan.vendor_name == "Test Vendor"
        assert plan.vendor_email == "vendor@example.com"
        assert plan.po_number == "PO12345"
        assert plan.lot_number == "LOT123"
        assert plan.summary == "Test summary"
        assert plan.recommendations == ["Fix 1", "Fix 2"]
        assert plan.email_subject == "Test Subject"
        assert plan.email_body_text == "Text body"
        assert plan.email_body_html == "<html>HTML body</html>"
    
    def test_agent_state_creation(self):
        """Test AgentState model creation"""
        now = datetime.now()
        state = AgentState(
            emails=[],
            current_email=None,
            extracted_data=None,
            validation_errors=[],
            action_plan=None,
            processed_count=0,
            failed_count=0,
            start_time=now
        )
        
        assert state.emails == []
        assert state.current_email is None
        assert state.extracted_data is None
        assert state.validation_errors == []
        assert state.action_plan is None
        assert state.processed_count == 0
        assert state.failed_count == 0
        assert state.start_time == now
    
    def test_extracted_data_optional_fields(self):
        """Test ExtractedData with optional fields"""
        data = ExtractedData(
            po_number="PO12345",
            lot_number=None,  # Optional
            vendor_name="Test Vendor",
            vendor_email="vendor@example.com",
            error_description="Test error",
            extracted_fields={}  # Empty dict
        )
        
        assert data.po_number == "PO12345"
        assert data.lot_number is None
        assert data.extracted_fields == {}
    
    def test_validation_error_severity_validation(self):
        """Test ValidationError severity validation"""
        # Valid severities
        for severity in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            error = ValidationError(
                error_type="TEST_ERROR",
                severity=severity,
                description="Test description",
                location="Test location",
                recommendation="Test recommendation"
            )
            assert error.severity == severity
    
    def test_model_serialization(self):
        """Test model serialization to dict"""
        email = EmailData(
            message_id="test_123",
            subject="Test Subject",
            sender="test@example.com",
            body="Test body",
            attachments=[],
            received_date="2024-01-15T10:30:00Z"
        )
        
        email_dict = email.dict()
        
        assert email_dict["message_id"] == "test_123"
        assert email_dict["subject"] == "Test Subject"
        assert email_dict["sender"] == "test@example.com"
        assert email_dict["body"] == "Test body"
        assert email_dict["attachments"] == []
        assert email_dict["received_date"] == "2024-01-15T10:30:00Z"
    
    def test_model_json_serialization(self):
        """Test model JSON serialization"""
        data = ExtractedData(
            po_number="PO12345",
            lot_number="LOT123",
            vendor_name="Test Vendor",
            vendor_email="vendor@example.com",
            error_description="Test error",
            extracted_fields={"key": "value"}
        )
        
        json_str = data.json()
        assert isinstance(json_str, str)
        assert "PO12345" in json_str
        assert "LOT123" in json_str
        assert "Test Vendor" in json_str
