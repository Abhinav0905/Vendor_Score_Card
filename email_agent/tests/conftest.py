"""Test configuration and fixtures"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from email_agent.config.settings import Settings
from email_agent.models.email_models import EmailData, ExtractedData, ValidationError, ActionPlan

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as requiring asyncio"
    )

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for asyncio tests"""
    try:
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()
    finally:
        asyncio.set_event_loop(None)

@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    settings = Mock(spec=Settings)
    settings.OPENAI_API_KEY = "test_key"
    settings.OPENAI_MODEL = "gpt-3.5-turbo"
    settings.DATABASE_URL = "sqlite:///:memory:"
    settings.MAX_EMAILS_PER_RUN = 5
    settings.ERROR_EMAIL_LABEL = "TEST_ERRORS"
    settings.PROCESSED_EMAIL_LABEL = "TEST_PROCESSED"
    return settings

@pytest.fixture
def sample_email_data():
    """Sample email data for testing"""
    return EmailData(
        message_id="test_message_123",
        subject="EPCIS Validation Error - PO12345",
        sender="vendor@example.com",
        body="There was an error with PO number 12345 and LOT number ABC123",
        attachments=[],
        received_date="2024-01-15T10:30:00Z"
    )

@pytest.fixture
def sample_extracted_data():
    """Sample extracted data for testing"""
    return ExtractedData(
        po_number="PO12345",
        lot_number="LOT123",
        vendor_name="Test Vendor",
        vendor_email="vendor@example.com",
        error_description="EPCIS validation failed",
        extracted_fields={"supplier_id": "SUP001"}
    )

@pytest.fixture
def sample_validation_error():
    """Sample validation error for testing"""
    return ValidationError(
        error_type="SEQUENCE_ERROR",
        severity="HIGH",
        description="Invalid sequence in EPCIS events",
        location="Event #3",
        recommendation="Ensure proper event sequencing"
    )

@pytest.fixture
def sample_action_plan():
    """Sample action plan for testing"""
    return ActionPlan(
        vendor_name="Test Vendor",
        vendor_email="vendor@example.com",
        po_number="PO12345",
        lot_number="LOT123",
        summary="EPCIS validation errors found",
        recommendations=[
            "Fix event sequencing in EPCIS file",
            "Validate identifier formats",
            "Check timestamp consistency"
        ],
        email_subject="Action Required: EPCIS Validation Errors - PO12345",
        email_body_text="Please see attached recommendations...",
        email_body_html="<html>Please see attached recommendations...</html>"
    )

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing"""
    client = AsyncMock()
    client.chat.completions.create = AsyncMock()
    return client

@pytest.fixture
def mock_gmail_service():
    """Mock Gmail service for testing"""
    service = AsyncMock()
    service.get_error_emails = AsyncMock(return_value=[])
    service.send_email = AsyncMock()
    service.mark_email_processed = AsyncMock()
    service.is_authenticated = Mock(return_value=True)
    return service

@pytest.fixture
def mock_database_service():
    """Mock database service for testing"""
    service = AsyncMock()
    service.search_po_lot = AsyncMock(return_value=None)
    service.test_connection = Mock(return_value=True)
    return service
