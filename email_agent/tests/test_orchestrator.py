"""Tests for the main orchestrator agent"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from email_agent.agents.orchestrator import EmailProcessingOrchestrator
from email_agent.models.email_models import AgentState, EmailData


class TestOrchestratorAgent:
    """Test cases for the OrchestratorAgent"""
    
    @pytest.fixture
    def orchestrator(self, mock_settings):
        """Create orchestrator agent with mocked dependencies"""
        with             patch('email_agent.agents.orchestrator.GmailService'), \
             patch('email_agent.agents.orchestrator.DatabaseService'), \
             patch('email_agent.agents.orchestrator.EmailProcessorAgent'), \
             patch('email_agent.agents.orchestrator.EPCISAnalyzerAgent'), \
             patch('email_agent.agents.orchestrator.VendorCommunicatorAgent'), \
             patch('email_agent.agents.orchestrator.ChatOpenAI'):
            
            return EmailProcessingOrchestrator()
    
    def test_init(self, orchestrator, mock_settings):
        """Test orchestrator initialization"""
        assert orchestrator.settings == mock_settings
        assert orchestrator.gmail_service is not None
        assert orchestrator.db_service is not None
        assert orchestrator.email_processor is not None
        assert orchestrator.epcis_analyzer is not None
        assert orchestrator.vendor_communicator is not None
        assert orchestrator.workflow is not None
    
    @pytest.mark.asyncio
    async def test_fetch_emails(self, orchestrator, sample_email_data):
        """Test email fetching functionality"""
        # Mock the gmail service
        orchestrator.gmail_service.get_error_emails = AsyncMock(
            return_value=[sample_email_data]
        )
        
        # Create initial state
        state = AgentState(
            emails=[],
            processed_count=0,
            failed_count=0,
            start_time=datetime.now()
        )
        
        # Test fetching emails
        result_state = await orchestrator._fetch_emails(state)
        
        # Verify results
        assert len(result_state.emails) == 1
        assert result_state.emails[0] == sample_email_data
        orchestrator.gmail_service.get_error_emails.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_data(self, orchestrator, sample_extracted_data, sample_email_data):
        """Test data extraction functionality"""
        # Mock the email processor
        orchestrator.email_processor.extract_data = AsyncMock(
            return_value=sample_extracted_data
        )
        
        # Create state with current email
        state = AgentState(
            emails=[sample_email_data],
            current_email=sample_email_data,
            processed_count=0,
            failed_count=0,
            start_time=datetime.now()
        )
        
        # Test data extraction
        result_state = await orchestrator._extract_data(state)
        
        # Verify results
        assert result_state.extracted_data == sample_extracted_data
        orchestrator.email_processor.extract_data.assert_called_once_with(sample_email_data)
    
    @pytest.mark.asyncio
    async def test_validate_epcis(self, orchestrator, sample_validation_error, sample_extracted_data):
        """Test EPCIS validation functionality"""
        # Mock the EPCIS analyzer
        orchestrator.epcis_analyzer.analyze_errors = AsyncMock(
            return_value=[sample_validation_error]
        )
        
        # Create state with extracted data
        state = AgentState(
            emails=[],
            extracted_data=sample_extracted_data,
            validation_errors=[],
            processed_count=0,
            failed_count=0,
            start_time=datetime.now()
        )
        
        # Test EPCIS validation
        result_state = await orchestrator._validate_epcis(state)
        
        # Verify results
        assert len(result_state.validation_errors) == 1
        assert result_state.validation_errors[0] == sample_validation_error
        orchestrator.epcis_analyzer.analyze_errors.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_action_plan(self, orchestrator, sample_action_plan, sample_validation_error):
        """Test action plan generation"""
        # Mock the vendor communicator
        orchestrator.vendor_communicator.generate_action_plan = AsyncMock(
            return_value=sample_action_plan
        )
        
        # Create state with validation errors
        state = AgentState(
            emails=[],
            validation_errors=[sample_validation_error],
            action_plan=None,
            processed_count=0,
            failed_count=0,
            start_time=datetime.now()
        )
        
        # Test action plan generation
        result_state = await orchestrator._generate_action_plan(state)
        
        # Verify results
        assert result_state.action_plan == sample_action_plan
        orchestrator.vendor_communicator.generate_action_plan.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_response(self, orchestrator, sample_action_plan, sample_email_data):
        """Test response sending"""
        # Mock the vendor communicator
        orchestrator.vendor_communicator.send_correction_email = AsyncMock()
        
        # Create state with action plan
        state = AgentState(
            emails=[],
            current_email=sample_email_data,
            action_plan=sample_action_plan,
            processed_count=0,
            failed_count=0,
            start_time=datetime.now()
        )
        
        # Test response sending
        result_state = await orchestrator._send_response(state)
        
        # Verify results
        orchestrator.vendor_communicator.send_correction_email.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_status(self, orchestrator, sample_email_data):
        """Test status update functionality"""
        # Mock the gmail service
        orchestrator.gmail_service.mark_email_processed = AsyncMock()
        
        # Create state with current email
        state = AgentState(
            emails=[],
            current_email=sample_email_data,
            processed_count=0,
            failed_count=0,
            start_time=datetime.now()
        )
        
        # Test status update
        result_state = await orchestrator._update_status(state)
        
        # Verify results
        orchestrator.gmail_service.mark_email_processed.assert_called_once_with(
            sample_email_data.message_id
        )
    
    def test_get_status(self, orchestrator):
        """Test status retrieval"""
        # Mock service statuses
        orchestrator.gmail_service.is_authenticated = Mock(return_value=True)
        orchestrator.db_service.test_connection = Mock(return_value=True)
        
        # Get status
        status = orchestrator.get_status()
        
        # Verify results
        assert status["status"] == "ready"
        assert status["gmail_connected"] is True
        assert status["database_connected"] is True
        assert "settings" in status
    
    @pytest.mark.asyncio
    async def test_process_single_email_by_id_success(self, orchestrator, sample_email_data, 
                                                      sample_extracted_data, sample_validation_error, 
                                                      sample_action_plan):
        """Test processing single email by ID - success case"""
        # Mock all dependencies
        orchestrator.gmail_service.get_email_by_id = AsyncMock(return_value=sample_email_data)
        orchestrator.email_processor.extract_data = AsyncMock(return_value=sample_extracted_data)
        orchestrator.epcis_analyzer.analyze_errors = AsyncMock(return_value=[sample_validation_error])
        orchestrator.vendor_communicator.generate_action_plan = AsyncMock(return_value=sample_action_plan)
        orchestrator.vendor_communicator.send_correction_email = AsyncMock()
        orchestrator.gmail_service.mark_email_processed = AsyncMock()
        
        # Test processing single email
        result = await orchestrator.process_single_email_by_id("test_message_123")
        
        # Verify results
        assert result["status"] == "success"
        assert "extracted_data" in result
        assert "validation_errors" in result
        assert "action_plan" in result
    
    @pytest.mark.asyncio
    async def test_process_single_email_by_id_not_found(self, orchestrator):
        """Test processing single email by ID - email not found"""
        # Mock email not found
        orchestrator.gmail_service.get_email_by_id = AsyncMock(return_value=None)
        
        # Test processing single email
        result = await orchestrator.process_single_email_by_id("nonexistent_id")
        
        # Verify results
        assert result["status"] == "error"
        assert "Email not found" in result["message"]
    
    @pytest.mark.asyncio
    async def test_run_workflow_success(self, orchestrator, sample_email_data):
        """Test complete workflow execution - success case"""
        # Mock all workflow steps
        orchestrator.gmail_service.get_error_emails = AsyncMock(return_value=[sample_email_data])
        orchestrator._process_single_email = AsyncMock()
        
        # Mock workflow compilation and execution
        mock_workflow = AsyncMock()
        mock_workflow.ainvoke = AsyncMock(return_value={
            "processed_count": 1,
            "failed_count": 0,
            "start_time": datetime.now()
        })
        orchestrator.workflow = mock_workflow
        
        # Test workflow execution
        result = await orchestrator.run()
        
        # Verify results
        assert result["status"] == "completed"
        assert result["processed_count"] == 1
        assert result["failed_count"] == 0
        assert "duration" in result
