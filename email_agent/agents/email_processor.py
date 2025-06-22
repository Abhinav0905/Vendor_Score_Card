import re
import logging
from typing import List, Dict, Any, Optional
from langchain.tools import Tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from models import ExtractedData, EmailData
from config import settings

logger = logging.getLogger(__name__)

class EmailProcessorAgent:
    """AI Agent for processing and extracting data from emails"""
    
    def __init__(self, settings=None):
        self.settings = settings or settings
        self.llm = ChatOpenAI(
            model=self.settings.OPENAI_MODEL,
            temperature=0.1,
            api_key=self.settings.OPENAI_API_KEY
        )
        self.agent = self._create_agent()
    
    def _create_agent(self):
        """Create the email processing agent"""
        
        # Define tools for the agent
        tools = [
            Tool(
                name="extract_po_numbers",
                description="Extract Purchase Order (PO) numbers from text",
                func=self._extract_po_numbers
            ),
            Tool(
                name="extract_lot_numbers", 
                description="Extract LOT numbers from text",
                func=self._extract_lot_numbers
            ),
            Tool(
                name="extract_vendor_info",
                description="Extract vendor name and contact information from text",
                func=self._extract_vendor_info
            ),
            Tool(
                name="extract_error_details",
                description="Extract error descriptions and details from text",
                func=self._extract_error_details
            )
        ]
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert email processor specialized in EPCIS (Electronic Product Code Information Services) error handling.

Your job is to analyze emails related to EPCIS errors and extract key information including:
1. Purchase Order (PO) numbers
2. LOT numbers  
3. Vendor information
4. Error descriptions
5. File names and submission IDs

Use the available tools to extract this information systematically.

Key patterns to look for:
- PO numbers: Usually formatted as PO#12345, Purchase Order: 12345, or similar
- LOT numbers: Often appear as LOT123456, Lot Number: ABC123, or in EPCIS data
- Vendor names: Company names in sender information or email content
- Error descriptions: Technical error messages, validation failures, format issues

Be thorough and accurate in your extraction."""),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        # Create agent
        agent = create_openai_tools_agent(self.llm, tools, prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    def process_email(self, email_data: EmailData) -> ExtractedData:
        """Process email and extract relevant data"""
        try:
            # Combine subject and body for analysis
            email_content = f"Subject: {email_data.subject}\n\nSender: {email_data.sender}\n\nBody: {email_data.body}"
            
            # Use the agent to process the email
            result = self.agent.invoke({
                "input": f"Please analyze this email and extract all relevant PO numbers, LOT numbers, vendor information, and error details:\n\n{email_content}"
            })
            
            # Parse the agent's output and combine with tool results
            extracted_data = ExtractedData(
                po_numbers=self._extract_po_numbers(email_content),
                lot_numbers=self._extract_lot_numbers(email_content),
                vendor_name=self._extract_vendor_info(email_content),
                error_description=self._extract_error_details(email_content),
                submission_id=self._extract_submission_id(email_content),
                file_name=self._extract_file_name(email_content)
            )
            
            logger.info(f"Extracted data from email {email_data.id}: {extracted_data}")
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error processing email: {str(e)}")
            return ExtractedData()
    
    def _extract_po_numbers(self, text: str) -> List[str]:
        """Extract PO numbers from text"""
        patterns = [
            r'PO[:#\s]*([A-Z0-9-]{5,15})',
            r'Purchase\s+Order[:#\s]*([A-Z0-9-]{5,15})',
            r'P\.O\.[:#\s]*([A-Z0-9-]{5,15})',
            r'Order\s+Number[:#\s]*([A-Z0-9-]{5,15})',
            r'bizTransaction[^>]*>([^<]*PO[^<]*)',
            r'urn:epcglobal:cbv:bt:[^:]*:([A-Z0-9-]+)'
        ]
        
        po_numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Clean up the match
                cleaned = re.sub(r'[^\w-]', '', match).upper()
                if len(cleaned) >= 5 and cleaned not in po_numbers:
                    po_numbers.append(cleaned)
        
        logger.info(f"Extracted PO numbers: {po_numbers}")
        return po_numbers
    
    def _extract_lot_numbers(self, text: str) -> List[str]:
        """Extract LOT numbers from text"""
        patterns = [
            r'LOT[:#\s]*([A-Z0-9-]{3,20})',
            r'Lot\s+Number[:#\s]*([A-Z0-9-]{3,20})',
            r'Batch[:#\s]*([A-Z0-9-]{3,20})',
            r'lotNumber[">:\s]*([A-Z0-9-]{3,20})',
            r'<lotNumber>([^<]+)</lotNumber>',
            r'"lotNumber"[:\s]*"([^"]+)"'
        ]
        
        lot_numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                cleaned = re.sub(r'[^\w-]', '', match).upper()
                if len(cleaned) >= 3 and cleaned not in lot_numbers:
                    lot_numbers.append(cleaned)
        
        logger.info(f"Extracted LOT numbers: {lot_numbers}")
        return lot_numbers
    
    def _extract_vendor_info(self, text: str) -> Optional[str]:
        """Extract vendor name from text"""
        # Try to extract from sender email
        sender_match = re.search(r'Sender:\s*([^<\n]+)', text)
        if sender_match:
            sender = sender_match.group(1).strip()
            # Extract company name from email
            if '@' in sender:
                domain = sender.split('@')[1].split('.')[0]
                return domain.replace('-', ' ').title()
        
        # Look for vendor mentions in content
        vendor_patterns = [
            r'Vendor[:\s]+([A-Za-z0-9\s&.-]+)',
            r'Supplier[:\s]+([A-Za-z0-9\s&.-]+)',
            r'Company[:\s]+([A-Za-z0-9\s&.-]+)',
            r'From[:\s]+([A-Za-z0-9\s&.-]+)'
        ]
        
        for pattern in vendor_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                vendor_name = match.group(1).strip()
                if len(vendor_name) > 2 and len(vendor_name) < 50:
                    return vendor_name
        
        return None
    
    def _extract_error_details(self, text: str) -> Optional[str]:
        """Extract error descriptions from text"""
        error_patterns = [
            r'Error[s]?[:\s]+(.*?)(?:\n\n|\Z)',
            r'Validation\s+(?:Error|Failed)[:\s]+(.*?)(?:\n\n|\Z)',
            r'Invalid[:\s]+(.*?)(?:\n\n|\Z)',
            r'Missing[:\s]+(.*?)(?:\n\n|\Z)',
            r'Failed[:\s]+(.*?)(?:\n\n|\Z)'
        ]
        
        for pattern in error_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                error_desc = match.group(1).strip()
                if len(error_desc) > 10:
                    return error_desc[:500]  # Limit length
        
        return None
    
    def _extract_submission_id(self, text: str) -> Optional[str]:
        """Extract submission ID from text"""
        patterns = [
            r'Submission\s+ID[:\s]*([a-f0-9-]{36})',
            r'ID[:\s]*([a-f0-9-]{36})',
            r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_file_name(self, text: str) -> Optional[str]:
        """Extract file name from text"""
        patterns = [
            r'File[:\s]+([A-Za-z0-9_.-]+\.(?:xml|json))',
            r'Filename[:\s]+([A-Za-z0-9_.-]+\.(?:xml|json))',
            r'([A-Za-z0-9_.-]+\.(?:xml|json))'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
