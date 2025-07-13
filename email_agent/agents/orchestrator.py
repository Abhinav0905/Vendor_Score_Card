"""
Main Orchestrator Agent that coordinates all sub-agents for EPCIS error correction workflow
"""
import logging
from pathlib import Path
import sys
from typing import List, Dict, Any
from datetime import datetime
import asyncio

from langchain.schema import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from email_agent.models.email_models import EmailData, AgentState, ValidationError, ActionPlan
from email_agent.config.settings import Settings
from email_agent.services.gmail_service import GmailService
from email_agent.services.database_service import DatabaseService
from email_agent.agents.email_processor import EmailProcessorAgent
from email_agent.agents.epcis_analyzer import EPCISAnalyzerAgent
from email_agent.agents.vendor_communicator import VendorCommunicatorAgent

# Add parent directory to path to access backend modules
parent_dir = Path(__file__).resolve().parents[3]
sys.path.append(str(parent_dir))


logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Main orchestrator that coordinates all sub-agents"""
    
    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self.llm = ChatOpenAI(
            model=self.settings.OPENAI_MODEL,
            temperature=0.1,
            api_key=self.settings.OPENAI_API_KEY
        )
        
        # Initialize services
        self.gmail_service = GmailService(self.settings)
        self.db_service = DatabaseService(self.settings)
        
        # Initialize sub-agents
        self.email_processor = EmailProcessorAgent(self.settings)
        self.epcis_analyzer = EPCISAnalyzerAgent(self.settings)
        self.vendor_communicator = VendorCommunicatorAgent(self.settings)
        
        # Build workflow graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the agent workflow using LangGraph"""
        
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("fetch_emails", self._fetch_emails)
        workflow.add_node("process_all_emails", self._process_all_emails)
        
        # Set entry point
        workflow.set_entry_point("fetch_emails")
        
        # Add edges
        workflow.add_edge("fetch_emails", "process_all_emails")
        workflow.add_edge("process_all_emails", END)
        
        return workflow.compile()
    
    async def run(self) -> Dict[str, Any]:
        """Run the complete email processing workflow"""
        logger.info("Starting EPCIS Error Correction Agent workflow")
        
        try:
            initial_state = AgentState(
                emails=[],
                current_email=None,
                extracted_data=None,
                validation_errors=[],
                action_plan=None,
                processed_count=0,
                failed_count=0,
                start_time=datetime.now()
            )
            
            result = await self.workflow.ainvoke(initial_state)
            
            logger.info(f"Workflow completed. Processed: {result.get('processed_count', 0)}, "
                       f"Failed: {result.get('failed_count', 0)}")
            
            return {
                "status": "completed",
                "processed_count": result.get("processed_count", 0),
                "failed_count": result.get("failed_count", 0),
                "duration": (datetime.now() - result.get("start_time", datetime.now())).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Workflow failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "processed_count": 0,
                "failed_count": 0
            }
    
    async def _fetch_emails(self, state: AgentState) -> AgentState:
        """Fetch and parse new error emails from Gmail"""
        logger.info("Fetching new error emails...")
        
        try:
            raw_emails = await self.gmail_service.get_error_emails(
                max_results=self.settings.MAX_EMAILS_PER_RUN
            )
            
            if not raw_emails:
                logger.info("No new error emails found.")
                state.emails = []
                return state

            logger.info(f"Found {len(raw_emails)} raw emails. Extracting content...")

            # Extract content from all emails concurrently
            extracted_email_tasks = [
                self.gmail_service.extract_email_content(email)
                for email in raw_emails
            ]
            extracted_email_data = await asyncio.gather(*extracted_email_tasks)

            # Create EmailData models from the extracted content
            email_models = []
            for email_data in extracted_email_data:
                if "error" not in email_data:
                    try:
                        email_models.append(EmailData(**email_data))
                    except Exception as e:
                        logger.error(f"Pydantic validation failed for email {email_data.get('message_id')}: {e}")
                else:
                    logger.warning(f"Skipping email due to extraction error: {email_data['error']}")

            logger.info(f"Successfully extracted and validated {len(email_models)} emails.")
            state.emails = email_models
            
        except Exception as e:
            logger.error(f"Failed to fetch or process emails: {str(e)}", exc_info=True)
            state.emails = []
        
        return state
    
    async def _process_all_emails(self, state: AgentState) -> AgentState:
        """Process all emails from the initial state."""
        if not state.emails:
            logger.info("No emails to process.")
            state.processed_count = 0
            state.failed_count = 0
            return state

        processed_count = 0
        failed_count = 0

        for email_data in state.emails:
            try:
                logger.info(f"--- Starting processing for email: {email_data.subject} ---")
                
                # Create a self-contained state for processing a single email
                single_email_state = AgentState(
                    current_email=email_data, 
                    start_time=state.start_time,
                    emails=[] # Clear list for single processing
                )

                # 1. Extract Data
                extracted_state = await self._extract_data(single_email_state)
                if not extracted_state.extracted_data:
                    logger.error(f"Data extraction failed for {email_data.subject}. Skipping.")
                    failed_count += 1
                    continue

                # 2. Lookup Database Information
                enriched_state = await self._lookup_database_info(extracted_state)
                if not enriched_state.extracted_data:
                    logger.error(f"Database lookup failed for {email_data.subject}. Skipping.")
                    failed_count += 1
                    continue

                # 3. Validate EPCIS
                validated_state = await self._validate_epcis(enriched_state)
                if not validated_state.validation_errors:
                    logger.info(f"No validation errors for {email_data.subject}. Marking as processed.")
                    await self._update_status(validated_state)
                    processed_count += 1
                    continue

                # 4. Generate Action Plan - Handle multiple PO/LOT combinations
                all_pos = enriched_state.extracted_data.extracted_fields.get('all_po_numbers', [])
                all_lots = enriched_state.extracted_data.extracted_fields.get('all_lot_numbers', [])
                
                # Filter out invalid PO numbers (like 'NDING', 'SENDER')
                valid_pos = [po for po in all_pos if po.isdigit() and len(po) >= 5]
                valid_lots = [lot for lot in all_lots if lot.isdigit()]
                
                if not valid_pos:
                    valid_pos = [enriched_state.extracted_data.po_number]
                if not valid_lots:
                    valid_lots = [enriched_state.extracted_data.lot_number] if enriched_state.extracted_data.lot_number else ['']
                
                # Create pairs of PO/LOT combinations
                po_lot_pairs = []
                for i, po in enumerate(valid_pos):
                    lot = valid_lots[i] if i < len(valid_lots) else (valid_lots[0] if valid_lots else '')
                    po_lot_pairs.append((po, lot))
                
                logger.info(f"Processing {len(po_lot_pairs)} PO/LOT combinations: {po_lot_pairs}")
                
                # Create a comprehensive action plan with all PO/LOT combinations
                # Use the first PO/LOT for the main action plan, but include all pairs in the email content
                first_po, first_lot = po_lot_pairs[0] if po_lot_pairs else (enriched_state.extracted_data.po_number, enriched_state.extracted_data.lot_number)
                
                temp_extracted_data = enriched_state.extracted_data
                temp_extracted_data.po_number = first_po
                temp_extracted_data.lot_number = first_lot
                # Add all pairs to extracted_fields instead of creating new attribute
                temp_extracted_data.extracted_fields['all_po_lot_pairs'] = po_lot_pairs
                
                action_plan = await self.vendor_communicator.generate_action_plan(
                    temp_extracted_data,
                    validated_state.validation_errors,
                    enriched_state.current_email
                )
                
                # Use the validated_state as planned_state
                planned_state = validated_state
                planned_state.action_plan = action_plan
                
                if not planned_state.action_plan or not planned_state.action_plan.recommendations:
                    logger.error(f"Action plan generation failed or was empty for {email_data.subject}. Skipping.")
                    failed_count += 1
                    continue

                # 5. Send Response - Send ONE email with all PO/LOT combinations
                await self._send_response(planned_state)
                
                # 6. Update Status
                await self._update_status(planned_state)
                
                processed_count += 1
                logger.info(f"--- Successfully processed email: {email_data.subject} ---")

            except Exception as e:
                logger.critical(f"An unhandled exception occurred while processing email {email_data.subject}: {e}", exc_info=True)
                failed_count += 1
                continue

        # Use a copy to set final counts without modifying the input state directly
        final_state = state.copy(deep=True)
        final_state.processed_count = processed_count
        final_state.failed_count = failed_count
        return final_state
    
    async def _extract_data(self, state: AgentState) -> AgentState:
        """Extract PO/LOT numbers and vendor info from email"""
        try:
            extracted_data = await self.email_processor.process_email(state.current_email)
            state.extracted_data = extracted_data
            logger.info(f"Extracted data: PO={extracted_data.po_number}, LOT={extracted_data.lot_number}")
            
        except Exception as e:
            logger.error(f"Failed to extract data: {str(e)}")
            state.extracted_data = None
        
        return state
    
    async def _lookup_database_info(self, state: AgentState) -> AgentState:
        """Lookup PO/LOT information from database and enrich vendor details"""
        try:
            extracted_data = state.extracted_data
            
            # Get all PO numbers to lookup
            all_pos = extracted_data.extracted_fields.get('all_po_numbers', [])
            valid_pos = [po for po in all_pos if po.isdigit() and len(po) >= 5]
            
            if not valid_pos:
                valid_pos = [extracted_data.po_number] if extracted_data.po_number else []
            
            if not valid_pos:
                logger.warning("No valid PO numbers found for database lookup")
                return state
            
            logger.info(f"Looking up database information for PO numbers: {valid_pos}")
            
            # Lookup information for each PO
            enriched_vendor_info = {}
            po_details = {}
            
            for po_number in valid_pos:
                try:
                    # Query database for PO information
                    po_info = await self.db_service.get_po_information(po_number)
                    
                    if po_info:
                        po_details[po_number] = po_info
                        logger.info(f"Found database info for PO {po_number}: {po_info.get('vendor_name', 'Unknown')}")
                        
                        # Enrich vendor information with database data
                        if not enriched_vendor_info:  # Use first PO's vendor info as primary
                            enriched_vendor_info = {
                                'vendor_name': po_info.get('vendor_name', extracted_data.vendor_name),
                                'vendor_email': po_info.get('vendor_email', extracted_data.vendor_email),
                                'vendor_contact': po_info.get('vendor_contact'),
                                'vendor_phone': po_info.get('vendor_phone'),
                                'vendor_address': po_info.get('vendor_address'),
                                'primary_contact': po_info.get('primary_contact'),
                            }
                    else:
                        logger.warning(f"No database information found for PO {po_number}")
                        
                except Exception as e:
                    logger.error(f"Error looking up PO {po_number}: {str(e)}")
                    continue
            
            # Update extracted data with enriched information
            if enriched_vendor_info:
                # Update vendor details
                extracted_data.vendor_name = enriched_vendor_info.get('vendor_name', extracted_data.vendor_name)
                extracted_data.vendor_email = enriched_vendor_info.get('vendor_email', extracted_data.vendor_email)
                
                # Add database information to extracted_fields
                extracted_data.extracted_fields['database_vendor_info'] = enriched_vendor_info
                extracted_data.extracted_fields['po_details'] = po_details
                
                logger.info(f"Enriched vendor information: {extracted_data.vendor_name} ({extracted_data.vendor_email})")
            else:
                logger.warning("No database information found for any PO numbers")
                # Still proceed with email-extracted data
            
            state.extracted_data = extracted_data
            
        except Exception as e:
            logger.error(f"Failed to lookup database information: {str(e)}")
            # Don't fail the entire process, continue with email-extracted data
        
        return state
    
    async def _validate_epcis(self, state: AgentState) -> AgentState:
        """Validate EPCIS data and identify errors"""
        try:
            validation_errors = await self.epcis_analyzer.analyze_errors(
                state.extracted_data,
                state.current_email
            )
            state.validation_errors = validation_errors
            logger.info(f"Found {len(validation_errors)} validation errors")
            
        except Exception as e:
            logger.error(f"Failed to validate EPCIS: {str(e)}")
            state.validation_errors = []
        
        return state
    
    async def _generate_action_plan(self, state: AgentState) -> AgentState:
        """Generate action plan for error correction"""
        try:
            action_plan = await self.vendor_communicator.generate_action_plan(
                state.extracted_data,
                state.validation_errors,
                state.current_email
            )
            state.action_plan = action_plan
            logger.info(f"Generated action plan with {len(action_plan.recommendations)} recommendations")
            
        except Exception as e:
            logger.error(f"Failed to generate action plan: {str(e)}")
            state.action_plan = None
        
        return state
    
    async def _send_response(self, state: AgentState) -> AgentState:
        """Send correction email to vendor"""
        try:
            await self.vendor_communicator.send_correction_email(
                state.action_plan,
                state.extracted_data,
                state.current_email
            )
            logger.info(f"Sent correction email to {state.current_email.sender}")
            
        except Exception as e:
            logger.error(f"Failed to send response email: {str(e)}")
            raise
        
        return state
    
    async def _update_status(self, state: AgentState) -> AgentState:
        """Update email status and labels"""
        try:
            await self.gmail_service.mark_email_processed(state.current_email.message_id)
            logger.info(f"Marked email {state.current_email.message_id} as processed")
            
        except Exception as e:
            logger.error(f"Failed to update email status: {str(e)}")
        
        return state
    
    async def process_single_email_by_id(self, message_id: str) -> Dict[str, Any]:
        """Process a single email by message ID (for testing/debugging)"""
        try:
            email = await self.gmail_service.get_email_by_id(message_id)
            if not email:
                return {"status": "error", "message": "Email not found"}
            
            state = AgentState(
                emails=[email],
                current_email=email,
                processed_count=0,
                failed_count=0,
                start_time=datetime.now()
            )
            
            # Process single email
            state = await self._extract_data(state)
            state = await self._lookup_database_info(state)
            state = await self._validate_epcis(state)
            state = await self._generate_action_plan(state)
            state = await self._send_response(state)
            state = await self._update_status(state)
            
            return {
                "status": "success",
                "message": "Email processed successfully",
                "extracted_data": state.extracted_data.dict() if state.extracted_data else None,
                "validation_errors": [error.dict() for error in state.validation_errors],
                "action_plan": state.action_plan.dict() if state.action_plan else None
            }
            
        except Exception as e:
            logger.error(f"Failed to process single email: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        is_gmail_connected = await self.gmail_service.is_authenticated()
        is_db_connected = self.db_service.test_connection()

        return {
            "agent_name": self.settings.AGENT_NAME,
            "status": "ready",
            "gmail_connected": is_gmail_connected,
            "database_connected": is_db_connected,
            "settings": {
                "max_emails_per_run": self.settings.MAX_EMAILS_PER_RUN,
                "openai_model": self.settings.OPENAI_MODEL,
                "error_email_label": self.settings.ERROR_EMAIL_LABEL
            }
        }
